"""Painel administrativo: autorização, CRUD, preço, filtros, upload seguro, exclusão, CLI e migração."""
import io
import re
from pathlib import Path

import pytest
from PIL import Image

from knazh.extensions import db
from knazh.models import Category, Customer, Favorite, Order, OrderItem, Product
from knazh.services.money import parse_brl_to_cents
from tests.conftest import csrf_token

PASSWORD = "senha1234"
MANAGED = re.compile(r"^uploads/products/[0-9a-f]{32}\.(jpg|png)$")


# ---------------------------------------------------------------- helpers
def make_customer(email, admin=False, name="Pessoa Teste"):
    c = Customer(name=name, email=email, phone="(41) 99999-0000")
    c.set_password(PASSWORD)
    if admin:
        c.is_admin = True
    db.session.add(c)
    db.session.commit()
    return c


def login_as(client, email):
    token = csrf_token(client, "/conta/entrar")
    r = client.post("/conta/entrar", data={"email": email, "password": PASSWORD, "csrf_token": token})
    assert r.status_code == 302
    return client


@pytest.fixture()
def admin_client(app):
    make_customer("admin@example.com", admin=True, name="Dona KNAZH")
    return login_as(app.test_client(), "admin@example.com")


@pytest.fixture()
def user_client(app):
    make_customer("cliente@example.com")
    return login_as(app.test_client(), "cliente@example.com")


def token(client):
    return csrf_token(client, "/contato")


def png(size=(120, 90), color=(200, 100, 50), mode="RGB"):
    buf = io.BytesIO()
    Image.new(mode, size, color).save(buf, format="PNG")
    return buf.getvalue()


def product_data(**over):
    cat = db.session.scalar(db.select(Category).where(Category.slug == "brownies"))
    data = {"name": "Brownie de Teste", "description": "Descrição curta do teste", "details": "Mais detalhes",
            "category_id": str(cat.id), "price": "18,50", "image_alt": "Foto do brownie", "is_available": "y"}
    data.update(over)
    return data


def submit(client, path, data, image=None, filename="foto.png", **kw):
    data = dict(data)
    data["csrf_token"] = token(client)
    if image is not None:
        data["image"] = (io.BytesIO(image), filename)
    return client.post(path, data=data, content_type="multipart/form-data", **kw)


def create_product(client, image=None, **over):
    r = submit(client, "/admin/produtos/novo", product_data(**over), png() if image is None else image)
    assert r.status_code == 302, r.get_data(as_text=True)[:500]
    return db.session.scalar(db.select(Product).where(Product.name == product_data(**over)["name"]))


def upload_dir(app):
    return Path(app.config["UPLOAD_DIR"])


def uploaded_files(app):
    d = upload_dir(app)
    return sorted(p.name for p in d.iterdir()) if d.exists() else []


def get_product(slug):
    return db.session.scalar(db.select(Product).where(Product.slug == slug))


# ---------------------------------------------------------------- 1 e 2: autorização
ADMIN_GET = ["/admin/", "/admin/produtos", "/admin/produtos/novo", "/admin/produtos/1/editar", "/admin/produtos/1/excluir"]


def test_visitor_is_sent_to_login_for_every_admin_page(client):
    for path in ADMIN_GET:
        r = client.get(path)
        assert r.status_code == 302, path
        assert "/conta/entrar" in r.headers["Location"] and "admin" in r.headers["Location"], path


def test_every_admin_route_is_protected_for_visitors_and_regular_customers(app, client, user_client):
    adapter = app.url_map.bind("localhost")
    rules = [r for r in app.url_map.iter_rules() if r.endpoint.startswith("admin.")]
    assert len(rules) >= 7  # index, lista, novo, editar, disponibilidade, excluir (GET e POST)
    before = db.session.query(Product).count()
    pid = db.session.scalar(db.select(Product.id).limit(1))
    for rule in rules:
        values = {"product_id": pid} if "product_id" in rule.arguments else {}
        if "user_id" in rule.arguments:
            values = {"user_id": 1}
        for method in rule.methods - {"HEAD", "OPTIONS"}:
            url = adapter.build(rule.endpoint, values, method=method)
            for who, expected in ((client, 302), (user_client, 403)):
                if method == "GET":
                    r = who.get(url)
                else:
                    r = who.post(url, data={"csrf_token": token(who)})
                assert r.status_code == expected, (who is client, method, url, r.status_code)
    assert db.session.query(Product).count() == before and db.session.get(Product, pid) is not None


def test_visitor_post_without_csrf_is_rejected(client):
    pid = db.session.scalar(db.select(Product.id).limit(1))
    r = client.post(f"/admin/produtos/{pid}/excluir")
    assert r.status_code in (302, 400) and db.session.get(Product, pid) is not None


def test_regular_customer_gets_branded_403_and_cannot_post(user_client):
    for path in ADMIN_GET:
        r = user_client.get(path)
        assert r.status_code == 403, path
        html = r.get_data(as_text=True)
        assert "Área restrita a administradores" in html and "KNAZH" in html
    pid = db.session.scalar(db.select(Product.id).where(Product.slug == "cookie"))
    was = db.session.get(Product, pid).is_available
    assert submit(user_client, "/admin/produtos/novo", product_data(), png()).status_code == 403
    assert submit(user_client, f"/admin/produtos/{pid}/editar", product_data(name="Hackeado"), png()).status_code == 403
    assert user_client.post(f"/admin/produtos/{pid}/disponibilidade", data={"csrf_token": token(user_client)}).status_code == 403
    assert user_client.post(f"/admin/produtos/{pid}/excluir", data={"csrf_token": token(user_client)}).status_code == 403
    db.session.expire_all()
    p = db.session.get(Product, pid)
    assert p is not None and p.name == "Cookie" and p.is_available == was
    assert db.session.scalar(db.select(Product).where(Product.name == "Brownie de Teste")) is None


def test_privilege_cannot_be_granted_by_url_form_or_cookie(app, user_client):
    assert user_client.get("/admin/produtos?is_admin=1&admin=true").status_code == 403
    user_client.set_cookie("is_admin", "1")
    user_client.set_cookie("admin", "true")
    assert user_client.get("/admin/produtos").status_code == 403
    r = user_client.post("/conta/perfil", data={"name": "Fulano", "phone": "(41) 99999-0000", "is_admin": "y",
                                                  "csrf_token": csrf_token(user_client, "/conta/perfil")})
    assert r.status_code in (200, 302)
    db.session.expire_all()
    assert db.session.scalar(db.select(Customer).where(Customer.email == "cliente@example.com")).is_admin is False


def test_admin_loses_access_when_revoked_in_database(app, admin_client):
    assert admin_client.get("/admin/produtos").status_code == 200
    c = db.session.scalar(db.select(Customer).where(Customer.email == "admin@example.com"))
    c.is_admin = False
    db.session.commit()
    assert admin_client.get("/admin/produtos").status_code == 403  # a conta é relida do banco a cada requisição


def test_login_with_next_returns_admin_to_panel(app, client):
    make_customer("admin@example.com", admin=True)
    r = client.get("/admin/produtos")
    assert "/conta/entrar" in r.headers["Location"]
    tok = csrf_token(client, "/conta/entrar")
    r = client.post("/conta/entrar", data={"email": "admin@example.com", "password": PASSWORD, "next": "/admin/produtos", "csrf_token": tok})
    assert r.status_code == 302 and r.headers["Location"].endswith("/admin/produtos")


def test_admin_link_only_for_admins(app, client, user_client, admin_client):
    assert "/admin/produtos" not in client.get("/").get_data(as_text=True)
    assert "/admin/produtos" not in user_client.get("/").get_data(as_text=True)
    assert "Painel administrativo" in admin_client.get("/").get_data(as_text=True)


# ---------------------------------------------------------------- 10: contas públicas
def test_public_registration_never_creates_admin(client):
    tok = csrf_token(client, "/conta/cadastrar")
    r = client.post("/conta/cadastrar", data={"name": "Ana Souza", "email": "ana@example.com", "phone": "(41) 98888-7777",
                                              "password": PASSWORD, "confirm": PASSWORD, "is_admin": "y", "admin": "1", "csrf_token": tok})
    assert r.status_code == 302
    c = db.session.scalar(db.select(Customer).where(Customer.email == "ana@example.com"))
    assert c.is_admin is False
    assert client.get("/admin/produtos").status_code == 403


def test_new_customers_default_to_non_admin(app):
    c = Customer(name="Zé", email="ze@example.com", phone="(41) 99999-0000", password_hash="x")
    db.session.add(c)
    db.session.commit()
    assert c.is_admin is False
    assert Customer.__table__.c.is_admin.server_default is not None


# ---------------------------------------------------------------- 3: listar, cadastrar, editar
def test_admin_lists_products_with_real_data(admin_client):
    r = admin_client.get("/admin/produtos")
    html = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "Olá, Admin!" in html and "Acesso restrito • Administrador" in html and "Novo produto" in html
    assert "Bolo de Chocolate" in html and "Dona KNAZH" in html and "mascote-feliz.png" in html  # 1ª página (ordem alfabética)
    total = db.session.query(Product).count()
    assert f"<strong>{total}</strong><span>Produtos cadastrados</span>" in html
    assert "noindex" in html
    for fake in (">Pedidos<", ">Clientes<", ">Configurações<"):
        assert fake not in html  # sem links/telas falsas


def test_admin_creates_product_with_image(app, admin_client):
    r = submit(admin_client, "/admin/produtos/novo", product_data(is_featured="y"), png(), follow_redirects=True)
    html = r.get_data(as_text=True)
    assert r.status_code == 200 and "foi cadastrado" in html
    p = get_product("brownie-de-teste")
    assert p is not None and p.price_cents == 1850 and p.is_available and p.is_featured and not p.is_demo
    assert MANAGED.match(p.image) and (upload_dir(app) / p.image.rsplit("/", 1)[1]).is_file()
    assert p.category.slug == "brownies" and "brownie de teste" in p.search_text
    shop = admin_client.get("/produto/brownie-de-teste")
    assert shop.status_code == 200 and p.image in shop.get_data(as_text=True)
    assert "Brownie de Teste" in admin_client.get("/cardapio?ordem=recentes").get_data(as_text=True)


def test_create_requires_photo_and_valid_fields(app, admin_client):
    before = db.session.query(Product).count()
    r = submit(admin_client, "/admin/produtos/novo", product_data(), None)
    assert r.status_code == 200 and "Escolha uma foto do produto" in r.get_data(as_text=True)
    for over in ({"name": ""}, {"name": "A"}, {"name": "x" * 121}, {"description": ""}, {"description": "y" * 401},
                 {"category_id": "99999"}, {"category_id": ""}, {"category_id": "abc"}, {"image_alt": "z" * 201}):
        r = submit(admin_client, "/admin/produtos/novo", product_data(**over), png())
        assert r.status_code == 200, over
    assert db.session.query(Product).count() == before and uploaded_files(app) == []


def test_slug_is_unique_and_safe(admin_client):
    a = create_product(admin_client, name="Torta de Limão")
    submit(admin_client, "/admin/produtos/novo", product_data(name="Torta de Limão"), png())
    slugs = [p.slug for p in db.session.scalars(db.select(Product).where(Product.name == "Torta de Limão"))]
    assert a.slug == "torta-de-limao" and sorted(slugs) == ["torta-de-limao", "torta-de-limao-2"]
    p = create_product(admin_client, name="<b>Olá</b> ../ Bolo & Cia!")
    assert re.fullmatch(r"[a-z0-9-]+", p.slug)


def test_admin_edits_product_and_keeps_slug_and_image(app, admin_client):
    p = create_product(admin_client)
    old_image, slug = p.image, p.slug
    r = submit(admin_client, f"/admin/produtos/{p.id}/editar", product_data(name="Nome Novo", price="20", is_available=""), None, follow_redirects=True)
    assert r.status_code == 200 and "foi atualizado" in r.get_data(as_text=True)
    db.session.expire_all()
    p = db.session.get(Product, p.id)
    assert p.name == "Nome Novo" and p.price_cents == 2000 and p.is_available is False
    assert p.slug == slug and p.image == old_image  # 6: sem nova imagem, preserva a atual
    assert (upload_dir(app) / old_image.rsplit("/", 1)[1]).is_file()
    assert admin_client.get(f"/produto/{slug}").status_code == 200  # URL pública não quebrou


def test_edit_form_shows_current_image_and_values(admin_client):
    pid = db.session.scalar(db.select(Product.id).where(Product.slug == "cookie"))
    html = admin_client.get(f"/admin/produtos/{pid}/editar").get_data(as_text=True)
    assert "img/produtos/cookie.svg" in html and 'value="Cookie"' in html and "12,00" in html
    assert "Salvar alterações" in html and "Cancelar" in html and "Trocar foto" in html
    assert admin_client.get("/admin/produtos/999999/editar").status_code == 404


def test_editing_demo_product_detaches_it_from_demo_seed(admin_client):
    pid = db.session.scalar(db.select(Product.id).where(Product.slug == "cookie"))
    submit(admin_client, f"/admin/produtos/{pid}/editar", product_data(name="Cookie", price="13"), None)
    db.session.expire_all()
    assert db.session.get(Product, pid).is_demo is False


# ---------------------------------------------------------------- 4: preço
@pytest.mark.parametrize("text,cents", [("18", 1800), ("18,5", 1850), ("18,50", 1850), ("R$ 18,00", 1800), ("1.234,56", 123456), ("18.50", 1850), ("0,01", 1)])
def test_price_parsing_to_cents(text, cents):
    assert parse_brl_to_cents(text) == cents


@pytest.mark.parametrize("bad", ["", "0", "0,00", "-5", "abc", "18,555", "1,2,3", "R$", "10.000.000"])
def test_price_parsing_rejects_invalid(bad):
    with pytest.raises(ValueError):
        parse_brl_to_cents(bad)


def test_price_conversion_and_rejection_in_form(app, admin_client):
    p = create_product(admin_client, price="1.234,56", name="Caro")
    assert p.price_cents == 123456
    before = db.session.query(Product).count()
    for bad in ("", "0", "-3", "abc", "18,555", "12e3"):
        r = submit(admin_client, "/admin/produtos/novo", product_data(price=bad, name="Preço Ruim"), png())
        assert r.status_code == 200, bad
    assert db.session.query(Product).count() == before


# ---------------------------------------------------------------- 5: busca, filtros, status, paginação
def test_search_filters_and_status(admin_client):
    def page(qs):
        r = admin_client.get("/admin/produtos" + qs)
        assert r.status_code == 200
        return r.get_data(as_text=True)

    html = page("?q=oreo")
    assert "Brownie com Oreo" in html and "Cookie" not in html
    assert "Mousse de Maracujá" in page("?q=maracuja")  # sem acento
    sob = db.session.scalar(db.select(Category.id).where(Category.slug == "sobremesas"))
    html = page(f"?categoria={sob}")
    assert "Mousse de Morango" in html and "Cookie" not in html
    html = page("?status=indisponiveis")
    assert "Brownie de Pistache" in html and "Cookie" not in html
    assert "Cookie" in page("?status=disponiveis&q=cookie")
    assert "Nenhum produto encontrado" in page("?status=disponiveis&q=pistache")
    assert "Nenhum produto encontrado" in page("?q=zzzinexistente")
    assert page("?categoria=abc&status=zzz&pagina=x&q=" + "a" * 500)  # parâmetros inválidos não quebram


def test_pagination(app, admin_client):
    total = db.session.query(Product).count()
    assert total > app.config["ADMIN_PER_PAGE"]
    html = admin_client.get("/admin/produtos").get_data(as_text=True)
    assert "Página 1 de 2" in html and "Próxima" in html
    html2 = admin_client.get("/admin/produtos?pagina=2").get_data(as_text=True)
    assert "Página 2 de 2" in html2 and "Anterior" in html2
    assert admin_client.get("/admin/produtos?pagina=999").status_code == 200


def test_toggle_availability(admin_client):
    pid = db.session.scalar(db.select(Product.id).where(Product.slug == "cookie"))
    r = admin_client.post(f"/admin/produtos/{pid}/disponibilidade", data={"csrf_token": token(admin_client), "next": "/admin/produtos?status=todos"}, follow_redirects=True)
    assert "agora está indisponível" in r.get_data(as_text=True)
    db.session.expire_all()
    assert db.session.get(Product, pid).is_available is False
    assert admin_client.get(f"/admin/produtos/{pid}/disponibilidade").status_code == 405  # só POST
    # next externo é ignorado
    r = admin_client.post(f"/admin/produtos/{pid}/disponibilidade", data={"csrf_token": token(admin_client), "next": "https://evil.example/"})
    assert r.status_code == 302 and "evil.example" not in r.headers["Location"]


# ---------------------------------------------------------------- 7 e 8: upload
def test_form_has_local_preview_hooks_and_multipart(admin_client):
    html = admin_client.get("/admin/produtos/novo").get_data(as_text=True)
    assert 'enctype="multipart/form-data"' in html and "data-image-preview" in html and "data-image-input" in html
    assert 'accept="image/jpeg,image/png,image/webp"' in html and "admin.js" in html
    assert "style=" not in html and "<script>" not in html  # CSP: sem inline


def test_upload_is_reprocessed_and_named_safely(app, admin_client):
    p = create_product(admin_client, image=png((3000, 2000)), name="Grande")
    f = upload_dir(app) / p.image.rsplit("/", 1)[1]
    assert MANAGED.match(p.image) and f.is_file()
    with Image.open(f) as im:
        assert max(im.size) <= app.config["UPLOAD_MAX_SIDE"] and im.format in ("JPEG", "PNG")


def test_filename_from_browser_never_becomes_path(app, admin_client):
    r = submit(admin_client, "/admin/produtos/novo", product_data(name="Traversal"), png(), filename="../../../evil.png")
    assert r.status_code == 302
    p = get_product("traversal")
    assert MANAGED.match(p.image) and ".." not in p.image and "evil" not in p.image
    assert len(uploaded_files(app)) == 1
    assert not list(Path(app.static_folder).rglob("evil*"))


def test_invalid_uploads_are_refused_without_leaks(app, admin_client):
    cases = [
        (b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>', "x.svg", "Formato não permitido"),
        (b'<svg xmlns="http://www.w3.org/2000/svg"></svg>', "x.png", "Arquivo inválido"),     # extensão falsificada
        (b"isto nao e uma imagem", "x.jpg", "Arquivo inválido"),
        (b"", "x.png", None),
    ]
    buf = io.BytesIO()
    Image.new("RGB", (20, 20)).save(buf, format="GIF")
    cases.append((buf.getvalue(), "x.gif", "Formato não permitido"))
    cases.append((png()[:60], "x.png", None))  # truncado
    before = db.session.query(Product).count()
    for content, name, msg in cases:
        r = submit(admin_client, "/admin/produtos/novo", product_data(name="Invalido"), content, filename=name)
        html = r.get_data(as_text=True)
        assert r.status_code == 200, name
        assert "Traceback" not in html and "/home/" not in html and str(upload_dir(app)) not in html  # sem detalhes internos
        if msg:
            assert msg in html, (name, msg)
    assert db.session.query(Product).count() == before and uploaded_files(app) == []


def test_oversized_upload_is_refused(app, admin_client):
    limit = app.config["UPLOAD_MAX_FILE_BYTES"]
    # acima do limite de arquivo, mas ainda dentro do limite da requisição: recusado pelo servidor com mensagem clara
    r = submit(admin_client, "/admin/produtos/novo", product_data(name="Grande Demais"), b"\x89PNG" + b"0" * (limit + 100_000))
    assert r.status_code == 200 and "grande demais" in r.get_data(as_text=True)
    # acima do limite da requisição: 413 amigável, sem traceback
    r = submit(admin_client, "/admin/produtos/novo", product_data(name="Enorme"), b"0" * (limit + 2 * 1024 * 1024))
    assert r.status_code == 413
    html = r.get_data(as_text=True)
    assert "MiB" in html and "Traceback" not in html
    assert db.session.scalar(db.select(Product).where(Product.name.in_(["Grande Demais", "Enorme"]))) is None
    assert uploaded_files(app) == []


def test_public_site_keeps_small_request_limit(client):
    tok = csrf_token(client, "/contato")
    r = client.post("/contato", data={"csrf_token": tok, "message": "x" * (80 * 1024)})
    assert r.status_code == 413


def test_replacing_image_removes_only_managed_old_file(app, admin_client):
    p = create_product(admin_client, name="Troca Foto")
    first = p.image
    r = submit(admin_client, f"/admin/produtos/{p.id}/editar", product_data(name="Troca Foto"), png(color=(10, 200, 10)))
    assert r.status_code == 302
    db.session.expire_all()
    p = db.session.get(Product, p.id)
    assert p.image != first and MANAGED.match(p.image)
    files = uploaded_files(app)
    assert files == [p.image.rsplit("/", 1)[1]]  # a antiga saiu, a nova ficou, nada órfão

    # imagem original do projeto (SVG) nunca é apagada
    svg = Path(app.static_folder) / "img/produtos/cookie.svg"
    cid = db.session.scalar(db.select(Product.id).where(Product.slug == "cookie"))
    assert svg.is_file()
    submit(admin_client, f"/admin/produtos/{cid}/editar", product_data(name="Cookie"), png())
    assert svg.is_file()
    db.session.expire_all()
    assert MANAGED.match(db.session.get(Product, cid).image)


def test_database_failure_keeps_old_image_and_cleans_new_file(app, admin_client, monkeypatch):
    from sqlalchemy.exc import OperationalError
    p = create_product(admin_client, name="Falha Banco")
    old = p.image
    real_commit = db.session.commit

    def boom():
        raise OperationalError("x", {}, Exception("falha simulada"))
    monkeypatch.setattr(db.session, "commit", boom)
    r = submit(admin_client, f"/admin/produtos/{p.id}/editar", product_data(name="Falha Banco 2"), png(color=(1, 2, 3)))
    monkeypatch.setattr(db.session, "commit", real_commit)
    assert r.status_code == 200 and "Traceback" not in r.get_data(as_text=True)
    db.session.rollback()
    db.session.expire_all()
    p = db.session.get(Product, p.id)
    assert p.image == old and p.name == "Falha Banco"
    assert uploaded_files(app) == [old.rsplit("/", 1)[1]]  # imagem antiga intacta, nova removida


# ---------------------------------------------------------------- 9: exclusão
def test_delete_requires_confirmation_post_and_csrf(app, admin_client):
    p = create_product(admin_client, name="Para Excluir")
    html = admin_client.get("/admin/produtos").get_data(as_text=True)
    assert "data-delete-dialog" in html and "Excluir produto" in html and "irreversível" in html and "Cancelar" in html

    confirm = admin_client.get(f"/admin/produtos/{p.id}/excluir")  # GET só mostra a confirmação
    ch = confirm.get_data(as_text=True)
    assert confirm.status_code == 200 and "Para Excluir" in ch and "irreversível" in ch and 'method="post"' in ch
    assert db.session.get(Product, p.id) is not None

    assert admin_client.post(f"/admin/produtos/{p.id}/excluir").status_code == 400  # sem CSRF
    assert admin_client.post(f"/admin/produtos/{p.id}/excluir", data={"csrf_token": "falso"}).status_code == 400
    assert db.session.get(Product, p.id) is not None
    assert admin_client.post("/admin/produtos/999999/excluir", data={"csrf_token": token(admin_client)}).status_code == 404

    r = admin_client.post(f"/admin/produtos/{p.id}/excluir", data={"csrf_token": token(admin_client)}, follow_redirects=True)
    assert "foi excluído" in r.get_data(as_text=True)
    db.session.expire_all()
    assert db.session.get(Product, p.id) is None
    assert uploaded_files(app) == []  # a foto enviada pelo painel foi removida depois do commit


def test_delete_preserves_order_history_and_cleans_favorites(app, admin_client):
    cookie = get_product("cookie")
    buyer = make_customer("comprador@example.com")
    order = Order(customer_id=buyer.id, customer_name="Maria", customer_phone="(41) 99999-1234", subtotal_cents=2400, total_cents=2400,
                  submission_token="tok-historico-123", number="KN-HIST-1")
    order.items.append(OrderItem(product_id=cookie.id, product_name="Cookie", unit_price_cents=1200, quantity=2, line_total_cents=2400))
    db.session.add_all([order, Favorite(customer_id=buyer.id, product_id=cookie.id)])
    db.session.commit()
    oid, cid = order.id, cookie.id

    svg = Path(app.static_folder) / "img/produtos/cookie.svg"
    r = admin_client.post(f"/admin/produtos/{cid}/excluir", data={"csrf_token": token(admin_client)})
    assert r.status_code == 302
    db.session.expire_all()
    assert db.session.get(Product, cid) is None
    o = db.session.get(Order, oid)
    item = o.items[0]
    assert item.product_id is None and item.product_name == "Cookie"
    assert item.unit_price_cents == 1200 and item.line_total_cents == 2400 and item.quantity == 2 and o.total_cents == 2400
    assert db.session.query(Favorite).filter_by(product_id=cid).count() == 0
    assert svg.is_file()  # ilustração original do projeto nunca é apagada
    # o pedido antigo continua abrindo normalmente para o cliente
    c = login_as(app.test_client(), "comprador@example.com")
    assert c.get(f"/conta/pedidos/{o.public_id}").status_code == 200


def test_delete_failure_shows_safe_message(app, admin_client, monkeypatch):
    from sqlalchemy.exc import IntegrityError
    pid = db.session.scalar(db.select(Product.id).where(Product.slug == "cookie"))
    real_commit = db.session.commit

    def boom():
        raise IntegrityError("x", {}, Exception("fk"))
    monkeypatch.setattr(db.session, "commit", boom)
    r = admin_client.post(f"/admin/produtos/{pid}/excluir", data={"csrf_token": token(admin_client)}, follow_redirects=True)
    monkeypatch.setattr(db.session, "commit", real_commit)
    html = r.get_data(as_text=True)
    assert "Não foi possível excluir" in html and "marque-o como indisponível" in html and "Traceback" not in html
    db.session.rollback()
    db.session.expire_all()
    assert db.session.get(Product, pid) is not None


# ---------------------------------------------------------------- 11: CLI e migração
def test_promote_and_revoke_admin_cli(app):
    make_customer("ana@example.com")
    runner = app.test_cli_runner()
    r = runner.invoke(args=["promote-admin", "  ANA@Example.com "])
    assert r.exit_code == 0 and "agora é administradora" in r.output
    db.session.expire_all()
    assert db.session.scalar(db.select(Customer).where(Customer.email == "ana@example.com")).is_admin is True
    assert "já é administradora" in runner.invoke(args=["promote-admin", "ana@example.com"]).output
    r = runner.invoke(args=["revoke-admin", "ana@example.com"])
    assert r.exit_code == 0
    db.session.expire_all()
    assert db.session.scalar(db.select(Customer).where(Customer.email == "ana@example.com")).is_admin is False


def test_promote_admin_fails_for_unknown_account(app):
    r = app.test_cli_runner().invoke(args=["promote-admin", "ninguem@example.com"])
    assert r.exit_code != 0 and "Nenhuma conta encontrada" in r.output
    assert db.session.query(Customer).count() == 0  # nunca cria conta


def test_no_public_route_can_promote(app, client):
    rules = {r.rule for r in app.url_map.iter_rules()}
    assert not any("promote" in r or "promover" in r for r in rules)


def test_migration_adds_column_idempotently_and_keeps_data(tmp_path):
    from sqlalchemy import create_engine, inspect, text
    from knazh.migrations import add_customer_is_admin, run_migrations

    engine = create_engine(f"sqlite:///{tmp_path / 'antigo.db'}")
    with engine.begin() as conn:  # esquema da versão anterior (sem is_admin)
        conn.execute(text("CREATE TABLE customers (id INTEGER PRIMARY KEY, name VARCHAR(120) NOT NULL, email VARCHAR(254) NOT NULL UNIQUE, "
                          "phone VARCHAR(30) NOT NULL DEFAULT '', password_hash VARCHAR(255) NOT NULL, created_at DATETIME NOT NULL)"))
        conn.execute(text("INSERT INTO customers (name, email, phone, password_hash, created_at) VALUES "
                          "('Ana', 'ana@example.com', '', 'hash1', '2024-01-01 00:00:00'), ('Bia', 'bia@example.com', '', 'hash2', '2024-02-01 00:00:00')"))
    assert add_customer_is_admin(engine) == "adicionada"
    assert add_customer_is_admin(engine) == "ja-existe"  # idempotente
    assert run_migrations(engine) == [("customers.is_admin", "ja-existe"), ("customers.can_manage_admins", "adicionada")]
    assert run_migrations(engine) == [("customers.is_admin", "ja-existe"), ("customers.can_manage_admins", "ja-existe")]
    assert [c["name"] for c in inspect(engine).get_columns("customers")].count("is_admin") == 1
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT email, password_hash, is_admin FROM customers ORDER BY id")).all()
    assert [tuple(r) for r in rows] == [("ana@example.com", "hash1", 0), ("bia@example.com", "hash2", 0)]
    assert add_customer_is_admin(create_engine("sqlite://")) == "sem-tabela"


def test_migrate_db_command_is_repeatable(app):
    runner = app.test_cli_runner()
    first = runner.invoke(args=["migrate-db"])
    second = runner.invoke(args=["migrate-db"])
    assert first.exit_code == 0 and second.exit_code == 0
    assert "Migração concluída" in second.output and "já estava aplicada" in second.output


# ---------------------------------------------------------------- 12: o site público continua igual
def test_public_catalog_and_product_pages_still_work(admin_client, client):
    create_product(admin_client, name="Novo no Cardápio")
    for path in ("/", "/cardapio", "/cardapio/brownies", "/produto/brownie-tradicional", "/produto/novo-no-cardapio", "/busca?q=oreo", "/conta/entrar"):
        assert client.get(path).status_code == 200, path
    assert "Novo no Cardápio" in client.get("/cardapio?ordem=recentes").get_data(as_text=True)
