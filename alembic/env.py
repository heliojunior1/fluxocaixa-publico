"""Ambiente Alembic do FluxoDeCaixa.

Resolve a URL do banco com a mesma precedência da aplicação
(DATABASE_URL → SQLite em instance/fluxo.db) e habilita batch mode
no SQLite (render_as_batch), exigido para ALTER TABLE nesse dialeto.
"""
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(BASE_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from fluxocaixa.config import Config as AppConfig  # noqa: E402
from fluxocaixa.models import Base  # noqa: E402  (importa todos os models)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# Permite override por testes (cfg.set_main_option) e por -x sqlalchemy.url;
# sem override, usa a mesma URL da aplicação.
if not config.get_main_option("sqlalchemy.url"):
    config.set_main_option(
        "sqlalchemy.url", AppConfig.SQLALCHEMY_DATABASE_URI.replace("%", "%%")
    )

target_metadata = Base.metadata


def _render_as_batch(url_ou_conexao) -> bool:
    if hasattr(url_ou_conexao, "dialect"):
        return url_ou_conexao.dialect.name == "sqlite"
    return str(url_ou_conexao).startswith("sqlite")


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=_render_as_batch(url),
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=_render_as_batch(connection),
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
