"""Preparação do banco no boot: migrações Alembic e flags de ambiente.

Comportamento (spec infraestrutura-banco, change adotar-alembic-migrations):

- `AUTO_MIGRATE` (default true): executa `alembic upgrade head` no boot.
  Com false, o boot não altera o schema — falha com instrução se o banco
  ainda não estiver sob controle do Alembic.
- Instalação legada (tabelas flc_* criadas pelo antigo `create_all()`,
  sem `alembic_version`): aborta com a instrução exata de adoção
  (`alembic stamp head`), sem tocar no banco.
"""
import os

from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import inspect

# `env_flag` é reexportado: vive em `config` (módulo leve), mas metade do
# projeto já o importa daqui.
from .config import BASE_DIR, Config, env_flag  # noqa: F401
from .models.base import engine


def alembic_config() -> AlembicConfig:
    cfg = AlembicConfig(os.path.join(BASE_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(BASE_DIR, "alembic"))
    # '%' escapado: ConfigParser trata '%' como interpolação
    cfg.set_main_option(
        "sqlalchemy.url", Config.SQLALCHEMY_DATABASE_URI.replace("%", "%%")
    )
    return cfg


def preparar_banco() -> None:
    inspector = inspect(engine)
    sob_controle = inspector.has_table("alembic_version")
    tem_tabelas_negocio = inspector.has_table("flc_lancamento")

    if not env_flag("AUTO_MIGRATE", True):
        if not sob_controle:
            raise RuntimeError(
                "AUTO_MIGRATE=false e o banco não está sob controle do Alembic. "
                "Execute 'alembic upgrade head' para criar/atualizar o schema "
                "e reinicie a aplicação."
            )
        return

    if tem_tabelas_negocio and not sob_controle:
        raise RuntimeError(
            "Instalação existente detectada: o banco possui tabelas flc_* mas "
            "não está sob controle do Alembic. O schema atual equivale à "
            "baseline — execute 'alembic stamp 0001' uma única vez e reinicie "
            "(as migrações posteriores serão aplicadas no boot). "
            "Nada foi alterado no banco."
        )

    command.upgrade(alembic_config(), "head")


def resetar_banco() -> None:
    """Apaga e recria todo o schema (uso de desenvolvimento — /recreate-db)."""
    from .models.base import Base

    Base.metadata.drop_all(bind=engine)
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP TABLE IF EXISTS alembic_version")
    command.upgrade(alembic_config(), "head")
