import re

import pytest

from knazh.extensions import db
from knazh.models import Order, OrderItem, Product
from tests.conftest import VALID_ORDER, csrf_token, pid


def cart_html(client):
    return client.get("/carrinho").get_data(as_text=True)


def cart_names(client):
    html = cart_html(client)
    m = re.search(r'<ul class="cart-list">(.*?)</ul>', html, re.S)
    return re.findall(r'<h3><a href="/produto/[^"]+">([^<]+)</a></h3>', m.group(1)) if m else []


def test_empty_cart_state(client):
    html = cart_html(client)
    assert "Seu carrinho está vazio" in html and "Ver cardápio" in html


def test_add_update_remove_and_totals(client, post, fill_cart):
    fill_cart(("brownie-tradicional", 2), ("cookie", 1))
    html = cart_html(client)
    assert "R$ 28,00" in html and "R$ 12,00" in html and "R$ 40,00" in html and "3 itens" in html
    post("/carrinho/atualizar", {"product_id": pid("brownie-tradicional"), "quantity": 3})
    assert "R$ 54,00" in cart_html(client)
    post("/carrinho/remover", {"product_id": pid("cookie")})
    html = cart_html(client)
    assert cart_names(client) == ["Brownie Tradicional"] and "R$ 42,00" in html
    post("/carrinho/atualizar", {"product_id": pid("brownie-tradicional"), "quantity": 0})
    assert "Seu carrinho está vazio" in cart_html(client)


def test_adding_same_product_merges_quantity(client, fill_cart):
    fill_cart(("cookie", 1), ("cookie", 2))
    assert "3 itens" in cart_html(client)


def test_cart_badge_counts_items(client, fill_cart):
    fill_cart(("cookie", 2), ("brownie-com-oreo", 1))
    assert re.search(r'data-cart-count >3<', client.get("/").get_data(as_text=True))


@pytest.mark.parametrize("qty", ["0", "-1", "abc", "", "999", "1.5"])
def test_invalid_quantities_rejected(client, post, qty):
    r = post("/carrinho/adicionar", {"product_id": pid("cookie"), "quantity": qty}, follow=True)
    assert "Seu carrinho está vazio" in cart_html(client)
    assert r.status_code == 200


def test_unknown_product_and_garbage_ids_rejected(client, post):
    for bad in ["99999", "abc", "-3", ""]:
        post("/carrinho/adicionar", {"product_id": bad, "quantity": 1})
    assert "Seu carrinho está vazio" in cart_html(client)


def test_max_quantity_per_product_enforced(client, post, fill_cart):
    fill_cart(("cookie", 20))
    post("/carrinho/adicionar", {"product_id": pid("cookie"), "quantity": 1})
    assert "20 itens" in cart_html(client)


def test_json_response_for_fetch(client, post):
    r = post("/carrinho/adicionar", {"product_id": pid("cookie"), "quantity": 2}, headers={"X-Requested-With": "fetch"})
    assert r.get_json() == {"ok": True, "message": "“Cookie” foi adicionado ao carrinho.", "count": 2}
    r = post("/carrinho/adicionar", {"product_id": "x", "quantity": 1}, headers={"X-Requested-With": "fetch"})
    assert r.status_code == 400 and r.get_json()["ok"] is False


def test_open_redirect_blocked_on_next(client, post):
    r = post("/carrinho/adicionar", {"product_id": pid("cookie"), "quantity": 1, "next": "https://evil.example/x"})
    assert r.headers["Location"].endswith("/carrinho")
    r = post("/carrinho/adicionar", {"product_id": pid("cookie"), "quantity": 1, "next": "//evil.example"})
    assert r.headers["Location"].endswith("/carrinho")
    r = post("/carrinho/adicionar", {"product_id": pid("cookie"), "quantity": 1, "next": "/cardapio?x=1"})
    assert r.headers["Location"].endswith("/cardapio?x=1")


def test_csrf_required_for_state_changes(client):
    r = client.post("/carrinho/adicionar", data={"product_id": 1, "quantity": 1})
    assert r.status_code == 400 and "Traceback" not in r.get_data(as_text=True)


def test_product_becoming_unavailable_blocks_checkout(client, fill_cart):
    fill_cart(("cookie", 1))
    db.session.execute(db.update(Product).where(Product.slug == "cookie").values(is_available=False))
    db.session.commit()
    html = cart_html(client)
    assert "ficou indisponível" in html and "/finalizar" not in html
    assert client.get("/finalizar").status_code == 302


def test_product_removed_from_catalog_is_dropped_from_cart(client, fill_cart):
    fill_cart(("cookie", 1), ("brownie-com-oreo", 1))
    p = db.session.scalar(db.select(Product).where(Product.slug == "cookie"))
    db.session.delete(p)
    db.session.commit()
    html = cart_html(client)  # aviso aparece uma vez; depois o carrinho já foi limpo
    assert "não está mais no cardápio" in html
    assert cart_names(client) == ["Brownie com Oreo"]


def test_checkout_redirects_when_cart_empty(client):
    r = client.get("/finalizar")
    assert r.status_code == 302 and r.headers["Location"].endswith("/carrinho")


def checkout_post(client, post, **overrides):
    page = client.get("/finalizar").get_data(as_text=True)
    token = re.search(r'name="submission_token"[^>]*value="([^"]+)"', page).group(1)
    data = {**VALID_ORDER, "submission_token": token, **overrides}
    return post("/finalizar", data, token_from="/finalizar")


def test_order_created_with_server_prices_and_persisted(client, post, fill_cart):
    fill_cart(("brownie-tradicional", 2), ("cookie", 1))
    r = checkout_post(client, post, price="1", total_cents="1", total="0,01", unit_price_cents="1")  # manipulação ignorada
    assert r.status_code == 302 and "/pedido/" in r.headers["Location"]
    order = db.session.scalar(db.select(Order))
    assert order.number == f"KNZ-{order.id:06d}" and order.status == "pendente"
    assert order.total_cents == 4000 and order.subtotal_cents == 4000
    assert {(i.product_name, i.quantity, i.unit_price_cents, i.line_total_cents) for i in order.items} == {
        ("Brownie Tradicional", 2, 1400, 2800), ("Cookie", 1, 1200, 1200)}
    assert order.customer_name == "Maria Silva" and order.notes == "Sem granulado"
    assert "Seu carrinho está vazio" in cart_html(client)  # carrinho limpo após o pedido


def test_order_snapshot_survives_price_change(client, post, fill_cart):
    fill_cart(("cookie", 2))
    checkout_post(client, post)
    db.session.execute(db.update(Product).where(Product.slug == "cookie").values(price_cents=9900, name="Outro"))
    db.session.commit()
    item = db.session.scalar(db.select(OrderItem))
    assert (item.product_name, item.unit_price_cents) == ("Cookie", 1200)


def test_confirmation_page_is_honest_and_unconfigured_channels_noted(client, post, fill_cart):
    fill_cart(("cookie", 1))
    loc = checkout_post(client, post).headers["Location"]
    html = client.get(loc).get_data(as_text=True)
    assert "Aguardando confirmação" in html and "ainda não foi confirmado nem cobrado" in html
    assert "ainda não foram configurados" in html and "wa.me" not in html


@pytest.mark.parametrize("field,value", [("name", ""), ("name", "A"), ("phone", "123"), ("phone", "abc"), ("email", "sem-arroba"), ("notes", "x" * 501)])
def test_checkout_validation_rejects_bad_data(client, post, fill_cart, field, value):
    fill_cart(("cookie", 1))
    r = checkout_post(client, post, **{field: value})
    assert r.status_code == 200 and "Confira os campos" in r.get_data(as_text=True)
    assert db.session.query(Order).count() == 0
    assert "1 item" in cart_html(client)


def test_double_submit_does_not_duplicate_order(client, post, fill_cart):
    fill_cart(("cookie", 1))
    page = client.get("/finalizar").get_data(as_text=True)
    token = re.search(r'name="submission_token"[^>]*value="([^"]+)"', page).group(1)
    data = {**VALID_ORDER, "submission_token": token}
    r1 = post("/finalizar", data, token_from="/finalizar")
    r2 = post("/finalizar", data, token_from="/contato")
    assert r1.headers["Location"] == r2.headers["Location"]
    assert db.session.query(Order).count() == 1


def test_checkout_blocked_without_csrf(client, fill_cart):
    fill_cart(("cookie", 1))
    assert client.post("/finalizar", data=VALID_ORDER).status_code == 400
    assert db.session.query(Order).count() == 0


def test_confirmation_not_visible_to_other_sessions(app, client, post, fill_cart):
    fill_cart(("cookie", 1))
    loc = checkout_post(client, post).headers["Location"]
    assert client.get(loc).status_code == 200
    assert app.test_client().get(loc).status_code == 404
    assert client.get("/pedido/inexistente").status_code == 404
