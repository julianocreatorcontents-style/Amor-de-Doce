from knazh.extensions import db
from knazh.models import Category, Product
from knazh.demo_data import seed_demo
from knazh.services.money import format_brl
from knazh.services.text import normalize


def names(html):
    import re
    return re.findall(r'class="product-card__title"><a [^>]*>([^<]+)</a>', html)


def test_money_format_uses_cents_and_brazilian_style():
    assert format_brl(1400) == "R$ 14,00"
    assert format_brl(123456) == "R$ 1.234,56"
    assert format_brl(5) == "R$ 0,05"
    assert normalize("  Paçoca   DOCE ") == "pacoca doce"


def test_seed_is_idempotent_and_never_overwrites_real_products(app):
    before = db.session.query(Product).count()
    assert seed_demo()["criados"] == 0
    assert db.session.query(Product).count() == before
    real = db.session.scalar(db.select(Product).where(Product.slug == "cookie"))
    real.is_demo, real.price_cents = False, 9999
    db.session.commit()
    seed_demo()
    assert db.session.scalar(db.select(Product.price_cents).where(Product.slug == "cookie")) == 9999


def test_catalog_lists_products_from_database(client):
    html = client.get("/cardapio").get_data(as_text=True)
    assert "Brownie Tradicional" in html and "Cookie" in html
    assert "17 produtos encontrados" in html


def test_category_page_and_unknown_category(client):
    html = client.get("/cardapio/brownies").get_data(as_text=True)
    assert "8 produtos encontrados" in html and "Mousse" not in html
    assert client.get("/cardapio/inexistente").status_code == 404


def test_search_ignores_case_accents_and_extra_spaces(client):
    a = names(client.get("/busca?q=PAÇOCA").get_data(as_text=True))
    b = names(client.get("/busca?q=%20%20pacoca%20").get_data(as_text=True))
    assert a == b == ["Brownie de Paçoca"]


def test_search_matches_description_and_all_terms(client):
    assert "Brownie com Oreo" in client.get("/busca?q=creme+oreo").get_data(as_text=True)
    assert "nenhum resultado" in client.get("/busca?q=oreo+maracuja").get_data(as_text=True).lower()


def test_search_changes_result_set_and_empty_query_goes_to_catalog(client):
    assert client.get("/busca?q=mousse").get_data(as_text=True).count("product-card__title") == 3
    r = client.get("/busca?q=")
    assert r.status_code == 302 and r.headers["Location"].endswith("/cardapio")


def test_search_empty_state_offers_next_action(client):
    html = client.get("/busca?q=pizza").get_data(as_text=True)
    assert "Nenhum resultado encontrado" in html and "/cardapio" in html


def test_search_term_with_like_wildcards_is_literal(client):
    assert "Nenhum resultado" in client.get("/busca?q=%25").get_data(as_text=True)


def test_filter_by_category_and_price_and_sort(client):
    html = client.get("/cardapio?categoria=brigadeiros&ordem=menor-preco").get_data(as_text=True)
    assert names(html) == ["Brigadeiro Tradicional", "Brigadeiro Gourmet", "Brigadeiro de Ninho"]
    html = client.get("/cardapio?preco=ate-15&ordem=maior-preco").get_data(as_text=True)
    got = names(html)
    assert got[0] == "Bolo de Chocolate" and "Brownie Tradicional" in got and "Brownie com Oreo" not in got
    assert all(n in got for n in ["Brigadeiro Gourmet", "Cookie"])
    html = client.get("/cardapio?categoria=outros&categoria=bolos&ordem=nome").get_data(as_text=True)
    assert names(html) == ["Bolo de Chocolate", "Bolo no Pote", "Cookie"]


def test_invalid_filter_params_are_ignored_not_errors(client):
    r = client.get("/cardapio?categoria=x'%3BDROP&preco=zzz&ordem=hack&pagina=abc")
    assert r.status_code == 200 and "17 produtos" in r.get_data(as_text=True)


def test_pagination(client):
    p1 = names(client.get("/cardapio").get_data(as_text=True))
    p2 = names(client.get("/cardapio?pagina=2").get_data(as_text=True))
    assert len(p1) == 12 and len(p2) == 5 and not set(p1) & set(p2)
    assert client.get("/cardapio?pagina=99").status_code == 200


def test_empty_category_state(client, app):
    db.session.add(Category(slug="vazia", name="Vazia", sort_order=9))
    db.session.commit()
    html = client.get("/cardapio/vazia").get_data(as_text=True)
    assert "Nenhum produto encontrado" in html and "Ver outras categorias" in html


def test_product_detail_and_404(client):
    html = client.get("/produto/brownie-tradicional").get_data(as_text=True)
    assert "Brownie Tradicional" in html and "R$ 14,00" in html and "Adicionar ao carrinho" in html
    assert client.get("/produto/nao-existe").status_code == 404


def test_unavailable_product_cannot_be_bought(client, post, product_id):
    html = client.get("/produto/brownie-de-pistache").get_data(as_text=True)
    assert "Produto indisponível" in html and "Adicionar ao carrinho" not in html
    r = post("/carrinho/adicionar", {"product_id": product_id("brownie-de-pistache"), "quantity": 1}, follow=True)
    assert "indisponível" in r.get_data(as_text=True)
    assert "Seu carrinho está vazio" in client.get("/carrinho").get_data(as_text=True)


def test_demo_banner_is_gone_even_with_demo_products(client):
    from knazh.models import Product
    assert db.session.scalar(db.select(db.func.count(Product.id)).where(Product.is_demo.is_(True))) > 0  # há produtos demo
    for path in ("/", "/cardapio", "/contato", "/conta/entrar"):
        html = client.get(path).get_data(as_text=True)
        assert "Catálogo de demonstração" not in html and "demo-notice" not in html, path
        assert html.index('<header class="site-header">') < html.index("<main"), path
