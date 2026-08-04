import os

from fastapi import HTTPException
from sqlalchemy import MetaData, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import (
    Query,
    declarative_base,
    scoped_session,
    sessionmaker,
)
from sqlalchemy.pool import NullPool

from ..config import Config


def _garantir_diretorio_sqlite(url: str) -> None:
    """SQLite abre o arquivo, mas não cria o diretório dele.

    O caminho default é `instance/fluxo.db` e `instance/` não é versionado,
    então um clone novo não tem a pasta e o primeiro boot morre em
    `unable to open database file` antes de qualquer migração.
    """
    if not url.startswith("sqlite"):
        return
    caminho = make_url(url).database
    if not caminho or caminho == ":memory:":
        return
    os.makedirs(os.path.dirname(os.path.abspath(caminho)), exist_ok=True)


def _engine_kwargs(url: str) -> dict:
    """SQLite: sem pool de conexões (NullPool).

    SQLite não se beneficia de pooling e o `QueuePool` default (5+10
    conexões, `pool_timeout=30s`) esgota quando muitas threads de curta
    duração — ex.: as threads de portal do TestClient nos testes, ou o
    executor do agendador — retêm conexões via `scoped_session` sem
    devolvê-las: a próxima aquisição bloqueia 30s e estoura. `NullPool`
    abre/fecha por uso, sem limite, eliminando a exaustão. PostgreSQL
    mantém o pool default.
    """
    if url.startswith("sqlite"):
        return {"poolclass": NullPool, "connect_args": {"check_same_thread": False}}
    return {}


# Nomes determinísticos de constraints/índices: exigidos pelo batch mode do
# Alembic no SQLite e por downgrades que precisam referenciar constraints.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

_garantir_diretorio_sqlite(Config.SQLALCHEMY_DATABASE_URI)
engine = create_engine(
    Config.SQLALCHEMY_DATABASE_URI, **_engine_kwargs(Config.SQLALCHEMY_DATABASE_URI)
)
# ⚠️ SAVEPOINT (begin_nested) NÃO é confiável aqui: o pysqlite emite BEGIN em
# momentos próprios e "commita" inserts fora do controle da Session. A receita
# oficial (isolation_level=None + BEGIN explícito) foi MEDIDA e descartada:
# 22 falhas e o dobro do tempo de suíte — os lotes atômicos de importação
# (importacao-arquivos R8) usam try/except por linha + rollback único, sem
# savepoints, por causa disto.
SessionLocal = scoped_session(sessionmaker(bind=engine, autocommit=False, autoflush=False))

Base = declarative_base(metadata=MetaData(naming_convention=NAMING_CONVENTION))
Base.query = SessionLocal.query_property()


def _query_get_or_404(self: Query, ident, description=None):
    obj = self.get(ident)
    if obj is None:
        if description is None:
            model = self.column_descriptions[0]["type"].__name__
            description = f"{model} not found"
        raise HTTPException(status_code=404, detail=description)
    return obj


Query.get_or_404 = _query_get_or_404


class _DB:
    """Simple helper to mimic the minimal interface of Flask-SQLAlchemy."""

    def __init__(self):
        self.session = SessionLocal

    def create_all(self):
        Base.metadata.create_all(bind=engine)

    def drop_all(self):
        Base.metadata.drop_all(bind=engine)


db = _DB()


def get_db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

