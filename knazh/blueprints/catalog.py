"""Cardápio, categorias, busca e detalhes de produto."""
from __future__ import annotations

from flask import Blueprint, abort, current_app, redirect, render_template, request, url_for

from ..models import Favorite
from ..services import catalog as svc
from flask import g
from ..extensions import db
from sqlalchemy import select

bp = Blueprint("catalog", __name__)


def _favorite_ids() -> set[int]:
    if g.get("customer") is None:
        return set()
    return set(db.session.scalars(select(Favorite.product_id).where(Favorite.customer_id == g.customer.id)))


def _listing(mode: str, category=None, filters=None):
    filters = filters or svc.parse_filters(request.args, forced_category=category.slug if category else None)
    page = svc.search_products(filters)
    counts = svc.category_counts(filters)
    return render_template(
        "pages/catalog.html", mode=mode, category=category, filters=filters, page=page, counts=counts,
        categories=svc.active_categories(), price_ranges=current_app.config["PRICE_RANGES"], sorts=svc.SORT_OPTIONS,
        favorite_ids=_favorite_ids(),
    )


@bp.get("/cardapio")
def catalog():
    return _listing("catalog")


@bp.get("/cardapio/<slug>")
def category(slug: str):
    cat = svc.get_category(slug)
    if cat is None:
        abort(404)
    return _listing("category", category=cat)


@bp.get("/busca")
def search():
    filters = svc.parse_filters(request.args)
    if not filters.q:
        return redirect(url_for("catalog.catalog"))
    return _listing("search", filters=filters)


@bp.get("/produto/<slug>")
def product(slug: str):
    p = svc.get_product(slug)
    if p is None:
        abort(404)
    return render_template("pages/product.html", product=p, related=svc.related_products(p), favorite_ids=_favorite_ids(),
                           max_qty=current_app.config["MAX_QTY_PER_ITEM"])
