from __future__ import annotations

import time
from urllib.parse import urlparse


def safe_next_url(target: str | None, default: str = "/") -> str:
    """Só aceita caminhos relativos do próprio site (evita open redirect)."""
    if not target or not target.startswith("/") or target.startswith("//") or "\\" in target:
        return default
    parsed = urlparse(target)
    if parsed.scheme or parsed.netloc:
        return default
    return target


class Throttle:
    """Limitador simples em memória (por processo): N falhas em uma janela de tempo."""

    def __init__(self, limit: int = 5, window_seconds: int = 600):
        self.limit, self.window = limit, window_seconds
        self._hits: dict[str, list[float]] = {}

    def _recent(self, key: str) -> list[float]:
        now = time.monotonic()
        hits = [t for t in self._hits.get(key, []) if now - t < self.window]
        self._hits[key] = hits
        return hits

    def blocked(self, key: str) -> bool:
        return len(self._recent(key)) >= self.limit

    def hit(self, key: str) -> None:
        self._recent(key).append(time.monotonic())

    def reset(self, key: str | None = None) -> None:
        if key is None:
            self._hits.clear()
        else:
            self._hits.pop(key, None)


login_throttle = Throttle()
