"""Painel administrativo do catálogo (somente contas com is_admin=True).

Segurança em camadas, todas no servidor:
1. `bp.before_request` aplica `require_admin()` a QUALQUER rota deste blueprint (inclusive as futuras);
2. cada view também usa `@admin_required` (defesa em profundidade);
3. todo POST passa pelo CSRFProtect global do app; a exclusão nunca acontece por GET.
"""
from __future__ import annotations

from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, url_for
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.datastructures import FileStorage

from ..auth import admin_manager_required, admin_required, require_admin, require_admin_manager
from ..extensions import db
from ..forms import ProductForm
from ..models import Category, Customer, Product
from ..services import admin_catalog as svc
from ..services import admin_users as users_svc
from ..services.money import cents_to_input
from ..services.security import safe_next_url
from ..services.uploads import ACCEPT_ATTR, UploadError, delete_managed_image, save_product_image

bp = Blueprint("admin", __name__, url_prefix="/admin")

GENERIC_SAVE_ERROR = "Não foi possível salvar agora. Nada foi alterado; tente novamente em instantes."


@bp.before_request
def _guard():
    denied = require_admin()
    if denied is None and (request.endpoint or "").startswith("admin.user_"):
        denied = require_admin_manager()  # gestão de administradores: exige a permissão específica, em QUALQUER rota user_*
    return denied


def _upload_dir():
    return current_app.config["UPLOAD_DIR"]


def _remove_file(rel_path: str | None) -> None:
    delete_managed_image(rel_path, upload_dir=_upload_dir())


def _uploaded_file(form: ProductForm) -> FileStorage | None:
    f = form.image.data
    return f if isinstance(f, FileStorage) and f.filename else None


def _store_upload(upload: FileStorage) -> str:
    cfg = current_app.config
    return save_product_image(upload.stream, upload.filename, upload.mimetype, upload_dir=_upload_dir(),
                              max_bytes=cfg["UPLOAD_MAX_FILE_BYTES"], max_pixels=cfg["UPLOAD_MAX_PIXELS"],
                              max_side=cfg["UPLOAD_MAX_SIDE"])


def _back(default: str) -> str:
    target = safe_next_url(request.form.get("next"), default)
    return target if target.startswith("/admin/") else default


def _get_product(product_id: int) -> Product:
    product = db.session.get(Product, product_id)
    if product is None:
        abort(404)
    return product


def _fill_form(form: ProductForm, product: Product) -> None:
    form.name.data, form.description.data, form.details.data = product.name, product.description, product.details
    form.category_id.data = str(product.category_id)
    form.price.data = cents_to_input(product.price_cents)
    form.image_alt.data = product.image_alt
    form.is_available.data, form.is_featured.data = product.is_available, product.is_featured


def _render_form(form: ProductForm, product: Product | None):
    return render_template("admin/product_form.html", form=form, product=product, accept=ACCEPT_ATTR,
                           max_bytes=current_app.config["UPLOAD_MAX_FILE_BYTES"], section="produtos")


@bp.get("/")
@admin_required
def index():
    return redirect(url_for("admin.products"))


@bp.get("/produtos")
@admin_required
def products():
    filters = svc.parse_filters(request.args)
    page = svc.search_products(filters)
    return render_template("admin/products.html", filters=filters, page=page, stats=svc.stats(),
                           categories=svc.all_categories(), status_options=svc.STATUS_OPTIONS, section="produtos")


@bp.route("/produtos/novo", methods=["GET", "POST"])
@admin_required
def product_new():
    form = ProductForm()
    form.set_categories(svc.form_categories())
    if request.method == "GET":
        form.is_available.data = True
    if form.validate_on_submit():
        upload = _uploaded_file(form)
        new_image = None
        if upload is None:
            form.image.errors = [*form.image.errors, "Escolha uma foto do produto."]
        else:
            try:
                new_image = _store_upload(upload)
            except UploadError as exc:
                form.image.errors = [*form.image.errors, str(exc)]
        if new_image:
            product = Product(
                slug=svc.unique_slug(form.name.data), name=form.name.data, description=form.description.data,
                details=form.details.data or "", price_cents=form.price_cents, image=new_image,
                image_alt=form.image_alt.data or "", is_available=form.is_available.data,
                is_featured=form.is_featured.data, is_demo=False,
            )
            product.category = db.session.get(Category, form.category_value)
            try:
                db.session.add(product)
                db.session.commit()
            except SQLAlchemyError:
                db.session.rollback()
                _remove_file(new_image)  # não deixa arquivo órfão
                flash(GENERIC_SAVE_ERROR, "error")
            else:
                flash(f"“{product.name}” foi cadastrado.", "success")
                return redirect(url_for("admin.products"))
    return _render_form(form, None)


@bp.route("/produtos/<int:product_id>/editar", methods=["GET", "POST"])
@admin_required
def product_edit(product_id: int):
    product = _get_product(product_id)
    form = ProductForm()
    form.set_categories(svc.form_categories(product))
    if request.method == "GET":
        _fill_form(form, product)
    if form.validate_on_submit():
        upload = _uploaded_file(form)
        new_image = None
        if upload is not None:
            try:
                new_image = _store_upload(upload)
            except UploadError as exc:
                form.image.errors = [*form.image.errors, str(exc)]
        if upload is None or new_image:
            old_image = product.image
            product.name, product.description = form.name.data, form.description.data
            product.details, product.image_alt = form.details.data or "", form.image_alt.data or ""
            product.price_cents = form.price_cents
            product.is_available, product.is_featured = form.is_available.data, form.is_featured.data
            product.category = db.session.get(Category, form.category_value)
            product.is_demo = False  # produto editado pelo painel deixa de ser "demo" (seed/remove-demo não o tocam)
            if new_image:
                product.image = new_image  # sem arquivo novo, a imagem atual é mantida
            try:
                db.session.commit()
            except SQLAlchemyError:
                db.session.rollback()
                _remove_file(new_image)
                flash(GENERIC_SAVE_ERROR, "error")
            else:
                if new_image:
                    _remove_file(old_image)  # só depois do commit; só apaga arquivos do próprio painel
                flash(f"“{product.name}” foi atualizado.", "success")
                return redirect(url_for("admin.products"))
    return _render_form(form, product)


@bp.post("/produtos/<int:product_id>/disponibilidade")
@admin_required
def product_toggle(product_id: int):
    product = _get_product(product_id)
    product.is_available = not product.is_available
    product.is_demo = False
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        flash(GENERIC_SAVE_ERROR, "error")
    else:
        state = "disponível" if product.is_available else "indisponível"
        flash(f"“{product.name}” agora está {state} na loja.", "success")
    return redirect(_back(url_for("admin.products")))


@bp.get("/produtos/<int:product_id>/excluir")
@admin_required
def product_delete_confirm(product_id: int):
    """Tela de confirmação (também serve de alternativa sem JavaScript). Este GET nunca exclui nada."""
    return render_template("admin/product_delete.html", product=_get_product(product_id), section="produtos")


@bp.post("/produtos/<int:product_id>/excluir")
@admin_required
def product_delete(product_id: int):
    product = _get_product(product_id)
    name, image = product.name, product.image
    try:
        svc.delete_product(product)
    except SQLAlchemyError:
        flash("Não foi possível excluir este produto agora. Se ele não deve mais aparecer na loja, "
              "marque-o como indisponível em vez de excluir.", "error")
        return redirect(_back(url_for("admin.products")))
    _remove_file(image)  # só depois do commit; ignora SVGs originais e qualquer coisa fora de uploads/products
    flash(f"“{name}” foi excluído.", "success")
    return redirect(_back(url_for("admin.products")))


# ------------------------------------------------------------------ gerenciar administradores
# Somente quem tem is_admin E can_manage_admins (before_request + @admin_manager_required). O serviço revalida no banco.
@bp.get("/administradores")
@admin_manager_required
def users():
    filters = users_svc.parse_filters(request.args)
    page = users_svc.search_users(filters, current_app.config["ADMIN_PER_PAGE"])
    return render_template("admin/users.html", filters=filters, page=page, stats=users_svc.stats(),
                           status_options=users_svc.STATUS_OPTIONS, section="administradores")


def _get_user(user_id: int) -> Customer:
    user = db.session.get(Customer, user_id)
    if user is None:
        abort(404)
    return user


@bp.route("/administradores/<int:user_id>/conceder", methods=["GET", "POST"])
@admin_manager_required
def user_grant(user_id: int):
    """GET: tela de confirmação (também serve sem JavaScript; nunca altera nada). POST: concede o acesso."""
    target = _get_user(user_id)
    if request.method == "POST":
        result = users_svc.grant_admin(g.customer, target.id, can_manage=request.form.get("can_manage") == "y")
        flash(result.message, "success" if result.ok else "error")
        return redirect(_back(url_for("admin.users")))
    return render_template("admin/user_confirm.html", target=target, action="grant", section="administradores")


@bp.route("/administradores/<int:user_id>/remover", methods=["GET", "POST"])
@admin_manager_required
def user_revoke(user_id: int):
    """GET: tela de confirmação (nunca altera nada). POST: remove o acesso administrativo."""
    target = _get_user(user_id)
    if request.method == "POST":
        result = users_svc.revoke_admin(g.customer, target.id)
        flash(result.message, "success" if result.ok else "error")
        return redirect(_back(url_for("admin.users")))
    return render_template("admin/user_confirm.html", target=target, action="revoke", section="administradores")
