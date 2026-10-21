"""Carrinho: adicionar, atualizar quantidade, remover. Funciona com e sem JavaScript."""
from __future__ import annotations

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, url_for

from ..services import cart as svc
from ..services import catalog as catalog_svc
from ..services.channels import cart_message, get_channels
from ..services.security import safe_next_url

bp = Blueprint("cart", __name__)


def _wants_json() -> bool:
    return request.headers.get("X-Requested-With") == "fetch"


def _reply(ok: bool, message: str, default_endpoint: str = "cart.show"):
    if _wants_json():
        return jsonify(ok=ok, message=message, count=svc.count()), (200 if ok else 400)
    flash(message, "success" if ok else "error")
    return redirect(safe_next_url(request.form.get("next"), url_for(default_endpoint)))


@bp.get("/carrinho")
def show():
    cv = svc.view()
    ch = get_channels()
    suggestions = []
    if cv.lines:
        ids = {l.product.id for l in cv.lines}
        suggestions = [p for p in catalog_svc.featured_products(8) if p.id not in ids and p.is_available][:5]
    if not suggestions:
        suggestions = [p for p in catalog_svc.featured_products(5) if p.is_available][:5]
    wa = ch.whatsapp_link(cart_message(cv.lines, cv.subtotal_cents)) if cv.lines and cv.can_checkout else None
    return render_template("pages/cart.html", cart=cv, suggestions=suggestions, whatsapp_url=wa, max_qty=current_app.config["MAX_QTY_PER_ITEM"])


@bp.post("/carrinho/adicionar")
def add():
    try:
        product = svc.add(request.form.get("product_id"), request.form.get("quantity", 1))
    except svc.CartError as err:
        return _reply(False, str(err))
    return _reply(True, f"“{product.name}” foi adicionado ao carrinho.", "cart.show")


@bp.post("/carrinho/atualizar")
def update():
    try:
        svc.set_quantity(request.form.get("product_id"), request.form.get("quantity"))
    except (svc.CartError, ValueError, TypeError) as err:
        return _reply(False, str(err) if isinstance(err, svc.CartError) else "Item inválido.")
    return _reply(True, "Carrinho atualizado.")


@bp.post("/carrinho/remover")
def remove():
    try:
        svc.remove(request.form.get("product_id"))
    except (ValueError, TypeError):
        return _reply(False, "Item inválido.")
    return _reply(True, "Item removido do carrinho.")
