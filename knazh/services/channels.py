"""Canais comerciais (WhatsApp / iFood / redes). Tudo vem da configuração; nada é inventado.
Um link para a loja do iFood NÃO é integração de pedidos; abrir o WhatsApp NÃO garante envio/confirmação."""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import quote, urlparse

from flask import current_app

from .money import format_brl


def normalize_whatsapp(number: str | None) -> str | None:
    """Retorna só dígitos com DDI (55 assumido para números BR de 10/11 dígitos) ou None se inválido."""
    digits = re.sub(r"\D", "", number or "")
    if len(digits) in (10, 11):
        digits = "55" + digits
    if 12 <= len(digits) <= 15:
        return digits
    return None


def format_phone_display(digits: str) -> str:
    if digits.startswith("55") and len(digits) in (12, 13):
        ddd, rest = digits[2:4], digits[4:]
        return f"({ddd}) {rest[:-4]}-{rest[-4:]}"
    return "+" + digits


def safe_https_url(url: str | None) -> str | None:
    """Aceita apenas URLs https com host válido (bloqueia javascript:, data:, http:, etc.)."""
    if not url:
        return None
    parsed = urlparse(url.strip())
    if parsed.scheme != "https" or not parsed.netloc or " " in url or not re.fullmatch(r"[A-Za-z0-9.-]+(:\d+)?", parsed.netloc):
        return None
    return url.strip()


@dataclass(frozen=True)
class Channels:
    whatsapp_digits: str | None
    ifood_url: str | None
    instagram: str | None
    tiktok: str | None
    facebook: str | None
    youtube: str | None
    email: str | None

    @property
    def whatsapp_configured(self) -> bool:
        return bool(self.whatsapp_digits)

    @property
    def ifood_configured(self) -> bool:
        return bool(self.ifood_url)

    @property
    def whatsapp_display(self) -> str:
        return format_phone_display(self.whatsapp_digits) if self.whatsapp_digits else ""

    def whatsapp_link(self, message: str | None = None) -> str | None:
        if not self.whatsapp_digits:
            return None
        url = f"https://wa.me/{self.whatsapp_digits}"
        if message:
            url += "?text=" + quote(message[:1500], safe="")
        return url

    @property
    def socials(self) -> list[tuple[str, str, str]]:
        items = [("instagram", "Instagram", self.instagram), ("tiktok", "TikTok", self.tiktok),
                 ("facebook", "Facebook", self.facebook), ("youtube", "YouTube", self.youtube)]
        return [(k, label, url) for k, label, url in items if url]


def get_channels() -> Channels:
    c = current_app.config
    email = (c.get("PUBLIC_CONTACT_EMAIL") or "").strip()
    return Channels(
        whatsapp_digits=normalize_whatsapp(c.get("WHATSAPP_NUMBER")),
        ifood_url=safe_https_url(c.get("IFOOD_STORE_URL")),
        instagram=safe_https_url(c.get("INSTAGRAM_URL")),
        tiktok=safe_https_url(c.get("TIKTOK_URL")),
        facebook=safe_https_url(c.get("FACEBOOK_URL")),
        youtube=safe_https_url(c.get("YOUTUBE_URL")),
        email=email if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) else None,
    )


def cart_message(lines, subtotal_cents: int) -> str:
    rows = ["Olá, KNAZH! Gostaria de pedir:"]
    for l in lines:
        rows.append(f"• {l.quantity}x {l.product.name} — {format_brl(l.total_cents)}")
    rows.append(f"Total estimado: {format_brl(subtotal_cents)}")
    return "\n".join(rows)


def order_message(order) -> str:
    rows = [f"Olá, KNAZH! Registrei o pedido {order.number} no site:"]
    for i in order.items:
        rows.append(f"• {i.quantity}x {i.product_name} — {format_brl(i.line_total_cents)}")
    rows.append(f"Total estimado: {format_brl(order.total_cents)}")
    rows.append(f"Nome: {order.customer_name}")
    if order.notes:
        rows.append(f"Observações: {order.notes}")
    return "\n".join(rows)
