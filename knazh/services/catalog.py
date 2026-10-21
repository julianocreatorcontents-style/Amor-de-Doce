"""Consulta ao catálogo: filtros, busca, ordenação e paginação — sempre validados no servidor."""
from __future__ import annotations

from dataclasses import dataclass, field

from flask import current_app
from sqlalchemy import func, select

from ..extensions import db
from ..models import Category, Product
from .text import normalize

SORT_OPTIONS = [
    ("populares", "Mais populares"),
    ("menor-preco", "Menor preço"),
    ("maior-preco", "Maior preço"),
    ("nome", "Nome (A–Z)"),
    ("recentes", "Mais recentes"),
]
_SORT_KEYS = {k for k, _ in SORT_OPTIONS}
MAX_QUERY_LENGTH = 80


@dataclass
class CatalogFilters:
    q: str = ""
    categories: list[str] = field(default_factory=list)
    price: str = ""
    sort: str = "populares"
    page: int = 1
    forced: str | None = None  # categoria fixa da página de categoria (não conta como filtro do usuário)

    @property
    def terms(self) -> list[str]:
        return normalize(self.q).split()

    def as_params(self, **overrides) -> dict:
        """Parâmetros de URL (para links de paginação/limpar filtros)."""
        data = {"q": self.q, "categoria": self.categories, "preco": self.price, "ordem": self.sort, "pagina": self.page}
        data.update(overrides)
        out = {}
        for k, v in data.items():
            if v in ("", None, []):
                continue
            if k == "ordem" and v == "populares":
                continue
            if k == "pagina" and v == 1:
                continue
            out[k] = v
        return out

    @property
    def user_categories(self) -> list[str]:
        return [] if self.forced else self.categories

    @property
    def has_filters(self) -> bool:
        return bool(self.user_categories or self.price)


def active_categories() -> list[Category]:
    return list(db.session.scalars(select(Category).where(Category.is_active.is_(True)).order_by(Category.sort_order, Category.name)))


def parse_filters(args, forced_category: str | None = None) -> CatalogFilters:
    valid_slugs = {c.slug for c in active_categories()}
    q = (args.get("q") or "").strip()[:MAX_QUERY_LENGTH]
    cats = [s for s in args.getlist("categoria") if s in valid_slugs]
    if forced_category:
        cats = [forced_category]
    price_keys = {r[0] for r in current_app.config["PRICE_RANGES"]}
    price = args.get("preco", "")
    price = price if price in price_keys else ""
    sort = args.get("ordem", "populares")
    sort = sort if sort in _SORT_KEYS else "populares"
    try:
        page = max(1, min(int(args.get("pagina", 1)), 10_000))
    except (TypeError, ValueError):
        page = 1
    return CatalogFilters(q=q, categories=list(dict.fromkeys(cats)), price=price, sort=sort, page=page, forced=forced_category)


def _price_bounds(key: str) -> tuple[int | None, int | None]:
    for k, _label, lo, hi in current_app.config["PRICE_RANGES"]:
        if k == key:
            return lo, hi
    return None, None


def _base_stmt(filters: CatalogFilters, *, with_categories: bool = True):
    stmt = select(Product).join(Category).where(Category.is_active.is_(True))
    for term in filters.terms:
        stmt = stmt.where(Product.search_text.contains(term, autoescape=True))
    if with_categories and filters.categories:
        stmt = stmt.where(Category.slug.in_(filters.categories))
    if filters.price:
        lo, hi = _price_bounds(filters.price)
        if lo is not None:
            stmt = stmt.where(Product.price_cents >= lo)
        if hi is not None:
            stmt = stmt.where(Product.price_cents <= hi)
    return stmt


def _order_by(sort: str):
    return {
        "menor-preco": [Product.price_cents.asc(), Product.name.asc()],
        "maior-preco": [Product.price_cents.desc(), Product.name.asc()],
        "nome": [func.lower(Product.name).asc()],
        "recentes": [Product.created_at.desc(), Product.id.desc()],
    }.get(sort, [Product.popularity.desc(), Product.name.asc()])


def search_products(filters: CatalogFilters):
    stmt = _base_stmt(filters).order_by(*_order_by(filters.sort), Product.id.asc())
    return db.paginate(stmt, page=filters.page, per_page=current_app.config["PRODUCTS_PER_PAGE"], error_out=False)


def category_counts(filters: CatalogFilters) -> dict[str, int]:
    """Contagem por categoria respeitando busca e preço (mas não a seleção de categorias)."""
    sub = _base_stmt(filters, with_categories=False).subquery()
    rows = db.session.execute(
        select(Category.slug, func.count(sub.c.id)).select_from(Category).outerjoin(sub, sub.c.category_id == Category.id)
        .where(Category.is_active.is_(True)).group_by(Category.slug)
    ).all()
    return {slug: n for slug, n in rows}


def get_category(slug: str) -> Category | None:
    return db.session.scalar(select(Category).where(Category.slug == slug, Category.is_active.is_(True)))


def get_product(slug: str) -> Product | None:
    return db.session.scalar(select(Product).join(Category).where(Product.slug == slug, Category.is_active.is_(True)))


def featured_products(limit: int = 5) -> list[Product]:
    stmt = (select(Product).join(Category).where(Category.is_active.is_(True), Product.is_featured.is_(True))
            .order_by(Product.popularity.desc(), Product.id).limit(limit))
    return list(db.session.scalars(stmt))


def related_products(product: Product, limit: int = 5) -> list[Product]:
    stmt = (select(Product).where(Product.category_id == product.category_id, Product.id != product.id, Product.is_available.is_(True))
            .order_by(Product.popularity.desc(), Product.id).limit(limit))
    items = list(db.session.scalars(stmt))
    if len(items) < limit:
        extra = select(Product).join(Category).where(Product.id != product.id, Product.is_available.is_(True), Category.is_active.is_(True),
                                                      Product.id.notin_([p.id for p in items] or [0])).order_by(Product.popularity.desc()).limit(limit - len(items))
        items += list(db.session.scalars(extra))
    return items
