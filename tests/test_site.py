import re
import smtplib

import pytest

from knazh import create_app
from knazh.config import TestConfig
from knazh.extensions import db
from knazh.models import ContactMessage
from knazh.services.channels import get_channels, normalize_whatsapp, safe_https_url
from tests.conftest import pid

MSG = {"name": "João", "email": "joao@example.com", "subject": "Dúvida", "message": "Gostaria de saber mais sobre os doces."}


def internal_links(html):
    return {h.split("#")[0] for h in re.findall(r'href="(/[^"]*)"', html) if not h.startswith("//")}


def test_all_main_pages_load(client):
    for url in ["/", "/cardapio", "/sobre", "/duvidas", "/contato", "/privacidade", "/termos", "/carrinho", "/conta/entrar",
                "/conta/cadastrar", "/robots.txt", "/sitemap.xml", "/site.webmanifest", "/favicon.ico", "/busca?q=brownie"]:
        assert client.get(url).status_code == 200, url


def test_every_internal_link_on_key_pages_resolves(client):
    seen = set()
    for page in ["/", "/cardapio", "/produto/brownie-tradicional", "/sobre", "/duvidas", "/contato", "/carrinho"]:
        for link in internal_links(client.get(page).get_data(as_text=True)):
            if link in seen or link.startswith("/conta/sair"):
                continue
            seen.add(link)
            status = client.get(link).status_code
            assert status < 400, f"{page} -> {link} = {status}"
    assert len(seen) > 20


def test_no_dead_href_hash_or_empty_links(client):
    for page in ["/", "/cardapio", "/produto/cookie", "/sobre", "/duvidas", "/contato", "/carrinho", "/conta/entrar"]:
        html = client.get(page).get_data(as_text=True)
        assert 'href="#"' not in html and 'href=""' not in html and "javascript:" not in html


def test_static_assets_referenced_by_pages_exist(client):
    for page in ["/", "/cardapio", "/produto/cookie", "/sobre", "/contato"]:
        html = client.get(page).get_data(as_text=True)
        for src in set(re.findall(r'(?:src|href)="(/static/[^"?]+)', html)):
            assert client.get(src).status_code == 200, src


def test_security_headers_and_cache(client):
    r = client.get("/")
    assert "default-src 'self'" in r.headers["Content-Security-Policy"]
    assert r.headers["X-Content-Type-Options"] == "nosniff" and r.headers["X-Frame-Options"] == "DENY"
    assert "max-age" in client.get("/static/css/base.css").headers["Cache-Control"]
    assert "style=" not in client.get("/").get_data(as_text=True)  # CSP sem inline style


def test_seo_basics(client):
    html = client.get("/produto/brownie-tradicional").get_data(as_text=True)
    assert "<title>Brownie Tradicional — KNAZH</title>" in html and 'name="description"' in html and 'property="og:title"' in html
    assert "canonical" not in html  # sem domínio configurado, nada é inventado
    assert "Sitemap:" in client.get("/robots.txt").get_data(as_text=True)
    sm = client.get("/sitemap.xml").get_data(as_text=True)
    assert "/produto/brownie-tradicional" in sm and "/cardapio/brownies" in sm


def test_canonical_uses_configured_domain():
    class C(TestConfig):
        SITE_URL = "https://exemplo.test"
    app = create_app(C)
    with app.app_context():
        db.create_all()
        html = app.test_client().get("/sobre").get_data(as_text=True)
    assert 'rel="canonical" href="https://exemplo.test/sobre"' in html


# ---------------- canais não configurados / configurados
def test_unconfigured_channels_are_hidden_not_faked(client):
    for page in ["/", "/cardapio", "/produto/cookie", "/contato", "/duvidas"]:
        html = client.get(page).get_data(as_text=True)
        assert "wa.me" not in html and "ifood.com" not in html and "Pedir no iFood" not in html, page
    assert "Canal ainda não disponível" in client.get("/contato").get_data(as_text=True)


def test_configured_channels_render_real_links():
    class C(TestConfig):
        WHATSAPP_NUMBER = "(41) 99999-0000"
        IFOOD_STORE_URL = "https://www.ifood.com.br/delivery/loja-teste"
        INSTAGRAM_URL = "https://instagram.com/teste"
    app = create_app(C)
    with app.app_context():
        db.create_all()
        from knazh.demo_data import seed_demo
        seed_demo()
        c = app.test_client()
        html = c.get("/produto/cookie").get_data(as_text=True)
        assert "https://wa.me/5541999990000?text=" in html and "https://www.ifood.com.br/delivery/loja-teste" in html
        assert "(41) 99999-0000" in c.get("/contato").get_data(as_text=True)
        assert "instagram.com/teste" in c.get("/").get_data(as_text=True)


def test_channel_validation():
    assert normalize_whatsapp("+55 (41) 99620-6276") == "5541996206276"
    assert normalize_whatsapp("41996206276") == "5541996206276"
    assert normalize_whatsapp("123") is None and normalize_whatsapp("") is None and normalize_whatsapp(None) is None
    assert safe_https_url("javascript:alert(1)") is None and safe_https_url("http://x.com") is None
    assert safe_https_url("https://evil.com\" onclick=\"x") is None and safe_https_url("") is None
    assert safe_https_url("https://www.ifood.com.br/x") == "https://www.ifood.com.br/x"


def test_whatsapp_cart_message_contains_items(app, client, post):
    class C(TestConfig):
        WHATSAPP_NUMBER = "41999990000"
    app2 = create_app(C)
    with app2.app_context():
        db.create_all()
        from knazh.demo_data import seed_demo
        seed_demo()
        c = app2.test_client()
        tok = re.search(r'csrf-token" content="([^"]+)"', c.get("/").get_data(as_text=True)).group(1)
        c.post("/carrinho/adicionar", data={"csrf_token": tok, "product_id": pid("cookie"), "quantity": 2})
        html = c.get("/carrinho").get_data(as_text=True)
        assert "wa.me/5541999990000?text=Ol%C3%A1%2C%20KNAZH" in html and "2x%20Cookie" in html


# ---------------- contato
def test_contact_validation_errors(client, post):
    for over in [{"name": ""}, {"email": "x"}, {"subject": ""}, {"message": "curta"}]:
        r = post("/contato", {**MSG, **over})
        assert r.status_code == 200 and "Confira os campos" in r.get_data(as_text=True)
    assert db.session.query(ContactMessage).count() == 0


def test_contact_message_is_stored_and_email_status_is_truthful(client, post):
    r = post("/contato", MSG)
    assert r.status_code == 302
    m = db.session.scalar(db.select(ContactMessage))
    assert m.email == "joao@example.com" and m.email_status == "nao_configurado"
    assert "Mensagem registrada" in client.get(r.headers["Location"]).get_data(as_text=True)


def test_contact_honeypot_discards_bots(client, post):
    post("/contato", {**MSG, "website": "http://spam"})
    assert db.session.query(ContactMessage).count() == 0


def test_contact_email_failure_is_recorded(monkeypatch):
    class C(TestConfig):
        SMTP_HOST, CONTACT_EMAIL_TO, SMTP_FROM = "smtp.invalid", "dono@example.com", "site@example.com"
    def boom(*a, **k):
        raise OSError("sem rede")
    monkeypatch.setattr(smtplib, "SMTP", boom)
    app = create_app(C)
    with app.app_context():
        db.create_all()
        c = app.test_client()
        tok = re.search(r'csrf-token" content="([^"]+)"', c.get("/contato").get_data(as_text=True)).group(1)
        assert c.post("/contato", data={**MSG, "csrf_token": tok}).status_code == 302
        assert db.session.scalar(db.select(ContactMessage.email_status)) == "falhou"


def test_contact_email_sent_when_smtp_works(monkeypatch):
    sent = {}
    class FakeSMTP:
        def __init__(self, host, port, timeout=None): sent["host"] = host
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self): sent["tls"] = True
        def login(self, u, p): sent["login"] = u
        def send_message(self, msg): sent["to"] = msg["To"]; sent["subject"] = msg["Subject"]
    class C(TestConfig):
        SMTP_HOST, CONTACT_EMAIL_TO, SMTP_FROM, SMTP_USERNAME, SMTP_PASSWORD = "smtp.test", "dono@example.com", "site@example.com", "u", "p"
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    app = create_app(C)
    with app.app_context():
        db.create_all()
        c = app.test_client()
        tok = re.search(r'csrf-token" content="([^"]+)"', c.get("/contato").get_data(as_text=True)).group(1)
        c.post("/contato", data={**MSG, "csrf_token": tok})
        assert db.session.scalar(db.select(ContactMessage.email_status)) == "enviado"
    assert sent["to"] == "dono@example.com" and sent["tls"] and "[Site KNAZH]" in sent["subject"]


# ---------------- erros e configuração
def test_404_page_is_branded_and_safe(client):
    r = client.get("/nao-existe")
    html = r.get_data(as_text=True)
    assert r.status_code == 404 and "Essa página não existe" in html and "Voltar ao início" in html and "Traceback" not in html


def test_unexpected_error_does_not_leak_details(app):
    @app.get("/_boom")
    def boom():
        raise RuntimeError("segredo-interno /home/x SELECT * FROM users")
    app.config["PROPAGATE_EXCEPTIONS"] = False
    r = app.test_client().get("/_boom")
    html = r.get_data(as_text=True)
    assert r.status_code == 500 and "Algo deu errado" in html
    assert "segredo-interno" not in html and "SELECT" not in html and "/home/x" not in html


def test_method_not_allowed_and_bad_csrf_pages(client):
    assert client.get("/carrinho/adicionar").status_code == 405
    assert client.post("/contato", data=MSG).status_code == 400


def test_faq_pending_answers_are_marked_not_invented(client):
    html = client.get("/duvidas").get_data(as_text=True)
    assert "Informação pendente" in html and "ainda não foi definida pela KNAZH" in html


def test_legal_pages_flagged_as_provisional(client):
    for url in ["/privacidade", "/termos"]:
        assert "pendente de revisão" in client.get(url).get_data(as_text=True)


def test_production_requires_secret_key(monkeypatch):
    class Prod(TestConfig):
        SECRET_KEY = None
    with pytest.raises(RuntimeError):
        create_app(Prod)


def test_startup_is_not_destructive(tmp_path):
    uri = f"sqlite:///{tmp_path/'t.db'}"
    class C(TestConfig):
        SQLALCHEMY_DATABASE_URI = uri
    app = create_app(C)
    with app.app_context():
        from knazh.demo_data import seed_demo
        seed_demo()
        n = db.session.execute(db.text("select count(*) from products")).scalar()
    app2 = create_app(C)  # segunda inicialização não apaga dados
    with app2.app_context():
        assert db.session.execute(db.text("select count(*) from products")).scalar() == n == 17
