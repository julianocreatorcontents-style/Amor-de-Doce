"""Dinheiro sempre em centavos inteiros (nunca float)."""
from __future__ import annotations

import re


def format_brl(cents: int | None) -> str:
    """12345 -> 'R$ 123,45'."""
    if cents is None:
        return "—"
    sign = "-" if cents < 0 else ""
    cents = abs(int(cents))
    reais, centavos = divmod(cents, 100)
    return f"{sign}R$ {reais:,}".replace(",", ".") + f",{centavos:02d}"


def line_total(unit_price_cents: int, quantity: int) -> int:
    return int(unit_price_cents) * int(quantity)


_BRL_THOUSANDS = re.compile(r"^\d{1,3}(\.\d{3})+$")
_BRL_FULL = re.compile(r"^\d{1,3}(\.\d{3})*,\d{1,2}$|^\d+,\d{1,2}$")
_BRL_DOT_DECIMAL = re.compile(r"^\d+\.\d{1,2}$")
_BRL_INT = re.compile(r"^\d+$")
MAX_PRICE_CENTS = 10_000_000  # R$ 100.000,00 — teto de sanidade para o cadastro


def parse_brl_to_cents(text: str | None) -> int:
    """Converte o texto digitado em reais ('18', '18,5', 'R$ 1.234,56') para centavos inteiros, sem float.

    Levanta ValueError com mensagem pronta para o usuário se o valor for vazio, negativo, zero, excessivo
    ou ambíguo/inválido.
    """
    raw = (text or "").strip().replace("R$", "").replace("\u00a0", " ").strip().replace(" ", "")
    if not raw:
        raise ValueError("Informe o preço do produto.")
    if raw.startswith("-"):
        raise ValueError("O preço não pode ser negativo.")
    if _BRL_INT.match(raw):
        cents = int(raw) * 100
    elif _BRL_FULL.match(raw):
        reais, frac = raw.replace(".", "").split(",")
        cents = int(reais) * 100 + int(frac.ljust(2, "0"))
    elif _BRL_THOUSANDS.match(raw):
        cents = int(raw.replace(".", "")) * 100
    elif _BRL_DOT_DECIMAL.match(raw):
        reais, frac = raw.split(".")
        cents = int(reais) * 100 + int(frac.ljust(2, "0"))
    else:
        raise ValueError("Preço inválido. Use apenas números, por exemplo 18,50.")
    if cents <= 0:
        raise ValueError("O preço deve ser maior que zero.")
    if cents > MAX_PRICE_CENTS:
        raise ValueError("O preço máximo aceito é R$ 100.000,00.")
    return cents


def cents_to_input(cents: int | None) -> str:
    """1850 -> '18,50' (valor para o campo do formulário, sem 'R$')."""
    if cents is None:
        return ""
    reais, centavos = divmod(abs(int(cents)), 100)
    return f"{reais},{centavos:02d}"
