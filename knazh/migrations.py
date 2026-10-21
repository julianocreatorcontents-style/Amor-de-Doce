"""Migrações explícitas e idempotentes do banco (sem Alembic).

`db.create_all()` só cria tabelas ausentes: ele NÃO adiciona colunas novas a tabelas que já existem.
Por isso cada alteração de esquema em bancos já em uso entra aqui, usando introspecção para checar o estado
atual antes de alterar. Rodar mais de uma vez é seguro: o que já existe é ignorado e nenhum dado é apagado.

Uso: flask --app wsgi migrate-db   (faça backup do banco antes — veja o README).
"""
from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def _columns(engine: Engine, table: str) -> set[str] | None:
    insp = inspect(engine)
    if table not in insp.get_table_names():
        return None
    return {c["name"] for c in insp.get_columns(table)}


def add_customer_is_admin(engine: Engine) -> str:
    """Adiciona customers.is_admin (BOOLEAN NOT NULL DEFAULT false). Contas existentes ficam como clientes comuns.

    Retorna 'adicionada', 'ja-existe' ou 'sem-tabela' (tabela ainda inexistente: create_all a criará já com a coluna).
    """
    cols = _columns(engine, "customers")
    if cols is None:
        return "sem-tabela"
    if "is_admin" in cols:
        return "ja-existe"
    default = "0" if engine.dialect.name == "sqlite" else "FALSE"
    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE customers ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT {default}"))
    return "adicionada"


def add_customer_can_manage_admins(engine: Engine) -> str:
    """Adiciona customers.can_manage_admins (BOOLEAN NOT NULL DEFAULT false).

    Contas existentes ficam sem a permissão. Para não deixar um banco antigo sem NINGUÉM capaz de gerenciar
    administradores, se já houver administradores e nenhum gestor, TODOS os administradores atuais passam a gestores
    (comportamento anterior: qualquer administrador era de confiança total). Depois disso o painel permite ajustar.
    """
    cols = _columns(engine, "customers")
    if cols is None:
        return "sem-tabela"
    if "can_manage_admins" in cols:
        return "ja-existe"
    default = "0" if engine.dialect.name == "sqlite" else "FALSE"
    true = "1" if engine.dialect.name == "sqlite" else "TRUE"
    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE customers ADD COLUMN can_manage_admins BOOLEAN NOT NULL DEFAULT {default}"))
        if "is_admin" in cols:
            conn.execute(text(f"UPDATE customers SET can_manage_admins = {true} WHERE is_admin = {true}"))
    return "adicionada"


# Ordem importa: novas migrações entram no fim da lista.
MIGRATIONS = [
    ("customers.is_admin", add_customer_is_admin),
    ("customers.can_manage_admins", add_customer_can_manage_admins),
]


def run_migrations(engine: Engine) -> list[tuple[str, str]]:
    """Executa todas as migrações pendentes. Retorna [(nome, resultado)]."""
    return [(name, fn(engine)) for name, fn in MIGRATIONS]
