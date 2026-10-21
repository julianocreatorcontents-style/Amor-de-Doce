"""Site público KNAZH — fábrica da aplicação Flask."""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from flask import Flask, Request, current_app, g, render_template, request  # noqa: E402
from flask_wtf.csrf import CSRFError  # noqa: E402
from sqlalchemy.exc import SQLAlchemyError  # noqa: E402

from .auth import load_customer  # noqa: E402
from .config import Config  # noqa: E402
from .extensions import csrf, db  # noqa: E402
from .services import cart as cart_service  # noqa: E402
from .services.catalog import active_categories  # noqa: E402
from .services.channels import get_channels  # noqa: E402
from .services.money import format_brl  # noqa: E402

CSP = ("default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; font-src 'self'; "
       "connect-src 'self'; form-action 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'")


class KnazhRequest(Request):
    """Limite de corpo por rota: o site público segue com MAX_CONTENT_LENGTH pequeno (64 KiB); somente as rotas
    do painel administrativo (/admin/...) aceitam o tamanho maior necessário ao envio de uma foto."""

    @property
    def max_content_length(self):
        cfg = current_app.config
        prefix = cfg.get("ADMIN_URL_PREFIX", "/admin")
        if self.path == prefix or self.path.startswith(prefix + "/"):
            return cfg.get("ADMIN_MAX_CONTENT_LENGTH") or cfg.get("MAX_CONTENT_LENGTH")
        return cfg.get("MAX_CONTENT_LENGTH")

    @max_content_length.setter
    def max_content_length(self, _value):  # o limite vem sempre da configuração
        pass


def create_app(config_object=None) -> Flask:
    app = Flask(__name__, instance_relative_config=False)
    app.request_class = KnazhRequest
    app.config.from_object(config_object or Config)
    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("Defina SECRET_KEY no ambiente (obrigatório em produção). Veja .env.example.")
    Path(app.root_path).parent.joinpath("instance").mkdir(exist_ok=True)

    db.init_app(app)
    csrf.init_app(app)

    from .blueprints import account, admin, cart, catalog, checkout, main
    for bp in (main.bp, catalog.bp, cart.bp, checkout.bp, account.bp, admin.bp):
        app.register_blueprint(bp)

    from .cli import register_cli
    register_cli(app)

    app.jinja_env.filters["brl"] = format_brl
    app.jinja_env.trim_blocks = True
    app.jinja_env.lstrip_blocks = True

    @app.before_request
    def _before():
        # Flask-WTF guarda o token em `g`; descarta para não reaproveitar entre requisições
        # quando existe um contexto de aplicação externo ativo (testes, shell).
        g.pop("csrf_token", None)
        load_customer()

    @app.context_processor
    def _inject():
        endpoint = request.endpoint or ""
        try:
            cats = active_categories()
        except SQLAlchemyError:
            db.session.rollback()
            cats = []
        return {
            "cart_count": cart_service.count(),
            "channels": get_channels(),
            "nav_categories": cats,
            "current_year": datetime.now().year,
            "customer": g.get("customer"),
            "site_url": app.config["SITE_URL"] or request.url_root.rstrip("/"),
            "active_nav": _active_nav(endpoint),
        }

    @app.after_request
    def _headers(resp):
        resp.headers.setdefault("Content-Security-Policy", CSP)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if app.config["IS_PRODUCTION"]:
            resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
        if request.endpoint == "static":
            resp.headers["Cache-Control"] = "public, max-age=604800"
        elif request.method == "GET" and "Cache-Control" not in resp.headers:
            resp.headers["Cache-Control"] = "private, no-cache"
        return resp

    _register_errors(app)

    if app.config.get("AUTO_CREATE_TABLES", True):
        with app.app_context():
            db.create_all()  # não destrutivo: só cria o que ainda não existe
    logging.getLogger(__name__).info("KNAZH pronta (%s)", app.config["ENVIRONMENT"])
    return app


def _active_nav(endpoint: str) -> str:
    if endpoint == "main.home":
        return "inicio"
    if endpoint.startswith("catalog."):
        return "cardapio"
    return {"main.about": "sobre", "main.faq": "duvidas", "main.contact": "contato"}.get(endpoint, "")


def _register_errors(app: Flask) -> None:
    def respond(status: int, title: str, text: str, mascot: str, template: str = "pages/error.html"):
        return render_template(template, status=status, title=title, text=text, mascot=mascot), status

    @app.errorhandler(404)
    def not_found(_e):
        return respond(404, "Essa página não existe ou foi removida.", "Mas não se preocupe: você pode voltar para o início e continuar aproveitando nossos doces!", "mascote-404.png", "pages/404.html")

    @app.errorhandler(403)
    def forbidden(_e):
        if request.blueprint == "admin" and g.get("customer") is not None and g.customer.is_admin:
            return respond(403, "Você não gerencia administradores.", "Esta área é só de quem tem a permissão de gerenciar administradores. Peça a uma dessas pessoas se precisar de acesso.", "mascote-ops.png")
        if request.blueprint == "admin":
            return respond(403, "Área restrita a administradores.", "Sua conta não tem permissão para acessar o painel administrativo. Se você deveria ter acesso, fale com quem cuida da loja.", "mascote-ops.png")
        return respond(403, "Você não tem acesso a esta página.", "Entre na conta certa ou volte ao início.", "mascote-ops.png")

    @app.errorhandler(CSRFError)
    def csrf_error(_e):
        return respond(400, "Não foi possível validar o envio.", "A página ficou aberta por muito tempo ou os dados são inválidos. Volte, recarregue a página e tente novamente.", "mascote-ops.png")

    @app.errorhandler(400)
    def bad_request(_e):
        return respond(400, "Dados inválidos.", "Não conseguimos entender essa solicitação. Volte e tente novamente.", "mascote-ops.png")

    @app.errorhandler(405)
    def not_allowed(_e):
        return respond(405, "Ação não permitida.", "Essa ação não está disponível por aqui. Volte ao início.", "mascote-ops.png")

    @app.errorhandler(413)
    def too_large(_e):
        if request.path.startswith(app.config["ADMIN_URL_PREFIX"] + "/"):
            limit = app.config["UPLOAD_MAX_FILE_BYTES"] / (1024 * 1024)
            return respond(413, "Envio grande demais.", f"A imagem (ou o envio) ultrapassa o limite de {limit:g} MiB. Escolha uma foto menor e tente novamente.", "mascote-ops.png")
        return respond(413, "Envio grande demais.", "Reduza o tamanho do texto e tente novamente.", "mascote-ops.png")

    @app.errorhandler(Exception)
    def unexpected(error):
        from werkzeug.exceptions import HTTPException
        if isinstance(error, HTTPException):
            return respond(error.code or 500, error.name, "Algo não saiu como esperado.", "mascote-ops.png")
        app.logger.exception("Erro inesperado")  # detalhes só no log do servidor
        db.session.rollback()
        return respond(500, "Ops! Algo deu errado.", "Calma! Já volta. Tente novamente em alguns instantes.", "mascote-ops.png")
