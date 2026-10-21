"""Modelos de dados. Valores monetários em centavos inteiros."""
from __future__ import annotations

import secrets
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, UniqueConstraint, event, false
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db
from .services.text import normalize


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False, index=True)
    name = db.Column(db.String(80), nullable=False)
    description = db.Column(db.String(300), nullable=False, default="")
    icon = db.Column(db.String(40), nullable=False, default="package")
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    products = db.relationship("Product", back_populates="category", lazy="dynamic")


class Product(db.Model):
    __tablename__ = "products"
    __table_args__ = (CheckConstraint("price_cents > 0", name="ck_product_price_positive"),)

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(400), nullable=False, default="")
    details = db.Column(db.Text, nullable=False, default="")
    price_cents = db.Column(db.Integer, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False, index=True)
    image = db.Column(db.String(200), nullable=False, default="")  # caminho relativo a /static
    image_alt = db.Column(db.String(200), nullable=False, default="")
    is_available = db.Column(db.Boolean, nullable=False, default=True)
    is_featured = db.Column(db.Boolean, nullable=False, default=False)
    popularity = db.Column(db.Integer, nullable=False, default=0)
    is_demo = db.Column(db.Boolean, nullable=False, default=False)
    search_text = db.Column(db.Text, nullable=False, default="", index=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    category = db.relationship("Category", back_populates="products")

    def refresh_search_text(self) -> None:
        cat = self.category.name if self.category is not None else ""
        self.search_text = normalize(f"{self.name} {self.description} {self.details} {cat}")


@event.listens_for(Product, "before_insert")
@event.listens_for(Product, "before_update")
def _product_search_text(_mapper, _connection, target: Product) -> None:
    target.refresh_search_text()


class Customer(db.Model):
    __tablename__ = "customers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(254), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(30), nullable=False, default="")
    password_hash = db.Column(db.String(255), nullable=False)
    # Papel administrativo (catálogo). Nunca vem de formulário público: só o painel (por quem gerencia administradores)
    # ou os comandos de linha (`provision-initial-admin`, `promote-admin`) alteram estes campos.
    is_admin = db.Column(db.Boolean, nullable=False, default=False, server_default=false())
    # Permissão extra: pode conceder/remover acesso administrativo de outras contas. Só vale junto com is_admin.
    can_manage_admins = db.Column(db.Boolean, nullable=False, default=False, server_default=false())
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    orders = db.relationship("Order", back_populates="customer", lazy="dynamic")
    favorites = db.relationship("Favorite", back_populates="customer", cascade="all, delete-orphan")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Favorite(db.Model):
    __tablename__ = "favorites"
    __table_args__ = (UniqueConstraint("customer_id", "product_id", name="uq_favorite"),)

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    customer = db.relationship("Customer", back_populates="favorites")
    product = db.relationship("Product")


ORDER_STATUS_LABELS = {
    "pendente": "Aguardando confirmação",
    "confirmado": "Confirmado",
    "concluido": "Concluído",
    "cancelado": "Cancelado",
}


def new_public_id() -> str:
    return secrets.token_urlsafe(9)  # ~12 caracteres, não sequencial


class Order(db.Model):
    """Pedido registrado pelo site. NÃO representa pagamento: o site não cobra nada."""

    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.String(24), unique=True, nullable=False, default=new_public_id, index=True)
    number = db.Column(db.String(20), unique=True, nullable=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=True, index=True)
    status = db.Column(db.String(20), nullable=False, default="pendente")
    customer_name = db.Column(db.String(120), nullable=False)
    customer_phone = db.Column(db.String(30), nullable=False)
    customer_email = db.Column(db.String(254), nullable=False, default="")
    notes = db.Column(db.String(500), nullable=False, default="")
    subtotal_cents = db.Column(db.Integer, nullable=False)
    total_cents = db.Column(db.Integer, nullable=False)
    submission_token = db.Column(db.String(64), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    customer = db.relationship("Customer", back_populates="orders")
    items = db.relationship("OrderItem", back_populates="order", cascade="all, delete-orphan", order_by="OrderItem.id")

    @property
    def status_label(self) -> str:
        return ORDER_STATUS_LABELS.get(self.status, self.status)

    @property
    def item_count(self) -> int:
        return sum(i.quantity for i in self.items)


class OrderItem(db.Model):
    """Snapshot do produto no momento do pedido (nome e preço não mudam depois)."""

    __tablename__ = "order_items"
    __table_args__ = (CheckConstraint("quantity > 0", name="ck_item_qty_positive"),)

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    product_name = db.Column(db.String(120), nullable=False)
    unit_price_cents = db.Column(db.Integer, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    line_total_cents = db.Column(db.Integer, nullable=False)

    order = db.relationship("Order", back_populates="items")
    product = db.relationship("Product")


class ContactMessage(db.Model):
    __tablename__ = "contact_messages"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(254), nullable=False)
    subject = db.Column(db.String(60), nullable=False)
    message = db.Column(db.Text, nullable=False)
    email_status = db.Column(db.String(20), nullable=False, default="nao_configurado")  # nao_configurado|enviado|falhou
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
