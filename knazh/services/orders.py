"""Criação de pedidos: revalida tudo no servidor e grava um snapshot dos itens."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import Customer, Order, OrderItem
from . import cart as cart_service


class OrderError(Exception):
    """Mensagem segura para exibir ao visitante."""


def find_by_token(token: str) -> Order | None:
    return db.session.scalar(select(Order).where(Order.submission_token == token))


def create_order(*, name: str, phone: str, email: str, notes: str, customer: Customer | None, token: str) -> Order:
    """Cria o pedido a partir do carrinho da sessão. Preços/totais vêm do banco, nunca do navegador.
    Lança OrderError se o carrinho estiver vazio ou tiver itens indisponíveis."""
    cv = cart_service.view()
    if cv.is_empty:
        raise OrderError("Seu carrinho está vazio.")
    if cv.unavailable_lines:
        names = ", ".join(f"“{l.product.name}”" for l in cv.unavailable_lines)
        raise OrderError(f"Item indisponível no carrinho: {names}. Remova para continuar.")

    subtotal = 0
    order = Order(
        customer_id=customer.id if customer else None,
        status="pendente",
        customer_name=name,
        customer_phone=phone,
        customer_email=email,
        notes=notes,
        subtotal_cents=0,
        total_cents=0,
        submission_token=token,
    )
    for line in cv.lines:
        unit = int(line.product.price_cents)
        total = unit * line.quantity
        subtotal += total
        order.items.append(OrderItem(product_id=line.product.id, product_name=line.product.name,
                                     unit_price_cents=unit, quantity=line.quantity, line_total_cents=total))
    order.subtotal_cents = subtotal
    order.total_cents = subtotal  # sem frete/taxas: ainda não definidos pela KNAZH

    try:
        db.session.add(order)
        db.session.flush()
        order.number = f"KNZ-{order.id:06d}"
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        existing = find_by_token(token)
        if existing is not None:
            return existing
        raise OrderError("Não foi possível registrar o pedido. Tente novamente.") from None
    cart_service.clear()
    return order
