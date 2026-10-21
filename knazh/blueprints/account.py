"""Conta do cliente: cadastro, login, perfil, pedidos próprios e favoritos."""
from __future__ import annotations

from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, url_for
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from ..auth import login_customer, login_required, logout_customer
from ..extensions import db
from ..forms import LoginForm, ProfileForm, RegisterForm
from ..models import Customer, Favorite, Order, Product
from ..services.security import login_throttle, safe_next_url

bp = Blueprint("account", __name__, url_prefix="/conta")


def _throttle_key(email: str) -> str:
    return f"{request.remote_addr}|{email.lower()}"


@bp.route("/entrar", methods=["GET", "POST"])
def login():
    if g.customer:
        return redirect(url_for("account.dashboard"))
    form = LoginForm()
    if request.method == "GET":
        form.next.data = request.args.get("next", "")
    if form.validate_on_submit():
        email = form.email.data.lower()
        key = _throttle_key(email)
        if login_throttle.blocked(key):
            flash("Muitas tentativas. Aguarde alguns minutos e tente de novo.", "error")
        else:
            customer = db.session.scalar(select(Customer).where(Customer.email == email))
            if customer and customer.check_password(form.password.data):
                login_throttle.reset(key)
                login_customer(customer)
                return redirect(safe_next_url(form.next.data, url_for("account.dashboard")))
            login_throttle.hit(key)
            flash("E-mail ou senha incorretos.", "error")
    return render_template("account/login.html", form=form)


@bp.route("/cadastrar", methods=["GET", "POST"])
def register():
    if g.customer:
        return redirect(url_for("account.dashboard"))
    form = RegisterForm()
    if form.validate_on_submit() and form.email.data.lower() == current_app.config["INITIAL_ADMIN_EMAIL"]:
        # E-mail reservado ao administrador inicial: ele é criado só pelo comando de provisionamento (servidor), para que
        # ninguém registre esse e-mail antes e fique com a conta. Mesma mensagem genérica do cadastro duplicado.
        flash("Não foi possível criar a conta com esses dados. Se você já tem cadastro, entre na sua conta.", "error")
    elif form.validate_on_submit():
        customer = Customer(name=form.name.data, email=form.email.data.lower(), phone=form.phone.data)
        customer.set_password(form.password.data)
        try:
            db.session.add(customer)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("Não foi possível criar a conta com esses dados. Se você já tem cadastro, entre na sua conta.", "error")
        else:
            login_customer(customer)
            flash("Conta criada! Bem-vindo(a) à KNAZH.", "success")
            return redirect(url_for("account.dashboard"))
    return render_template("account/register.html", form=form)


@bp.post("/sair")
def logout():
    logout_customer()
    flash("Você saiu da sua conta.", "info")
    return redirect(url_for("main.home"))


@bp.get("")
@login_required
def dashboard():
    cid = g.customer.id
    orders = list(db.session.scalars(select(Order).where(Order.customer_id == cid).order_by(Order.id.desc()).limit(3)))
    n_orders = db.session.scalar(select(func.count(Order.id)).where(Order.customer_id == cid))
    n_favs = db.session.scalar(select(func.count(Favorite.id)).where(Favorite.customer_id == cid))
    return render_template("account/dashboard.html", orders=orders, n_orders=n_orders, n_favs=n_favs, section="perfil")


@bp.route("/perfil", methods=["GET", "POST"])
@login_required
def profile():
    form = ProfileForm(obj=g.customer)
    if form.validate_on_submit():
        g.customer.name, g.customer.phone = form.name.data, form.phone.data
        db.session.commit()
        flash("Perfil atualizado.", "success")
        return redirect(url_for("account.dashboard"))
    return render_template("account/profile.html", form=form, section="perfil")


@bp.get("/pedidos")
@login_required
def orders():
    rows = list(db.session.scalars(select(Order).where(Order.customer_id == g.customer.id).order_by(Order.id.desc())))
    return render_template("account/orders.html", orders=rows, section="pedidos")


@bp.get("/pedidos/<public_id>")
@login_required
def order_detail(public_id: str):
    order = db.session.scalar(select(Order).where(Order.public_id == public_id, Order.customer_id == g.customer.id))
    if order is None:
        abort(404)  # inclui pedidos de outros clientes: não revelamos que existem
    return render_template("account/order_detail.html", order=order, section="pedidos")


@bp.get("/favoritos")
@login_required
def favorites():
    products = list(db.session.scalars(select(Product).join(Favorite, Favorite.product_id == Product.id)
                                       .where(Favorite.customer_id == g.customer.id).order_by(Favorite.id.desc())))
    return render_template("account/favorites.html", products=products, favorite_ids={p.id for p in products}, section="favoritos")


@bp.post("/favoritos/alternar")
@login_required
def toggle_favorite():
    try:
        pid = int(request.form.get("product_id", ""))
    except ValueError:
        abort(400)
    product = db.session.get(Product, pid)
    if product is None:
        abort(404)
    fav = db.session.scalar(select(Favorite).where(Favorite.customer_id == g.customer.id, Favorite.product_id == pid))
    if fav:
        db.session.delete(fav)
        flash(f"“{product.name}” saiu dos favoritos.", "info")
    else:
        db.session.add(Favorite(customer_id=g.customer.id, product_id=pid))
        flash(f"“{product.name}” foi para os favoritos.", "success")
    db.session.commit()
    return redirect(safe_next_url(request.form.get("next"), url_for("account.favorites")))
