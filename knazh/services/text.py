"""Normalização de texto para busca (sem acentos, minúsculas, espaços colapsados)."""
from __future__ import annotations

import re
import unicodedata

_WS = re.compile(r"\s+")


def normalize(value: str | None) -> str:
    if not value:
        return ""
    decomposed = unicodedata.normalize("NFKD", value)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return _WS.sub(" ", stripped.lower()).strip()


def slugify(value: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", normalize(value)).strip("-")
    return base or "item"
