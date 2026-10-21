"""Consultas e operações do painel administrativo de produtos (sempre validadas no servidor)."""
from __future__ import annotations

from dataclasses import dataclass

from flask import current_app
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import SQLAlchemyError

from ..extensions import db
from ..models import Category, Favorite, OrderItem, Product
from .text import normalize, slugify

STATUS_OPTIONS = [("todos", "Todos"), ("disponiveis", "Disponíveis"), ("indisponiveis", "Indisponíveis")]
_STATUS_KEYS = {k for k, _ in STATUS_OPTIONS}
MAX_QUERY_LENGTH = 80


@dataclass
class AdminFilters:
    q: str = ""
    category: int | None = None
    status: str = "todos"
    page: int = 1

    def as_params(self, **overrides) -> dict:
        data = {"q": self.q, "categoria": self.category, "status": self.status, "pagina": self.page}
        data.update(overrides)
        out = {}
        for key, value in data.items():
            if value in ("", None):
                continue
            if key == "status" and value == "todos":
                continue
            if key == "pagina" and value == 1:
                continue
            out[key] = value
        return out

    @property
    def active(self) -> bool:
        return bool(self.q or self.category or self.status != "todos")


def all_categories() -> list[Category]:
    return list(db.session.scalars(select(Category).order_by(Category.sort_order, Category.name)))


def parse_filters(args) -> AdminFilters:
    valid_ids = {c.id for c in all_categories()}
    q = (args.get("q") or "").strip()[:MAX_QUERY_LENGTH]
    try:
        category = int(args.get("categoria", ""))
    except (TypeError, ValueError):
        category = None
    if category not in valid_ids:
        category = None
    status = args.get("status", "todos")
    status = status if status in _STATUS_KEYS else "todos"
    try:
        page = max(1, min(int(args.get("pagina", 1)), 10_000))
    except (TypeError, ValueError):
        page = 1
    return AdminFilters(q=q, category=category, status=status, page=page)


def stats() -> dict[str, int]:
    total = db.session.scalar(select(func.count(Product.id))) or 0
    available = db.session.scalar(select(func.count(Product.id)).where(Product.is_available.is_(True))) or 0
    categories = db.session.scalar(select(func.count(Category.id)).where(Category.is_active.is_(True))) or 0
    return {"total": total, "available": available, "unavailable": total - available, "categories": categories}


def search_products(filters: AdminFilters):
    stmt = select(Product).join(Category)
    for term in normalize(filters.q).split():
        stmt = stmt.where(Product.search_text.contains(term, autoescape=True))
    if filters.category:
        stmt = stmt.where(Product.category_id == filters.category)
    if filters.status == "disponiveis":
        stmt = stmt.where(Product.is_available.is_(True))
    elif filters.status == "indisponiveis":
        stmt = stmt.where(Product.is_available.is_(False))
    stmt = stmt.order_by(func.lower(Product.name).asc(), Product.id.asc())
    return db.paginate(stmt, page=filters.page, per_page=current_app.config["ADMIN_PER_PAGE"], error_out=False)


def unique_slug(name: str) -> str:
    """Slug seguro e único a partir do nome (só para produtos novos; a edição preserva o slug atual)."""
    base = slugify(name)[:100].strip("-") or "produto"
    candidate, n = base, 2
    while db.session.scalar(select(Product.id).where(Product.slug == candidate)) is not None:
        candidate = f"{base}-{n}"
        n += 1
    return candidate


def form_categories(product: Product | None = None) -> list[Category]:
    """Categorias ativas; na edição, inclui também a categoria atual do produto mesmo se estiver inativa."""
    cats = [c for c in all_categories() if c.is_active or (product is not None and c.id == product.category_id)]
    return cats


def delete_product(product: Product) -> None:
    """Exclui o produto preservando o histórico.

    - Itens de pedido guardam snapshot (nome, preço, totais): só o vínculo product_id é anulado; nada é recalculado.
    - Favoritos do produto são removidos (não têm valor sem o produto).
    O SQLite não aplica ON DELETE por padrão, então os dois passos são feitos explicitamente, na mesma transação.
    Em caso de erro faz rollback e relança SQLAlchemyError para a rota mostrar uma mensagem segura.
    """
    pid = product.id
    try:
        db.session.execute(update(OrderItem).where(OrderItem.product_id == pid).values(product_id=None))
        db.session.execute(delete(Favorite).where(Favorite.product_id == pid))
        db.session.delete(product)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise
