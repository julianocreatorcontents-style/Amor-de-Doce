"""DADOS DE DEMONSTRAÇÃO — claramente separados do catálogo oficial.

Nomes e descrições seguem as telas de referência; os PREÇOS, a popularidade e a disponibilidade são FICTÍCIOS,
só para exercitar catálogo, filtros, carrinho e pedidos. As imagens são ilustrações demonstrativas (não fotos aprovadas).
Todo produto criado aqui recebe is_demo=True e o site exibe um aviso enquanto houver produtos demo.

Para o catálogo real: cadastre/importe seus produtos (futuramente pelo GabHub) e rode `flask --app wsgi remove-demo`.
"""
from __future__ import annotations

from sqlalchemy import select

from .extensions import db
from .models import Category, Product
from .services.text import slugify

CATEGORIES = [
    ("brownies", "Brownies", "Massa fofinha, muito chocolate e aquele toque especial KNAZH.", "brownie", 1),
    ("brigadeiros", "Brigadeiros", "Cremosos, intensos e irresistíveis.", "brigadeiro", 2),
    ("bolos", "Bolos", "Camadas de sabor em cada colherada.", "bolo", 3),
    ("sobremesas", "Sobremesas", "Cremosas, leves e irresistíveis.", "sobremesa", 4),
    ("outros", "Outros", "Outras delícias para completar o seu pedido.", "outros", 5),
]

# (categoria, nome, descrição, preço_centavos_DEMO, imagem, popularidade, destaque, disponível)
PRODUCTS = [
    ("brownies", "Brownie Tradicional", "Massa fofinha, muito chocolate e toque especial KNAZH.", 1400, "brownie-tradicional", 100, True, True),
    ("brownies", "Brownie com Oreo", "Brownie com cobertura de creme e pedaços de Oreo.", 1800, "brownie-oreo", 90, False, True),
    ("brownies", "Brownie com Brigadeiro", "Brownie coberto com brigadeiro e granulado.", 1700, "brownie-brigadeiro", 80, False, True),
    ("brownies", "Brownie de Chocolate Branco", "Massa de chocolate com cobertura de chocolate branco e morangos.", 2000, "brownie-chocolate-branco", 70, False, True),
    ("brownies", "Brownie com Doce de Leite", "Brownie com cobertura de doce de leite e castanhas.", 1800, "brownie-doce-de-leite", 60, False, True),
    ("brownies", "Brownie de Paçoca", "Brownie com cobertura de paçoca e amendoim.", 1700, "brownie-pacoca", 55, False, True),
    ("brownies", "Brownie de Pistache", "Brownie com cobertura de pistache e crocante.", 2400, "brownie-pistache", 40, False, False),
    ("brownies", "Brownie com Chocolate Belga", "Massa com pedaços de chocolate belga.", 2600, "brownie-chocolate-belga", 65, False, True),
    ("brigadeiros", "Brigadeiro Gourmet", "Cremoso, intenso e irresistível.", 600, "brigadeiro-gourmet", 95, True, True),
    ("brigadeiros", "Brigadeiro de Ninho", "Brigadeiro cremoso de leite em pó, enrolado à mão.", 650, "brigadeiro-ninho", 50, False, True),
    ("brigadeiros", "Brigadeiro Tradicional", "O clássico de chocolate com granulado.", 500, "brigadeiro-tradicional", 45, False, True),
    ("bolos", "Bolo no Pote", "Camadas de sabor em cada colherada.", 1600, "bolo-no-pote", 92, True, True),
    ("bolos", "Bolo de Chocolate", "Fatia de bolo de chocolate com cobertura cremosa.", 1500, "bolo-chocolate", 58, False, True),
    ("sobremesas", "Mousse de Chocolate", "Cremoso, leve e irresistível.", 1500, "mousse-chocolate", 88, True, True),
    ("sobremesas", "Mousse de Maracujá", "Mousse aerada com o frescor do maracujá.", 1500, "mousse-maracuja", 52, False, True),
    ("sobremesas", "Mousse de Morango", "Mousse cremosa com sabor de morango.", 1500, "mousse-morango", 53, False, True),
    ("outros", "Cookie", "Crocante por fora, macio por dentro.", 1200, "cookie", 85, True, True),
]


def seed_demo() -> dict[str, int]:
    """Idempotente: cria/atualiza apenas itens demo (por slug). Nunca apaga pedidos nem produtos reais."""
    created = updated = 0
    cats: dict[str, Category] = {}
    for slug, name, desc, icon, order in CATEGORIES:
        cat = db.session.scalar(select(Category).where(Category.slug == slug))
        if cat is None:
            cat = Category(slug=slug, name=name, description=desc, icon=icon, sort_order=order)
            db.session.add(cat)
        cats[slug] = cat
    db.session.flush()
    for cat_slug, name, desc, price, img, pop, feat, avail in PRODUCTS:
        slug = slugify(name)
        p = db.session.scalar(select(Product).where(Product.slug == slug))
        if p is not None and not p.is_demo:
            continue  # nunca sobrescreve um produto real
        is_new = p is None
        if is_new:
            p = Product(slug=slug)
            db.session.add(p)
        p.name, p.description, p.price_cents = name, desc, price
        p.category = cats[cat_slug]
        p.image, p.image_alt = f"img/produtos/{img}.svg", f"Ilustração demonstrativa: {name}"
        p.popularity, p.is_featured, p.is_available, p.is_demo = pop, feat, avail, True
        created += is_new
        updated += not is_new
    db.session.commit()
    return {"criados": created, "atualizados": updated}


def remove_demo() -> int:
    """Remove somente produtos marcados como demo (pedidos antigos mantêm o snapshot)."""
    rows = list(db.session.scalars(select(Product).where(Product.is_demo.is_(True))))
    for p in rows:
        db.session.delete(p)
    db.session.commit()
    return len(rows)
