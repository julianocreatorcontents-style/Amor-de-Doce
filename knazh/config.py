"""Configuração centralizada. Tudo que depende de dado real da KNAZH vem do ambiente (.env)."""
from __future__ import annotations

import os
import secrets
import tempfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
INSTANCE_DIR = BASE_DIR / "instance"


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "sim", "on"}


def env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _dev_secret_key() -> str:
    """Chave local de desenvolvimento, gerada uma vez e guardada em instance/ (fora do ZIP)."""
    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    path = INSTANCE_DIR / ".dev_secret_key"
    if path.exists():
        return path.read_text().strip()
    key = secrets.token_hex(32)
    path.write_text(key)
    return key


class Config:
    ENVIRONMENT = os.environ.get("KNAZH_ENV", "development").lower()
    IS_PRODUCTION = ENVIRONMENT == "production"

    SECRET_KEY = os.environ.get("SECRET_KEY") or (None if IS_PRODUCTION else _dev_secret_key())
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or f"sqlite:///{INSTANCE_DIR / 'knazh.db'}"
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    # Sessões / cookies
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", IS_PRODUCTION)
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 24 * 30  # 30 dias (carrinho persiste)
    WTF_CSRF_TIME_LIMIT = None  # o token vale enquanto a sessão existir
    MAX_CONTENT_LENGTH = 64 * 1024  # limite do site público: formulários pequenos, sem uploads

    # Painel administrativo e upload de imagens de produto (somente rotas /admin/* aceitam corpo maior)
    ADMIN_URL_PREFIX = "/admin"
    UPLOAD_MAX_FILE_BYTES = env_int("UPLOAD_MAX_FILE_MB", 5) * 1024 * 1024   # por arquivo
    ADMIN_MAX_CONTENT_LENGTH = UPLOAD_MAX_FILE_BYTES + 512 * 1024            # arquivo + campos do formulário
    UPLOAD_MAX_PIXELS = 25_000_000   # largura x altura máximas (bloqueia decompression bombs)
    UPLOAD_MAX_SIDE = 1600           # a imagem salva é reduzida para no máximo 1600 px no maior lado
    UPLOAD_DIR = BASE_DIR / "knazh" / "static" / "uploads" / "products"  # diretório controlado (persistente em produção)
    ADMIN_PER_PAGE = env_int("ADMIN_PER_PAGE", 10)
    # Administrador inicial (provisionado por `flask --app wsgi provision-initial-admin`). A senha vem só da variável de
    # ambiente INITIAL_ADMIN_PASSWORD (ou de um prompt no terminal) e nunca é guardada na configuração.
    INITIAL_ADMIN_EMAIL = os.environ.get("INITIAL_ADMIN_EMAIL", "gaabprc@gmail.com").strip().lower()

    # Marca / site
    SITE_NAME = "KNAZH"
    SITE_TAGLINE = "Sabor em todas as formas."
    SITE_URL = os.environ.get("SITE_URL", "").rstrip("/")  # domínio real quando existir

    # Canais comerciais (vazios = "configuração pendente"; nada é inventado)
    WHATSAPP_NUMBER = os.environ.get("WHATSAPP_NUMBER", "").strip()
    IFOOD_STORE_URL = os.environ.get("IFOOD_STORE_URL", "").strip()
    INSTAGRAM_URL = os.environ.get("INSTAGRAM_URL", "").strip()
    TIKTOK_URL = os.environ.get("TIKTOK_URL", "").strip()
    FACEBOOK_URL = os.environ.get("FACEBOOK_URL", "").strip()
    YOUTUBE_URL = os.environ.get("YOUTUBE_URL", "").strip()
    PUBLIC_CONTACT_EMAIL = os.environ.get("PUBLIC_CONTACT_EMAIL", "").strip()

    # Formulário de contato: as mensagens sempre ficam gravadas no banco; e-mail é opcional.
    CONTACT_EMAIL_TO = os.environ.get("CONTACT_EMAIL_TO", "").strip()
    SMTP_HOST = os.environ.get("SMTP_HOST", "").strip()
    SMTP_PORT = env_int("SMTP_PORT", 587)
    SMTP_USERNAME = os.environ.get("SMTP_USERNAME", "").strip()
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
    SMTP_USE_TLS = env_bool("SMTP_USE_TLS", True)
    SMTP_FROM = os.environ.get("SMTP_FROM", "").strip()

    # Regras da loja
    MAX_QTY_PER_ITEM = env_int("MAX_QTY_PER_ITEM", 20)
    MAX_CART_LINES = env_int("MAX_CART_LINES", 40)
    PRODUCTS_PER_PAGE = env_int("PRODUCTS_PER_PAGE", 12)
    # Faixas de preço do filtro (em centavos); None = sem limite. Ajuste conforme o catálogo real.
    PRICE_RANGES = [
        ("ate-15", "Até R$ 15,00", None, 1500),
        ("15-25", "R$ 15,01 a R$ 25,00", 1501, 2500),
        ("25-40", "R$ 25,01 a R$ 40,00", 2501, 4000),
        ("40-mais", "Acima de R$ 40,00", 4001, None),
    ]


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret-key-not-for-production"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_ENGINE_OPTIONS = {}
    UPLOAD_DIR = Path(tempfile.gettempdir()) / "knazh-test-uploads" / "products"  # nunca a pasta real do projeto
    WTF_CSRF_ENABLED = True
    SESSION_COOKIE_SECURE = False
    WHATSAPP_NUMBER = ""
    IFOOD_STORE_URL = ""
    CONTACT_EMAIL_TO = ""
    SMTP_HOST = ""
