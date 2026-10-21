"""Formulários (Flask-WTF): validação no servidor + CSRF."""
from __future__ import annotations

import re

from flask_wtf import FlaskForm
from flask_wtf.file import FileField
from wtforms import BooleanField, HiddenField, PasswordField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, EqualTo, Length, Optional, ValidationError

from .services.money import parse_brl_to_cents

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _strip(value):
    return _CTRL.sub("", value).strip() if isinstance(value, str) else value


def email_check(_form, field):
    if field.data and not EMAIL_RE.match(field.data):
        raise ValidationError("Informe um e-mail válido (ex.: nome@email.com).")


def phone_check(_form, field):
    digits = re.sub(r"\D", "", field.data or "")
    if not 10 <= len(digits) <= 13:
        raise ValidationError("Informe um telefone com DDD (ex.: (41) 99999-9999).")


class CheckoutForm(FlaskForm):
    name = StringField("Nome completo", filters=[_strip], validators=[DataRequired("Informe seu nome."), Length(2, 120, "O nome deve ter entre 2 e 120 caracteres.")])
    phone = StringField("Telefone / WhatsApp", filters=[_strip], validators=[DataRequired("Informe um telefone para contato."), phone_check])
    email = StringField("E-mail (opcional)", filters=[_strip], validators=[Optional(), Length(max=254), email_check])
    notes = TextAreaField("Observações (opcional)", filters=[_strip], validators=[Optional(), Length(max=500, message="Use até 500 caracteres.")])
    submission_token = HiddenField(validators=[DataRequired(), Length(8, 64)])


class ContactForm(FlaskForm):
    SUBJECTS = ["Dúvida", "Sugestão", "Elogio", "Reclamação", "Sobre um pedido", "Outro assunto"]
    name = StringField("Nome completo", filters=[_strip], validators=[DataRequired("Informe seu nome."), Length(2, 120)])
    email = StringField("E-mail", filters=[_strip], validators=[DataRequired("Informe seu e-mail."), Length(max=254), email_check])
    subject = SelectField("Assunto", choices=[("", "Selecione um assunto")] + [(s, s) for s in SUBJECTS], validators=[DataRequired("Escolha um assunto.")])
    message = TextAreaField("Mensagem", filters=[_strip], validators=[DataRequired("Escreva sua mensagem."), Length(10, 2000, "A mensagem deve ter entre 10 e 2000 caracteres.")])
    website = StringField("Não preencha", filters=[_strip])  # honeypot contra robôs


def password_check(_form, field):
    pw = field.data or ""
    if len(pw) < 8:
        raise ValidationError("A senha deve ter pelo menos 8 caracteres.")
    if not (re.search(r"[A-Za-z]", pw) and re.search(r"\d", pw)):
        raise ValidationError("Use letras e números na senha.")


class RegisterForm(FlaskForm):
    name = StringField("Nome completo", filters=[_strip], validators=[DataRequired("Informe seu nome."), Length(2, 120)])
    email = StringField("E-mail", filters=[_strip], validators=[DataRequired("Informe seu e-mail."), Length(max=254), email_check])
    phone = StringField("Telefone / WhatsApp", filters=[_strip], validators=[DataRequired("Informe um telefone."), phone_check])
    password = PasswordField("Senha", validators=[DataRequired("Crie uma senha."), Length(max=128), password_check])
    confirm = PasswordField("Confirmar senha", validators=[DataRequired("Repita a senha."), EqualTo("password", "As senhas não conferem.")])


class LoginForm(FlaskForm):
    email = StringField("E-mail", filters=[_strip], validators=[DataRequired("Informe seu e-mail."), Length(max=254)])
    password = PasswordField("Senha", validators=[DataRequired("Informe sua senha."), Length(max=128)])
    next = HiddenField()


class ProfileForm(FlaskForm):
    name = StringField("Nome completo", filters=[_strip], validators=[DataRequired("Informe seu nome."), Length(2, 120)])
    phone = StringField("Telefone / WhatsApp", filters=[_strip], validators=[DataRequired("Informe um telefone."), phone_check])


class ProductForm(FlaskForm):
    """Cadastro/edição de produto no painel. O preço é digitado em reais e vira centavos inteiros no servidor.

    As opções de categoria são preenchidas pela rota (`set_categories`); o valor enviado é revalidado contra
    elas. A imagem é tratada pela rota (precisa de regra diferente no cadastro e na edição).
    """

    name = StringField("Nome do produto", filters=[_strip], validators=[DataRequired("Informe o nome do produto."), Length(2, 120, "O nome deve ter entre 2 e 120 caracteres.")])
    description = StringField("Descrição curta", filters=[_strip], validators=[DataRequired("Escreva uma descrição curta."), Length(max=400, message="Use até 400 caracteres.")])
    details = TextAreaField("Detalhes (opcional)", filters=[_strip], validators=[Optional(), Length(max=2000, message="Use até 2000 caracteres.")])
    category_id = SelectField("Categoria", choices=[], validate_choice=False, validators=[DataRequired("Escolha uma categoria.")])
    price = StringField("Preço (R$)", filters=[_strip], validators=[DataRequired("Informe o preço do produto.")])
    image_alt = StringField("Texto alternativo da imagem (opcional)", filters=[_strip], validators=[Optional(), Length(max=200, message="Use até 200 caracteres.")])
    is_available = BooleanField("Disponível na loja")
    is_featured = BooleanField("Destacar na página inicial")
    image = FileField("Foto do produto")

    price_cents: int | None = None
    category_value: int | None = None

    def set_categories(self, categories) -> None:
        self.category_id.choices = [(str(c.id), c.name) for c in categories]

    def validate_category_id(self, field) -> None:
        valid = {value for value, _label in self.category_id.choices}
        if (field.data or "") not in valid:
            raise ValidationError("Escolha uma categoria válida.")
        self.category_value = int(field.data)

    def validate_price(self, field) -> None:
        try:
            self.price_cents = parse_brl_to_cents(field.data)
        except ValueError as exc:
            raise ValidationError(str(exc)) from None
