"""Carrinho em sessão (cookie assinado). Guarda só {id_do_produto: quantidade}.
Preços, nomes e disponibilidade são SEMPRE lidos do banco — o navegador nunca é fonte de verdade."""
from __future__ import annotations

from dataclasses import dataclass, field

from flask import current_app, session
from sqlalchemy import select

from ..extensions import db
from ..models import Product
from .money import line_total

SESSION_KEY = "cart"


class CartError(Exception):
    """Mensagem segura para exibir ao visitante."""


@dataclass
class CartLine:
    product: Product
    quantity: int

    @property
    def available(self) -> bool:
        return bool(self.product.is_available)

    @property
    def total_cents(self) -> int:
        return line_total(self.product.price_cents, self.quantity)


@dataclass
class CartView:
    lines: list[CartLine] = field(default_factory=list)
    notices: list[str] = field(default_factory=list)

    @property
    def count(self) -> int:
        return sum(l.quantity for l in self.lines)

    @property
    def subtotal_cents(self) -> int:
        return sum(l.total_cents for l in self.lines if l.available)

    @property
    def unavailable_lines(self) -> list[CartLine]:
        return [l for l in self.lines if not l.available]

    @property
    def can_checkout(self) -> bool:
        return bool(self.lines) and not self.unavailable_lines

    @property
    def is_empty(self) -> bool:
        return not self.lines


def _raw() -> dict[str, int]:
    data = session.get(SESSION_KEY)
    if not isinstance(data, dict):
        return {}
    clean: dict[str, int] = {}
    for k, v in data.items():
        try:
            pid, qty = int(k), int(v)
        except (TypeError, ValueError):
            continue
        if pid > 0 and qty > 0:
            clean[str(pid)] = min(qty, current_app.config["MAX_QTY_PER_ITEM"])
    return clean


def _save(data: dict[str, int]) -> None:
    session[SESSION_KEY] = data
    session.permanent = True


def parse_quantity(value, default: int = 1) -> int:
    try:
        qty = int(str(value).strip())
    except (TypeError, ValueError):
        raise CartError("Quantidade inválida.") from None
    return qty


def add(product_id, quantity=1) -> Product:
    qty = parse_quantity(quantity)
    if qty < 1:
        raise CartError("Escolha pelo menos 1 unidade.")
    try:
        pid = int(product_id)
    except (TypeError, ValueError):
        raise CartError("Produto inválido.") from None
    product = db.session.get(Product, pid)
    if product is None or not product.category.is_active:
        raise CartError("Esse produto não está mais no cardápio.")
    if not product.is_available:
        raise CartError(f"“{product.name}” está indisponível no momento.")
    cart = _raw()
    max_qty = current_app.config["MAX_QTY_PER_ITEM"]
    if str(pid) not in cart and len(cart) >= current_app.config["MAX_CART_LINES"]:
        raise CartError("Seu carrinho atingiu o limite de itens diferentes.")
    new_qty = cart.get(str(pid), 0) + qty
    if new_qty > max_qty:
        raise CartError(f"O máximo é {max_qty} unidades por produto.")
    cart[str(pid)] = new_qty
    _save(cart)
    return product


def set_quantity(product_id, quantity) -> None:
    qty = parse_quantity(quantity)
    cart = _raw()
    key = str(int(product_id))
    if key not in cart:
        raise CartError("Esse item não está no carrinho.")
    if qty <= 0:
        cart.pop(key)
    else:
        max_qty = current_app.config["MAX_QTY_PER_ITEM"]
        if qty > max_qty:
            raise CartError(f"O máximo é {max_qty} unidades por produto.")
        cart[key] = qty
    _save(cart)


def remove(product_id) -> None:
    cart = _raw()
    cart.pop(str(int(product_id)), None)
    _save(cart)


def clear() -> None:
    session.pop(SESSION_KEY, None)


def view() -> CartView:
    raw = _raw()
    if not raw:
        return CartView()
    ids = [int(k) for k in raw]
    products = {p.id: p for p in db.session.scalars(select(Product).where(Product.id.in_(ids)))}
    cv = CartView()
    cleaned = dict(raw)
    for pid in ids:
        product = products.get(pid)
        if product is None or not product.category.is_active:
            cleaned.pop(str(pid), None)
            cv.notices.append("Um item foi removido do carrinho porque não está mais no cardápio.")
            continue
        cv.lines.append(CartLine(product=product, quantity=raw[str(pid)]))
    if cleaned != raw:
        _save(cleaned)
    for line in cv.unavailable_lines:
        cv.notices.append(f"“{line.product.name}” ficou indisponível. Remova o item para continuar.")
    return cv


def count() -> int:
    return sum(_raw().values())
