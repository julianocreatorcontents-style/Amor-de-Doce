"""Finalização do pedido e confirmação. O site NÃO cobra: o pedido fica 'Aguardando confirmação'."""
from __future__ import annotations

import secrets

from flask import Blueprint, abort, flash, g, redirect, render_template, request, session, url_for
from sqlalchemy import select

from ..extensions import db
from ..forms import CheckoutForm
from ..models import Order
from ..services import cart as cart_service
from ..services import orders as orders_service
from ..services.channels import cart_message, get_channels, order_message

bp = Blueprint("checkout", __name__)
TOKEN_KEY = "checkout_token"


def _remember_order(order: Order) -> None:
    mine = [p for p in session.get("orders", []) if p != order.public_id]
    mine.append(order.public_id)
    session["orders"] = mine[-20:]


def _can_view(order: Order) -> bool:
    if order.public_id in session.get("orders", []):
        return True
    return g.get("customer") is not None and order.customer_id == g.customer.id


@bp.route("/finalizar", methods=["GET", "POST"])
def checkout():
    cv = cart_service.view()
    form = CheckoutForm()

    if request.method == "POST":
        # Reenvio do mesmo formulário (duplo clique/atualizar): devolve o pedido já criado.
        token = (request.form.get("submission_token") or "")[:64]
        existing = orders_service.find_by_token(token) if token else None
        if existing is not None and _can_view(existing):
            return redirect(url_for("checkout.confirmation", public_id=existing.public_id))

    if cv.is_empty:
        flash("Seu carrinho está vazio. Escolha alguns doces para continuar.", "info")
        return redirect(url_for("cart.show"))
    if not cv.can_checkout:
        for note in cv.notices:
            flash(note, "error")
        return redirect(url_for("cart.show"))

    if form.validate_on_submit():
        try:
            order = orders_service.create_order(
                name=form.name.data, phone=form.phone.data, email=(form.email.data or "").lower(),
                notes=form.notes.data or "", customer=g.get("customer"), token=form.submission_token.data,
            )
        except orders_service.OrderError as err:
            flash(str(err), "error")
            return redirect(url_for("cart.show"))
        _remember_order(order)
        session.pop(TOKEN_KEY, None)
        return redirect(url_for("checkout.confirmation", public_id=order.public_id))

    if request.method == "POST":
        flash("Confira os campos destacados e tente novamente.", "error")
    else:
        session[TOKEN_KEY] = secrets.token_urlsafe(18)
        form.submission_token.data = session[TOKEN_KEY]
        if g.get("customer"):
            form.name.data, form.phone.data = g.customer.name, g.customer.phone
            form.email.data = g.customer.email
    return render_template("pages/checkout.html", cart=cv, form=form)


@bp.get("/pedido/<public_id>")
def confirmation(public_id: str):
    order = db.session.scalar(select(Order).where(Order.public_id == public_id))
    if order is None or not _can_view(order):
        abort(404)
    ch = get_channels()
    return render_template("pages/order_confirmation.html", order=order, whatsapp_url=ch.whatsapp_link(order_message(order)))
