"""Gerenciar administradores, cabeçalho simplificado, ícone de engrenagem e provisionamento do administrador inicial."""
import re

import pytest

from knazh.extensions import db
from knazh.models import Customer
from knazh.services import admin_users as svc
from tests.conftest import csrf_token
from tests.test_admin import PASSWORD, login_as, make_customer


def make_user(email, admin=False, manager=False, name=None):
    c = make_customer(email, admin=admin or manager, name=name or email.split("@")[0].title())
    if manager:
        c.can_manage_admins = True
        db.session.commit()
    return c


def fresh(email):
    db.session.expire_all()
    return db.session.scalar(db.select(Customer).where(Customer.email == email))


def tok(client):
    return csrf_token(client, "/contato")


@pytest.fixture()
def manager_client(app):
    make_user("gestora@example.com", manager=True, name="Gestora KNAZH")
    return login_as(app.test_client(), "gestora@example.com")


@pytest.fixture()
def plain_admin_client(app):
    make_user("admin@example.com", admin=True, name="Admin Comum")
    return login_as(app.test_client(), "admin@example.com")


@pytest.fixture()
def customer_client(app):
    make_user("cliente@example.com", name="Cliente")
    return login_as(app.test_client(), "cliente@example.com")


# ---------------------------------------------------------------- 1, 2, 3: cabeçalho, faixa preta, engrenagem
def test_header_nav_has_exactly_four_links_in_order(client):
    html = client.get("/").get_data(as_text=True)
    nav = re.search(r'<nav class="main-nav".*?</nav>', html, re.S).group(0)
    assert re.findall(r"<a [^>]*>([^<]+)</a>", nav) == ["Início", "Cardápio", "Dúvidas", "Contato"]
    assert "Sobre a KNAZH" not in nav


@pytest.mark.parametrize("path", ["/", "/cardapio", "/produto/cookie", "/duvidas", "/contato", "/carrinho", "/sobre"])
def test_nav_links_work_and_no_demo_banner_anywhere(client, path):
    html = client.get(path).get_data(as_text=True)
    assert client.get(path).status_code == 200
    assert "Catálogo de demonstração" not in html and "demo-notice" not in html
    nav = re.search(r'<nav class="main-nav".*?</nav>', html, re.S).group(0)
    for href in re.findall(r'href="([^"]+)"', nav):
        assert client.get(href).status_code == 200, href
    before_header = html.split("<body>")[1].split('<header class="site-header">')[0]
    assert "<div" not in before_header and "role=\"note\"" not in before_header  # só skip-link e sprite antes do cabeçalho


def test_demo_banner_code_and_config_removed():
    from pathlib import Path
    from knazh.config import Config
    root = Path(__file__).resolve().parent.parent
    assert not hasattr(Config, "CATALOG_IS_DEMO_NOTICE")
    assert "demo-notice" not in (root / "knazh/static/css/base.css").read_text(encoding="utf-8")
    assert "has_demo_products" not in (root / "knazh/services/catalog.py").read_text(encoding="utf-8")


def test_gear_icon_only_for_admins_and_uses_brand_colors(client, manager_client, customer_client):
    admin_html = manager_client.get("/").get_data(as_text=True)
    assert 'icon-btn icon-btn--gear' in admin_html and 'href="#i-gear"' in admin_html and 'aria-label="Painel administrativo"' in admin_html
    sym = re.search(r'<symbol id="i-gear".*?</symbol>', admin_html, re.S).group(0)
    assert "#FF6B1A" in sym and "#3A1608" in sym and "#FFF5E8" in sym
    for c in (client, customer_client):
        assert "icon-btn--gear" not in c.get("/").get_data(as_text=True)


# ---------------------------------------------------------------- 4: quem vê / acessa
def test_visitor_redirected_and_regular_users_blocked_from_admin_management(client, customer_client, plain_admin_client):
    other = make_user("alvo@example.com", name="Alvo")
    paths = ["/admin/administradores", f"/admin/administradores/{other.id}/conceder", f"/admin/administradores/{other.id}/remover"]
    for p in paths:
        r = client.get(p)
        assert r.status_code == 302 and "/conta/entrar" in r.headers["Location"], p
        assert customer_client.get(p).status_code == 403, p
        r = plain_admin_client.get(p)   # administrador SEM a permissão de gestão
        assert r.status_code == 403, p
        assert "Você não gerencia administradores" in r.get_data(as_text=True)
    for who in (customer_client, plain_admin_client):
        for p in paths[1:]:
            assert who.post(p, data={"csrf_token": tok(who)}).status_code == 403
        assert who.post(paths[1], data={"csrf_token": tok(who), "can_manage": "y"}).status_code == 403
    assert not fresh("alvo@example.com").is_admin


def test_plain_admin_does_not_see_the_admin_management_link(plain_admin_client, manager_client):
    assert "Administradores" not in plain_admin_client.get("/admin/produtos").get_data(as_text=True).split('<nav class="admin-nav">')[1].split("</nav>")[0]
    assert "/admin/administradores" in manager_client.get("/admin/produtos").get_data(as_text=True)


def test_manager_sees_users_with_access_levels(manager_client):
    make_user("a@example.com", admin=True, name="Ana Admin")
    make_user("c@example.com", name="Carlos Cliente")
    html = manager_client.get("/admin/administradores").get_data(as_text=True)
    assert "Gerenciar administradores" in html
    assert "Ana Admin" in html and "Carlos Cliente" in html and "Gestora KNAZH" in html
    assert "Gerencia administradores" in html and "Administrador</span>" in html and "Cliente</span>" in html
    assert "Você" in html  # a própria conta não tem botão de ação
    only_admins = manager_client.get("/admin/administradores?status=admins").get_data(as_text=True)
    assert "Ana Admin" in only_admins and "Carlos Cliente" not in only_admins
    found = manager_client.get("/admin/administradores?q=carlos").get_data(as_text=True)
    assert "Carlos Cliente" in found and "Ana Admin" not in found
    assert "Nenhuma conta encontrada" in manager_client.get("/admin/administradores?q=zzzz%25").get_data(as_text=True)


# ---------------------------------------------------------------- conceder / remover
def test_confirmation_pages_never_change_anything(manager_client):
    c = make_user("novo@example.com", name="Novo")
    r = manager_client.get(f"/admin/administradores/{c.id}/conceder")
    assert r.status_code == 200 and "Tornar administrador(a)?" in r.get_data(as_text=True)
    assert not fresh("novo@example.com").is_admin
    a = make_user("velho@example.com", admin=True, name="Velho")
    r = manager_client.get(f"/admin/administradores/{a.id}/remover")
    assert r.status_code == 200 and "Remover acesso administrativo?" in r.get_data(as_text=True)
    assert fresh("velho@example.com").is_admin
    assert manager_client.get("/admin/administradores/99999/conceder").status_code == 404


def test_grant_then_new_admin_can_use_panel_but_not_manage(app, manager_client):
    c = make_user("novo@example.com", name="Novo")
    r = manager_client.post(f"/admin/administradores/{c.id}/conceder", data={"csrf_token": tok(manager_client)}, follow_redirects=True)
    html = r.get_data(as_text=True)
    assert r.status_code == 200 and "Novo agora é administrador(a)." in html
    got = fresh("novo@example.com")
    assert got.is_admin and not got.can_manage_admins
    novo = login_as(app.test_client(), "novo@example.com")
    assert novo.get("/admin/produtos").status_code == 200
    assert novo.get("/admin/administradores").status_code == 403


def test_grant_with_manage_permission(manager_client, app):
    c = make_user("gestor2@example.com", name="Gestor Dois")
    r = manager_client.post(f"/admin/administradores/{c.id}/conceder", data={"csrf_token": tok(manager_client), "can_manage": "y"}, follow_redirects=True)
    assert "permissão de gerenciar administradores" in r.get_data(as_text=True)
    got = fresh("gestor2@example.com")
    assert got.is_admin and got.can_manage_admins
    assert login_as(app.test_client(), "gestor2@example.com").get("/admin/administradores").status_code == 200


def test_grant_twice_is_reported_and_changes_nothing(manager_client):
    a = make_user("velho@example.com", admin=True, name="Velho")
    r = manager_client.post(f"/admin/administradores/{a.id}/conceder", data={"csrf_token": tok(manager_client)}, follow_redirects=True)
    assert "já é administrador(a)" in r.get_data(as_text=True) and "toast--error" in r.get_data(as_text=True)


def test_revoke_removes_access_immediately_and_keeps_the_account(app, manager_client):
    a = make_user("velho@example.com", admin=True, name="Velho")
    velho = login_as(app.test_client(), "velho@example.com")
    assert velho.get("/admin/produtos").status_code == 200
    r = manager_client.post(f"/admin/administradores/{a.id}/remover", data={"csrf_token": tok(manager_client)}, follow_redirects=True)
    assert "foi removido" in r.get_data(as_text=True) and "toast--success" in r.get_data(as_text=True)
    got = fresh("velho@example.com")
    assert got is not None and not got.is_admin and not got.can_manage_admins
    assert velho.get("/admin/produtos").status_code == 403          # a sessão antiga perde o acesso na próxima requisição
    assert velho.get("/conta").status_code == 200                    # e a conta de cliente continua funcionando


def test_nobody_changes_their_own_access(manager_client):
    me = fresh("gestora@example.com")
    r = manager_client.post(f"/admin/administradores/{me.id}/remover", data={"csrf_token": tok(manager_client)}, follow_redirects=True)
    assert "não pode remover o seu próprio acesso" in r.get_data(as_text=True)
    r = manager_client.post(f"/admin/administradores/{me.id}/conceder", data={"csrf_token": tok(manager_client)}, follow_redirects=True)
    assert "próprio acesso" in r.get_data(as_text=True)
    assert fresh("gestora@example.com").is_admin and fresh("gestora@example.com").can_manage_admins


def test_a_manager_can_remove_another_manager_but_never_the_last_one(app, manager_client):
    other = make_user("gestor2@example.com", manager=True, name="Gestor Dois")
    me = fresh("gestora@example.com")
    r = manager_client.post(f"/admin/administradores/{other.id}/remover", data={"csrf_token": tok(manager_client)}, follow_redirects=True)
    assert "foi removido" in r.get_data(as_text=True)
    assert svc.manager_count() == 1
    # o gestor restante não consegue ser removido (nem por ele mesmo, nem por outro gestor recém-criado e removido)
    r2 = manager_client.post(f"/admin/administradores/{me.id}/remover", data={"csrf_token": tok(manager_client)}, follow_redirects=True)
    assert svc.manager_count() == 1 and fresh("gestora@example.com").can_manage_admins


def test_service_refuses_last_manager_even_if_called_directly(app):
    a = make_user("a@example.com", manager=True)
    b = make_user("b@example.com", manager=True)
    assert svc.revoke_admin(a, b.id).ok            # a remove b: sobra 1 gestor
    c = make_user("c@example.com", admin=True)
    out = svc.revoke_admin(a, a.id)                # autoremoção bloqueada
    assert not out.ok and svc.manager_count() == 1
    # um "ator" que NÃO é mais gestor (sessão antiga/forjada) não consegue alterar nada, mesmo chamando o serviço
    ghost = fresh("b@example.com")
    assert not svc.grant_admin(ghost, make_user("d@example.com").id).ok
    assert not svc.revoke_admin(ghost, c.id).ok
    assert fresh("c@example.com").is_admin and not fresh("d@example.com").is_admin


def test_last_manager_guard_on_target_who_is_the_only_manager(app):
    """Gestor A remove gestor B quando A já não é gestor (corrida): nada muda e continua havendo um gestor."""
    a = make_user("a@example.com", manager=True)
    b = make_user("b@example.com", manager=True)
    a_id = a.id
    # simula A ter perdido a permissão entre a checagem e a execução
    db.session.execute(db.update(Customer).where(Customer.id == a_id).values(can_manage_admins=False))
    db.session.commit()
    out = svc.revoke_admin(fresh("a@example.com"), b.id)
    assert not out.ok and fresh("b@example.com").can_manage_admins and svc.manager_count() == 1


def test_forged_requests_cannot_grant_admin(client, customer_client):
    me = fresh("cliente@example.com")
    for c in (client, customer_client):
        c.post(f"/admin/administradores/{me.id}/conceder", data={"csrf_token": tok(c), "can_manage": "y", "is_admin": "1"})
        c.post("/conta/perfil", data={"csrf_token": tok(c), "name": "X Y", "phone": "(41) 99999-0000", "is_admin": "1", "can_manage_admins": "1"})
        c.post("/conta/cadastrar", data={"csrf_token": tok(c), "name": "Esperto", "email": "esperto@example.com", "phone": "(41) 99999-0000",
                                         "password": "senha1234", "confirm": "senha1234", "is_admin": "1", "can_manage_admins": "1"})
    got = fresh("cliente@example.com")
    assert not got.is_admin and not got.can_manage_admins
    sneaky = fresh("esperto@example.com")
    assert sneaky is None or (not sneaky.is_admin and not sneaky.can_manage_admins)
    assert customer_client.get("/admin/produtos?is_admin=1&admin=true").status_code == 403


def test_post_without_csrf_is_rejected(manager_client):
    c = make_user("novo@example.com")
    r = manager_client.post(f"/admin/administradores/{c.id}/conceder", data={})
    assert r.status_code == 400 and not fresh("novo@example.com").is_admin


def test_tampered_next_cannot_redirect_off_site(manager_client):
    c = make_user("novo@example.com")
    r = manager_client.post(f"/admin/administradores/{c.id}/conceder", data={"csrf_token": tok(manager_client), "next": "https://evil.example/x"})
    assert r.status_code == 302 and r.headers["Location"].endswith("/admin/administradores")


def test_management_does_not_break_catalog_account_search_or_cart(manager_client, client, post, fill_cart):
    c = make_user("novo@example.com")
    manager_client.post(f"/admin/administradores/{c.id}/conceder", data={"csrf_token": tok(manager_client)})
    for path in ("/", "/cardapio", "/produto/cookie", "/busca?q=oreo", "/conta/entrar", "/carrinho"):
        assert client.get(path).status_code == 200, path
    fill_cart(("cookie", 2))
    assert "Cookie" in client.get("/carrinho").get_data(as_text=True)
    assert manager_client.get("/admin/produtos").status_code == 200


# ---------------------------------------------------------------- integração painel <-> catálogo público
def test_admin_product_changes_reach_the_public_catalog(manager_client, client):
    from tests.test_admin import create_product, submit, product_data, png
    p = create_product(manager_client, name="Torta KNAZH", price="31,90")
    page = client.get("/cardapio?ordem=recentes").get_data(as_text=True)
    assert "Torta KNAZH" in page and "R$ 31,90" in page.replace("\xa0", " ")
    r = submit(manager_client, f"/admin/produtos/{p.id}/editar", product_data(name="Torta KNAZH", price="35,00", description="Nova descrição"), None)
    assert r.status_code == 302
    detail = client.get("/produto/torta-knazh").get_data(as_text=True)
    assert "35,00" in detail.replace("\xa0", " ") and "Nova descrição" in detail
    manager_client.post(f"/admin/produtos/{p.id}/excluir", data={"csrf_token": tok(manager_client)})
    assert client.get("/produto/torta-knazh").status_code == 404
    assert "Torta KNAZH" not in client.get("/cardapio?ordem=recentes").get_data(as_text=True)


def test_visitors_and_customers_cannot_touch_products(client, customer_client):
    for who in (client, customer_client):
        assert who.get("/admin/produtos/novo").status_code in (302, 403)
        assert who.post("/admin/produtos/1/excluir", data={"csrf_token": tok(who)}).status_code in (302, 403)


# ---------------------------------------------------------------- migração
def test_migration_promotes_existing_admins_to_managers_once(tmp_path):
    from sqlalchemy import create_engine, text
    from knazh.migrations import add_customer_can_manage_admins
    engine = create_engine(f"sqlite:///{tmp_path / 'v2.db'}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE customers (id INTEGER PRIMARY KEY, name VARCHAR(120) NOT NULL, email VARCHAR(254) NOT NULL UNIQUE, "
                          "phone VARCHAR(30) NOT NULL DEFAULT '', password_hash VARCHAR(255) NOT NULL, is_admin BOOLEAN NOT NULL DEFAULT 0, created_at DATETIME NOT NULL)"))
        conn.execute(text("INSERT INTO customers (name, email, password_hash, is_admin, created_at) VALUES ('Dona','dona@e.com','h',1,'2024-01-01 00:00:00'),"
                          "('Cli','cli@e.com','h',0,'2024-01-02 00:00:00')"))
    assert add_customer_can_manage_admins(engine) == "adicionada"
    assert add_customer_can_manage_admins(engine) == "ja-existe"
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT email, is_admin, can_manage_admins, password_hash FROM customers ORDER BY id")).all()
    assert [tuple(r) for r in rows] == [("dona@e.com", 1, 1, "h"), ("cli@e.com", 0, 0, "h")]
    assert add_customer_can_manage_admins(create_engine("sqlite://")) == "sem-tabela"


# ---------------------------------------------------------------- administrador inicial (CLI)
INITIAL = "gaabprc@gmail.com"


def run(app, *args, env=None, input=None):
    return app.test_cli_runner().invoke(args=list(args), env=env or {}, input=input)


def test_initial_admin_email_default_is_the_requested_one(app):
    assert app.config["INITIAL_ADMIN_EMAIL"] == INITIAL


def test_provision_creates_account_from_env_password_and_never_prints_it(app):
    r = run(app, "provision-initial-admin", env={"INITIAL_ADMIN_PASSWORD": "Segredo2026x"})
    assert r.exit_code == 0, r.output
    assert "Segredo2026x" not in r.output
    c = fresh(INITIAL)
    assert c.is_admin and c.can_manage_admins and c.check_password("Segredo2026x") and c.password_hash != "Segredo2026x"
    assert login_as_password(app, INITIAL, "Segredo2026x").get("/admin/administradores").status_code == 200


def login_as_password(app, email, password):
    client = app.test_client()
    r = client.post("/conta/entrar", data={"email": email, "password": password, "csrf_token": csrf_token(client, "/conta/entrar")})
    assert r.status_code == 302
    return client


def test_provision_is_idempotent_and_never_replaces_credentials(app):
    run(app, "provision-initial-admin", env={"INITIAL_ADMIN_PASSWORD": "Segredo2026x"})
    first_hash = fresh(INITIAL).password_hash
    r = run(app, "provision-initial-admin", env={"INITIAL_ADMIN_PASSWORD": "OutraSenha999"})
    assert r.exit_code == 0 and "Nada a fazer" in r.output
    assert db.session.query(Customer).filter_by(email=INITIAL).count() == 1
    assert fresh(INITIAL).password_hash == first_hash and fresh(INITIAL).check_password("Segredo2026x")


def test_provision_existing_account_keeps_password_and_asks_for_confirmation(app):
    c = make_user(INITIAL, name="Dona Existente")
    old_hash = c.password_hash
    r = run(app, "provision-initial-admin", input="n\n")
    assert r.exit_code != 0 and not fresh(INITIAL).is_admin       # recusou: nada muda
    r = run(app, "provision-initial-admin", "--yes")
    assert r.exit_code == 0
    got = fresh(INITIAL)
    assert got.is_admin and got.can_manage_admins and got.password_hash == old_hash and got.name == "Dona Existente"


def test_provision_requires_a_safe_password(app):
    assert run(app, "provision-initial-admin").exit_code != 0                                   # sem senha e sem terminal
    assert fresh(INITIAL) is None
    r = run(app, "provision-initial-admin", env={"INITIAL_ADMIN_PASSWORD": "curta"})
    assert r.exit_code != 0 and "Senha recusada" in r.output and fresh(INITIAL) is None
    r = run(app, "provision-initial-admin", env={"INITIAL_ADMIN_PASSWORD": "somenteletras"})
    assert r.exit_code != 0 and fresh(INITIAL) is None


def test_public_signup_cannot_squat_the_initial_admin_email(app, client):
    r = client.post("/conta/cadastrar", data={"csrf_token": csrf_token(client, "/conta/cadastrar"), "name": "Intruso", "email": INITIAL.upper(),
                                              "phone": "(41) 99999-0000", "password": "senha1234", "confirm": "senha1234"}, follow_redirects=True)
    assert "Não foi possível criar a conta" in r.get_data(as_text=True)
    assert fresh(INITIAL) is None


def test_no_password_or_secret_in_source_tree():
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    for path in list((root / "knazh").rglob("*.py")) + list((root / "knazh").rglob("*.html")) + list((root / "knazh/static").rglob("*.js")):
        text = path.read_text(encoding="utf-8")
        # a senha só é lida do ambiente pelo comando de provisionamento; config.py apenas a menciona num comentário
        assert "INITIAL_ADMIN_PASSWORD" not in text or path.name in ("cli.py", "config.py"), path
        assert not re.search(r"password\s*=\s*[\"'][^\"']{4,}[\"']", text, re.I) or path.name == "cli.py", path
    assert "INITIAL_ADMIN_PASSWORD=\n" in (root / ".env.example").read_text(encoding="utf-8") + "\n"


def test_cli_revoke_refuses_last_manager_and_promote_manager_recovers(app):
    make_user("a@example.com", manager=True)
    make_user("b@example.com", admin=True)
    r = run(app, "revoke-admin", "a@example.com")
    assert r.exit_code != 0 and "única conta que gerencia" in r.output and fresh("a@example.com").can_manage_admins
    assert run(app, "promote-admin", "b@example.com", "--manager").exit_code == 0
    assert fresh("b@example.com").can_manage_admins
    assert run(app, "revoke-admin", "a@example.com").exit_code == 0
    got = fresh("a@example.com")
    assert not got.is_admin and not got.can_manage_admins
