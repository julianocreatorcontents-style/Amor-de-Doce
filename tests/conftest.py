import re

import pytest

from knazh import create_app
from knazh.config import TestConfig
from knazh.demo_data import seed_demo
from knazh.extensions import db
from knazh.models import Category, Product
from knazh.services.security import login_throttle


@pytest.fixture()
def app(tmp_path):
    class Cfg(TestConfig):
        UPLOAD_DIR = tmp_path / "uploads" / "products"  # cada teste grava num diretório temporário próprio

    login_throttle.reset()
    app = create_app(Cfg)
    with app.app_context():
        db.create_all()
        seed_demo()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def csrf_token(client, path="/contato"):
    html = client.get(path).get_data(as_text=True)
    return re.search(r'name="csrf-token" content="([^"]+)"', html).group(1)


@pytest.fixture()
def post(client):
    def _post(path, data=None, token_from="/contato", follow=False, **kw):
        data = dict(data or {})
        data.setdefault("csrf_token", csrf_token(client, token_from))
        return client.post(path, data=data, follow_redirects=follow, **kw)
    return _post


def pid(slug):
    return db.session.scalar(db.select(Product.id).where(Product.slug == slug))


@pytest.fixture()
def product_id(app):
    return pid


VALID_ORDER = {"name": "Maria Silva", "phone": "(41) 99999-1234", "email": "", "notes": "Sem granulado"}


@pytest.fixture()
def fill_cart(client, post):
    def _fill(*items):
        for slug, qty in items:
            post("/carrinho/adicionar", {"product_id": pid(slug), "quantity": qty})
    return _fill
