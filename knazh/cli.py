"""Comandos de linha: flask --app wsgi <comando>."""
from __future__ import annotations

import os
import sys
from types import SimpleNamespace

import click
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from wtforms.validators import ValidationError

from .demo_data import remove_demo, seed_demo
from .extensions import db
from .forms import EMAIL_RE, password_check
from .migrations import run_migrations
from .models import ContactMessage, Customer, Order
from .services import admin_users


def register_cli(app):
    @app.cli.command("init-db")
    def init_db():
        """Cria as tabelas que ainda não existem (não apaga dados)."""
        db.create_all()
        click.echo("Banco inicializado.")

    @app.cli.command("migrate-db")
    def migrate_db():
        """Atualiza o esquema de um banco existente (idempotente, não apaga dados). Faça backup antes."""
        for name, result in run_migrations(db.engine):
            label = {"adicionada": "coluna adicionada", "ja-existe": "já estava aplicada",
                     "sem-tabela": "tabela ainda não existe (será criada pelo init-db)"}.get(result, result)
            click.echo(f"  {name}: {label}")
        db.create_all()  # tabelas novas, se houver; nunca altera nem apaga as existentes
        click.echo("Migração concluída.")

    def _find_customer(email: str) -> Customer:
        normalized = (email or "").strip().lower()
        customer = db.session.scalar(select(Customer).where(Customer.email == normalized)) if normalized else None
        if customer is None:
            raise click.ClickException(f"Nenhuma conta encontrada com o e-mail «{normalized}». "
                                       "A pessoa precisa criar a conta no site antes de ser promovida.")
        return customer

    @app.cli.command("promote-admin")
    @click.argument("email")
    @click.option("--manager", is_flag=True, help="Também concede a permissão de gerenciar administradores (use para recuperar o acesso).")
    def promote_admin(email, manager):
        """Concede acesso de administrador a uma conta JÁ EXISTENTE (somente por linha de comando)."""
        customer = _find_customer(email)
        if customer.is_admin and (customer.can_manage_admins or not manager):
            click.echo(f"{customer.email} já é administradora{' e gerencia administradores' if customer.can_manage_admins else ''}. Nada a fazer.")
            return
        customer.is_admin = True
        customer.can_manage_admins = bool(manager) or customer.can_manage_admins
        db.session.commit()
        extra = " e pode gerenciar administradores" if customer.can_manage_admins else ""
        click.echo(f"Pronto: {customer.email} agora é administradora{extra}.")

    @app.cli.command("revoke-admin")
    @click.argument("email")
    def revoke_admin(email):
        """Remove o acesso de administrador de uma conta (ela continua como cliente comum).

        Recusa remover a ÚLTIMA conta que gerencia administradores (use `promote-admin EMAIL --manager` em outra conta antes)."""
        customer = _find_customer(email)
        if not customer.is_admin:
            click.echo(f"{customer.email} não é administradora. Nada a fazer.")
            return
        if customer.can_manage_admins and admin_users.manager_count() <= 1:
            raise click.ClickException(f"{customer.email} é a única conta que gerencia administradores e não pode ser removida. "
                                       "Conceda antes a permissão a outra conta: promote-admin EMAIL --manager")
        customer.is_admin = False
        customer.can_manage_admins = False
        db.session.commit()
        click.echo(f"Pronto: {customer.email} não é mais administradora.")

    @app.cli.command("provision-initial-admin")
    @click.option("--email", default=None, help="E-mail do administrador inicial (padrão: INITIAL_ADMIN_EMAIL).")
    @click.option("--name", envvar="INITIAL_ADMIN_NAME", default="Administração KNAZH", show_default=True)
    @click.option("--yes", is_flag=True, help="Não pedir confirmação ao promover uma conta que já existe.")
    def provision_initial_admin(email, name, yes):
        """Cria/promove o administrador inicial (com permissão de gerenciar administradores). Idempotente e seguro.

        A senha NUNCA vai em argumento nem no código: use a variável de ambiente INITIAL_ADMIN_PASSWORD (ou digite no
        prompt, oculto, se estiver num terminal). Se a conta já existe, a senha e os dados dela NÃO são alterados."""
        email = (email or app.config["INITIAL_ADMIN_EMAIL"] or "").strip().lower()
        if not email or not EMAIL_RE.match(email):
            raise click.ClickException("Informe um e-mail válido (--email ou INITIAL_ADMIN_EMAIL).")
        customer = db.session.scalar(select(Customer).where(Customer.email == email))
        if customer is not None:
            if customer.is_admin and customer.can_manage_admins:
                click.echo(f"{email}: a conta já existe e já gerencia administradores. Nada a fazer (a senha não foi tocada).")
                return
            click.echo(f"{email}: a conta já existe (criada em {customer.created_at:%d/%m/%Y}, nome «{customer.name}»). "
                       "A senha atual será mantida.")
            if not yes and not click.confirm("Esta conta é mesmo da pessoa responsável pela loja? Promover a administradora com gestão de administradores?"):
                raise click.Abort()
            customer.is_admin = True
            customer.can_manage_admins = True
            db.session.commit()
            click.echo(f"Pronto: {email} agora é administradora e gerencia administradores.")
            return
        password = os.environ.get("INITIAL_ADMIN_PASSWORD", "")
        if not password:
            if not sys.stdin.isatty():
                raise click.ClickException("Defina INITIAL_ADMIN_PASSWORD no ambiente (não vai para o código) ou rode num terminal para digitá-la.")
            password = click.prompt("Senha do administrador inicial", hide_input=True, confirmation_prompt=True)
        try:
            password_check(None, SimpleNamespace(data=password))
        except ValidationError as exc:
            raise click.ClickException(f"Senha recusada: {exc}")
        customer = Customer(name=name.strip() or "Administração KNAZH", email=email, phone="", is_admin=True, can_manage_admins=True)
        customer.set_password(password)
        db.session.add(customer)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            raise click.ClickException("A conta foi criada por outro processo agora há pouco. Rode o comando de novo para conferir a situação.")
        click.echo(f"Pronto: conta criada para {email} como administradora (gerencia administradores). "
                   "Remova INITIAL_ADMIN_PASSWORD do ambiente e troque a senha se ela foi compartilhada.")

    @app.cli.command("seed-demo")
    def seed_demo_cmd():
        """Carrega/atualiza o catálogo de DEMONSTRAÇÃO (preços fictícios)."""
        db.create_all()
        r = seed_demo()
        click.echo(f"Dados de demonstração: {r['criados']} criados, {r['atualizados']} atualizados.")

    @app.cli.command("remove-demo")
    def remove_demo_cmd():
        """Remove somente os produtos marcados como demonstração."""
        click.echo(f"{remove_demo()} produtos de demonstração removidos.")

    @app.cli.command("list-orders")
    @click.option("--limit", default=20)
    def list_orders(limit):
        """Lista os pedidos mais recentes."""
        for o in db.session.scalars(select(Order).order_by(Order.id.desc()).limit(limit)):
            click.echo(f"{o.number}  {o.created_at:%d/%m/%Y %H:%M}  {o.status_label:<22} {o.customer_name}  {o.total_cents/100:.2f}")

    @app.cli.command("list-messages")
    @click.option("--limit", default=20)
    def list_messages(limit):
        """Lista as mensagens do formulário de contato."""
        for m in db.session.scalars(select(ContactMessage).order_by(ContactMessage.id.desc()).limit(limit)):
            click.echo(f"#{m.id} {m.created_at:%d/%m/%Y %H:%M} [{m.email_status}] {m.name} <{m.email}> — {m.subject}\n    {m.message[:200]}")
