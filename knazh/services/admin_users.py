"""Gestão de administradores: regras de negócio, sempre executadas no servidor.

Quem pode agir: somente uma conta que, no banco e NESTA requisição, tenha `is_admin` e `can_manage_admins`.
Garantias:
- ninguém altera o próprio acesso pelo painel (evita se trancar fora sem querer);
- a conta que perde acesso perde também `can_manage_admins`;
- o ÚLTIMO gestor nunca é removido: a remoção é UM único UPDATE condicional (a contagem de gestores e a verificação
  de que quem age ainda é gestor acontecem dentro da própria instrução, então duas remoções simultâneas não zeram
  os gestores). Recuperação, se algo der errado: `flask --app wsgi promote-admin EMAIL --manager` (exige acesso ao servidor).
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import and_, exists, func, or_, select, update
from sqlalchemy.exc import SQLAlchemyError

from ..extensions import db
from ..models import Customer

STATUS_OPTIONS = [("todos", "Todos"), ("admins", "Administradores"), ("clientes", "Clientes")]
_STATUS_KEYS = {k for k, _ in STATUS_OPTIONS}
MAX_QUERY_LENGTH = 80


@dataclass
class Outcome:
    ok: bool
    message: str


@dataclass
class UserFilters:
    q: str = ""
    status: str = "todos"
    page: int = 1

    @property
    def active(self) -> bool:
        return bool(self.q or self.status != "todos")

    def as_params(self, **overrides) -> dict:
        data = {"q": self.q, "status": self.status, "pagina": self.page}
        data.update(overrides)
        out = {}
        for k, v in data.items():
            if v in ("", None):
                continue
            if (k == "status" and v == "todos") or (k == "pagina" and v == 1):
                continue
            out[k] = v
        return out


def parse_filters(args) -> UserFilters:
    q = (args.get("q") or "").strip()[:MAX_QUERY_LENGTH]
    status = args.get("status", "todos")
    status = status if status in _STATUS_KEYS else "todos"
    try:
        page = max(1, min(int(args.get("pagina", 1)), 10_000))
    except (TypeError, ValueError):
        page = 1
    return UserFilters(q=q, status=status, page=page)


def search_users(filters: UserFilters, per_page: int):
    stmt = select(Customer)
    for term in filters.q.lower().split():
        like = "%" + term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        stmt = stmt.where(or_(func.lower(Customer.email).like(like, escape="\\"), func.lower(Customer.name).like(like, escape="\\")))
    if filters.status == "admins":
        stmt = stmt.where(Customer.is_admin.is_(True))
    elif filters.status == "clientes":
        stmt = stmt.where(Customer.is_admin.is_(False))
    # administradores primeiro, depois ordem alfabética
    stmt = stmt.order_by(Customer.is_admin.desc(), func.lower(Customer.name), Customer.id)
    return db.paginate(stmt, page=filters.page, per_page=per_page, error_out=False)


def stats() -> dict:
    row = db.session.execute(select(
        func.count(Customer.id),
        func.coalesce(func.sum(db.case((Customer.is_admin.is_(True), 1), else_=0)), 0),
        func.coalesce(func.sum(db.case((Customer.can_manage_admins.is_(True), 1), else_=0)), 0),
    )).one()
    return {"total": row[0], "admins": int(row[1]), "managers": int(row[2])}


def manager_count() -> int:
    return db.session.scalar(select(func.count(Customer.id)).where(Customer.is_admin.is_(True), Customer.can_manage_admins.is_(True))) or 0


def _actor_is_manager(actor_id: int):
    """Subconsulta: a conta que age ainda é gestora (valor atual do banco, não o da sessão)."""
    return exists().where(Customer.id == actor_id, Customer.is_admin.is_(True), Customer.can_manage_admins.is_(True))


def _label(c: Customer) -> str:
    return c.name or c.email


GENERIC_ERROR = "Não foi possível salvar agora. Nada foi alterado; tente novamente em instantes."
NOT_ALLOWED = "Você não tem permissão para gerenciar administradores."


def grant_admin(actor: Customer, target_id: int, *, can_manage: bool = False) -> Outcome:
    """Concede acesso administrativo (e, opcionalmente, a permissão de gerenciar administradores)."""
    target = db.session.get(Customer, target_id)
    if target is None:
        return Outcome(False, "Essa conta não foi encontrada.")
    if target.id == actor.id:
        return Outcome(False, "Você não pode alterar o seu próprio acesso por aqui.")
    if target.is_admin and (target.can_manage_admins or not can_manage):
        return Outcome(False, f"{_label(target)} já é administrador(a). Nada foi alterado.")
    values = {"is_admin": True, "can_manage_admins": bool(can_manage)}
    try:
        result = db.session.execute(
            update(Customer).where(Customer.id == target.id, _actor_is_manager(actor.id)).values(**values).execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            db.session.rollback()
            return Outcome(False, NOT_ALLOWED)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return Outcome(False, GENERIC_ERROR)
    db.session.expire_all()
    role = "administrador(a) com permissão de gerenciar administradores" if can_manage else "administrador(a)"
    return Outcome(True, f"{_label(target)} agora é {role}.")


def revoke_admin(actor: Customer, target_id: int) -> Outcome:
    """Remove o acesso administrativo (a conta continua existindo como cliente comum)."""
    target = db.session.get(Customer, target_id)
    if target is None:
        return Outcome(False, "Essa conta não foi encontrada.")
    if target.id == actor.id:
        return Outcome(False, "Você não pode remover o seu próprio acesso. Peça a outra pessoa que gerencia administradores.")
    if not target.is_admin:
        return Outcome(False, f"{_label(target)} não é administrador(a). Nada foi alterado.")
    last_manager_guard = or_(
        Customer.can_manage_admins.is_(False),
        select(func.count(Customer.id)).where(Customer.is_admin.is_(True), Customer.can_manage_admins.is_(True)).scalar_subquery() > 1,
    )
    try:
        result = db.session.execute(
            update(Customer)
            .where(Customer.id == target.id, Customer.is_admin.is_(True), _actor_is_manager(actor.id), last_manager_guard)
            .values(is_admin=False, can_manage_admins=False)
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            db.session.rollback()
            db.session.expire_all()
            fresh_actor = db.session.get(Customer, actor.id)
            if fresh_actor is None or not (fresh_actor.is_admin and fresh_actor.can_manage_admins):
                return Outcome(False, NOT_ALLOWED)
            return Outcome(False, "Esta é a única conta que gerencia administradores e não pode ser removida. "
                                  "Conceda a permissão de gerenciar administradores a outra pessoa antes.")
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return Outcome(False, GENERIC_ERROR)
    db.session.expire_all()
    return Outcome(True, f"O acesso administrativo de {_label(target)} foi removido. A conta continua como cliente comum.")
