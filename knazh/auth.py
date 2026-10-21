"""Sessão do cliente (login por e-mail e senha) — senhas com hash do Werkzeug."""
from __future__ import annotations

from functools import wraps

from flask import abort, g, redirect, request, session, url_for

from .extensions import db
from .models import Customer


def load_customer() -> None:
    g.customer = None
    cid = session.get("customer_id")
    if cid:
        g.customer = db.session.get(Customer, cid)
        if g.customer is None:
            session.pop("customer_id", None)


def login_customer(customer: Customer) -> None:
    keep = {k: session[k] for k in ("cart", "orders") if k in session}
    session.clear()  # evita fixação de sessão
    session.update(keep)
    session["customer_id"] = customer.id
    session.permanent = True


def logout_customer() -> None:
    keep = {k: session[k] for k in ("cart",) if k in session}
    session.clear()
    session.update(keep)


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if g.get("customer") is None:
            return redirect(url_for("account.login", next=request.full_path.rstrip("?")))
        return view(*args, **kwargs)

    return wrapper


def require_admin():
    """Verificação de acesso administrativo, sempre feita no servidor a partir da conta carregada do banco
    nesta requisição (g.customer). Nada vindo do navegador (URL, formulário, cookie) concede privilégio.

    Retorna uma resposta de redirecionamento para visitantes, aborta com 403 para clientes comuns e
    retorna None quando o acesso é permitido.
    """
    customer = g.get("customer")
    if customer is None:
        # Em requisições que não são GET, voltar ao painel (um POST não pode ser repetido como GET após o login).
        target = request.full_path.rstrip("?") if request.method == "GET" else url_for("admin.products")
        return redirect(url_for("account.login", next=target))
    if customer.is_admin is not True:
        abort(403)
    return None


def require_admin_manager():
    """Como require_admin(), mas exige também a permissão de gerenciar administradores (checada no servidor,
    na conta relida do banco nesta requisição). Administrador sem a permissão recebe 403."""
    denied = require_admin()
    if denied is not None:
        return denied
    if g.customer.can_manage_admins is not True:
        abort(403)
    return None


def admin_manager_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        denied = require_admin_manager()
        if denied is not None:
            return denied
        return view(*args, **kwargs)

    return wrapper


def admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        denied = require_admin()
        if denied is not None:
            return denied
        return view(*args, **kwargs)

    return wrapper
