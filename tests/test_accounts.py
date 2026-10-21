import re

from knazh.extensions import db
from knazh.models import Customer, Favorite, Order
from tests.conftest import VALID_ORDER, pid

REG = {"name": "Ana Souza", "email": "ana@example.com", "phone": "(41) 98888-7777", "password": "senha1234", "confirm": "senha1234"}


def register(post, **over):
    return post("/conta/cadastrar", {**REG, **over}, token_from="/conta/cadastrar")


def login(post, email="ana@example.com", password="senha1234", **extra):
    return post("/conta/entrar", {"email": email, "password": password, **extra}, token_from="/conta/entrar")


def place_order(client, post, slug="cookie"):
    post("/carrinho/adicionar", {"product_id": pid(slug), "quantity": 1})
    page = client.get("/finalizar").get_data(as_text=True)
    token = re.search(r'name="submission_token"[^>]*value="([^"]+)"', page).group(1)
    return post("/finalizar", {**VALID_ORDER, "submission_token": token}, token_from="/finalizar").headers["Location"]


def test_register_hashes_password_and_logs_in(client, post):
    r = register(post)
    assert r.status_code == 302 and r.headers["Location"].endswith("/conta")
    c = db.session.scalar(db.select(Customer))
    assert c.email == "ana@example.com" and c.password_hash != "senha1234" and "senha1234" not in c.password_hash
    assert c.check_password("senha1234") and not c.check_password("outra")
    assert "Olá, Ana!" in client.get("/conta").get_data(as_text=True)


def test_register_validation(client, post):
    for over in [{"password": "curta1", "confirm": "curta1"}, {"password": "somenteletras", "confirm": "somenteletras"},
                 {"confirm": "diferente123"}, {"email": "ruim"}, {"phone": "1"}, {"name": ""}]:
        r = register(post, **over)
        assert r.status_code == 200
    assert db.session.query(Customer).count() == 0


def test_duplicate_email_rejected_case_insensitive(app, client, post):
    register(post)
    other = app.test_client()
    tok = re.search(r'csrf-token" content="([^"]+)"', other.get("/conta/cadastrar").get_data(as_text=True)).group(1)
    r = other.post("/conta/cadastrar", data={**REG, "email": "ANA@Example.com", "csrf_token": tok})
    assert r.status_code == 200 and db.session.query(Customer).count() == 1


def test_login_wrong_password_and_throttle(client, post):
    register(post)
    client.post("/conta/sair", data={"csrf_token": re.search(r'csrf-token" content="([^"]+)"', client.get("/contato").get_data(as_text=True)).group(1)})
    for _ in range(5):
        assert "incorretos" in login(post, password="errada123").get_data(as_text=True)
    assert "Muitas tentativas" in login(post).get_data(as_text=True)


def test_login_ok_and_safe_next(client, post):
    register(post)
    post("/conta/sair")
    r = login(post, next="/cardapio")
    assert r.headers["Location"].endswith("/cardapio")
    post("/conta/sair")
    r = login(post, next="https://evil.example")
    assert r.headers["Location"].endswith("/conta")


def test_private_pages_require_login(client):
    for url in ["/conta", "/conta/pedidos", "/conta/favoritos", "/conta/perfil"]:
        r = client.get(url)
        assert r.status_code == 302 and "/conta/entrar" in r.headers["Location"]


def test_customer_cannot_see_another_customers_orders(app, post, client):
    register(post)
    loc = place_order(client, post)
    public_id = loc.rsplit("/", 1)[1]
    assert public_id in client.get("/conta/pedidos").get_data(as_text=True) or "KNZ-" in client.get("/conta/pedidos").get_data(as_text=True)
    assert client.get(f"/conta/pedidos/{public_id}").status_code == 200

    other = app.test_client()
    tok = re.search(r'csrf-token" content="([^"]+)"', other.get("/conta/cadastrar").get_data(as_text=True)).group(1)
    other.post("/conta/cadastrar", data={**REG, "email": "bia@example.com", "name": "Bia", "csrf_token": tok})
    assert other.get(f"/conta/pedidos/{public_id}").status_code == 404
    assert other.get(loc).status_code == 404
    assert "KNZ-" not in other.get("/conta/pedidos").get_data(as_text=True)


def test_logged_order_is_linked_to_customer(client, post):
    register(post)
    place_order(client, post)
    assert db.session.scalar(db.select(Order.customer_id)) == db.session.scalar(db.select(Customer.id))


def test_guest_checkout_has_no_customer(client, post):
    place_order(client, post)
    assert db.session.scalar(db.select(Order.customer_id)) is None


def test_favorites_toggle(client, post):
    register(post)
    post("/conta/favoritos/alternar", {"product_id": pid("cookie")})
    assert db.session.query(Favorite).count() == 1
    assert "Cookie" in client.get("/conta/favoritos").get_data(as_text=True)
    post("/conta/favoritos/alternar", {"product_id": pid("cookie")})
    assert db.session.query(Favorite).count() == 0
    assert post("/conta/favoritos/alternar", {"product_id": "abc"}).status_code == 400
    assert post("/conta/favoritos/alternar", {"product_id": "99999"}).status_code == 404


def test_profile_update(client, post):
    register(post)
    post("/conta/perfil", {"name": "Ana Maria", "phone": "(41) 97777-6666"}, token_from="/conta/perfil")
    assert db.session.scalar(db.select(Customer.name)) == "Ana Maria"
