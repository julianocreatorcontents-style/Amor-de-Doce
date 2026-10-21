"""Páginas institucionais, contato e arquivos técnicos (robots, sitemap, manifest)."""
from __future__ import annotations

from flask import Blueprint, Response, current_app, flash, redirect, render_template, request, send_from_directory, url_for
from sqlalchemy import select

from .. import content
from ..extensions import db
from ..forms import ContactForm
from ..models import Category, ContactMessage, Product
from ..services.catalog import active_categories, featured_products
from ..services.mailer import send_contact_email

bp = Blueprint("main", __name__)


@bp.get("/")
def home():
    return render_template("pages/home.html", featured=featured_products(5), categories=active_categories())


@bp.get("/sobre")
def about():
    return render_template("pages/about.html", values=content.ABOUT_VALUES)


@bp.get("/duvidas")
def faq():
    groups = []
    for slug, label, icon in content.FAQ_CATEGORIES:
        items = [(q, a or content.PENDING_ANSWER, a is None) for cat, q, a in content.FAQ_ITEMS if cat == slug]
        if items:
            groups.append({"slug": slug, "label": label, "icon": icon, "entries": items})
    return render_template("pages/faq.html", groups=groups)


@bp.route("/contato", methods=["GET", "POST"])
def contact():
    form = ContactForm()
    if form.validate_on_submit():
        if form.website.data:  # honeypot: robôs preenchem; descartamos sem gravar
            return redirect(url_for("main.contact", enviado=1))
        msg = ContactMessage(name=form.name.data, email=form.email.data.lower(), subject=form.subject.data, message=form.message.data)
        db.session.add(msg)
        db.session.commit()
        msg.email_status = send_contact_email(msg.name, msg.email, msg.subject, msg.message)
        db.session.commit()
        return redirect(url_for("main.contact", enviado=1))
    if request.method == "POST":
        flash("Confira os campos destacados e tente novamente.", "error")
    return render_template("pages/contact.html", form=form, sent=request.args.get("enviado") == "1")


@bp.get("/privacidade")
def privacy():
    return render_template("pages/legal.html", title="Política de Privacidade", sections=content.PRIVACY_SECTIONS, kind="privacidade")


@bp.get("/termos")
def terms():
    return render_template("pages/legal.html", title="Termos de Uso", sections=content.TERMS_SECTIONS, kind="termos")


@bp.get("/robots.txt")
def robots():
    base = current_app.config["SITE_URL"] or request.url_root.rstrip("/")
    body = "User-agent: *\nAllow: /\nDisallow: /carrinho\nDisallow: /finalizar\nDisallow: /pedido/\nDisallow: /conta\n" f"Sitemap: {base}/sitemap.xml\n"
    return Response(body, mimetype="text/plain")


@bp.get("/sitemap.xml")
def sitemap():
    base = current_app.config["SITE_URL"] or request.url_root.rstrip("/")
    paths = ["/", "/cardapio", "/sobre", "/duvidas", "/contato", "/privacidade", "/termos"]
    paths += [f"/cardapio/{s}" for s in db.session.scalars(select(Category.slug).where(Category.is_active.is_(True)))]
    paths += [f"/produto/{s}" for s in db.session.scalars(select(Product.slug).join(Category).where(Category.is_active.is_(True)))]
    xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    xml += [f"<url><loc>{base}{p}</loc></url>" for p in paths]
    xml.append("</urlset>")
    return Response("\n".join(xml), mimetype="application/xml")


@bp.get("/favicon.ico")
def favicon():
    return send_from_directory(current_app.static_folder + "/img/brand", "favicon.ico", mimetype="image/vnd.microsoft.icon")


@bp.get("/site.webmanifest")
def manifest():
    s = lambda f: url_for("static", filename=f"img/brand/{f}")
    data = {
        "name": "KNAZH — Sabor em Todas as Formas", "short_name": "KNAZH", "description": "Doces e sobremesas KNAZH.",
        "start_url": "/", "display": "standalone", "background_color": "#FFF5E8", "theme_color": "#171717",
        "icons": [
            {"src": s("icon-192x192.png"), "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": s("icon-512x512.png"), "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": s("icon-maskable-512x512.png"), "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
    }
    import json
    return Response(json.dumps(data, ensure_ascii=False), mimetype="application/manifest+json")
