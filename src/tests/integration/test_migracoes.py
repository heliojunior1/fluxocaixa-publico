"""Testes de integração das migrações Alembic.

Cobre a spec `infraestrutura-banco` (change adotar-alembic-migrations):
R1 (upgrade/downgrade), R2 (anti-deriva), R3 (AUTO_MIGRATE no boot),
R4 (adoção em instalação legada) e R7 (naming convention).

Os testes de boot rodam a aplicação em subprocess porque o engine do
SQLAlchemy é criado em import-time a partir de DATABASE_URL — subprocess
garante ambiente limpo por cenário.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect

from alembic import command
from alembic.config import Config as AlembicConfig

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"

BOOT_CODE = "from fluxocaixa import create_app; create_app()"


def _run_py(code: str, env_extra: dict, timeout: int = 300) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env.pop("DATABASE_URL", None)
    env["PYTHONPATH"] = str(SRC)
    env.update(env_extra)
    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
        cwd=str(ROOT),
    )


def boot(db_url: str, **env_extra) -> subprocess.CompletedProcess:
    return _run_py(BOOT_CODE, {"DATABASE_URL": db_url, **env_extra})


def _cfg(db_url: str) -> AlembicConfig:
    ini = ROOT / "alembic.ini"
    assert ini.exists(), "alembic.ini não encontrado na raiz do projeto"
    cfg = AlembicConfig(str(ini))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


@pytest.fixture()
def db_url(tmp_path):
    return f"sqlite:///{tmp_path / 'mig.db'}"


def _criar_banco_legado(db_url: str) -> None:
    """Simula instalação pré-Alembic: schema da baseline SEM alembic_version."""
    command.upgrade(_cfg(db_url), "0001")
    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP TABLE alembic_version")


# --------------------------------------------------------------------------
# R1 — Schema versionado por migrações Alembic
# --------------------------------------------------------------------------

def test_upgrade_head_cria_schema_completo(db_url):
    command.upgrade(_cfg(db_url), "head")

    insp = inspect(create_engine(db_url))
    tabelas = set(insp.get_table_names())

    from fluxocaixa.models import Base

    esperadas = {t.name for t in Base.metadata.sorted_tables}
    faltantes = esperadas - tabelas
    assert not faltantes, f"Tabelas ausentes após upgrade head: {faltantes}"
    assert "alembic_version" in tabelas


def test_downgrade_base_remove_todas_as_tabelas(db_url):
    cfg = _cfg(db_url)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")

    insp = inspect(create_engine(db_url))
    restantes = [t for t in insp.get_table_names() if t.startswith("flc_")]
    assert restantes == [], f"Tabelas flc_* remanescentes após downgrade base: {restantes}"


# --------------------------------------------------------------------------
# R2 — Ausência de deriva entre models e migrações
# --------------------------------------------------------------------------

def test_sem_deriva_entre_models_e_migracoes(db_url):
    command.upgrade(_cfg(db_url), "head")

    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from fluxocaixa.models import Base

    engine = create_engine(db_url)
    with engine.connect() as conn:
        ctx = MigrationContext.configure(
            conn, opts={"compare_type": True, "render_as_batch": True}
        )
        diffs = compare_metadata(ctx, Base.metadata)

    assert diffs == [], f"Deriva entre models e migrações: {diffs}"


# --------------------------------------------------------------------------
# R3 — Auto-migração no boot controlada por AUTO_MIGRATE
# --------------------------------------------------------------------------

def test_boot_com_banco_vazio_e_auto_migrate_default(tmp_path):
    url = f"sqlite:///{tmp_path / 'boot.db'}"
    res = boot(url)
    assert res.returncode == 0, f"Boot falhou:\n{res.stderr[-3000:]}"

    insp = inspect(create_engine(url))
    tabelas = set(insp.get_table_names())
    assert "flc_lancamento" in tabelas
    assert "alembic_version" in tabelas


def test_boot_nao_altera_schema_com_auto_migrate_false(tmp_path):
    db_file = tmp_path / "semmig.db"
    url = f"sqlite:///{db_file}"
    res = boot(url, AUTO_MIGRATE="false")

    saida = res.stdout + res.stderr
    assert res.returncode != 0, "Boot deveria abortar: schema ausente e AUTO_MIGRATE=false"
    assert "alembic upgrade head" in saida, "Mensagem deve orientar a executar alembic upgrade head"

    if db_file.exists():
        insp = inspect(create_engine(url))
        assert insp.get_table_names() == [], "Nenhuma tabela deveria ser criada"


# --------------------------------------------------------------------------
# R4 — Adoção segura em instalação legada
# --------------------------------------------------------------------------

def test_instalacao_legada_aborta_com_instrucao_stamp(tmp_path):
    url = f"sqlite:///{tmp_path / 'legado.db'}"
    _criar_banco_legado(url)

    res = boot(url)
    saida = res.stdout + res.stderr
    assert res.returncode != 0, "Boot deveria abortar em instalação legada sem alembic_version"
    assert "alembic stamp 0001" in saida, "Mensagem deve conter o comando exato de adoção"

    insp = inspect(create_engine(url))
    assert "alembic_version" not in insp.get_table_names(), "Boot não deveria alterar o banco"


def test_apos_stamp_da_baseline_boot_migra_ate_head(tmp_path):
    url = f"sqlite:///{tmp_path / 'legado2.db'}"
    _criar_banco_legado(url)

    # Adoção: marca a baseline; o boot aplica as migrações posteriores (0002+)
    command.stamp(_cfg(url), "0001")

    res = boot(url)
    assert res.returncode == 0, f"Boot deveria prosseguir após stamp:\n{res.stderr[-3000:]}"

    insp = inspect(create_engine(url))
    assert "flc_usuario" in insp.get_table_names(), (
        "Migrações posteriores à baseline (0002) deveriam ter sido aplicadas no boot"
    )


# --------------------------------------------------------------------------
# R7 — Naming convention e compatibilidade
# --------------------------------------------------------------------------

def test_metadata_define_naming_convention():
    from fluxocaixa.models import Base

    convention = Base.metadata.naming_convention
    for chave in ("ix", "uq", "ck", "fk", "pk"):
        assert chave in convention, f"Naming convention sem padrão para '{chave}'"


def test_constraints_migradas_seguem_naming_convention(db_url):
    command.upgrade(_cfg(db_url), "head")

    insp = inspect(create_engine(db_url))
    uniques = insp.get_unique_constraints("flc_rubrica_formula")
    nomes = [u.get("name") or "" for u in uniques]
    assert any(n.startswith("uq_flc_rubrica_formula") for n in nomes), (
        f"Unique constraint sem nome da convenção: {nomes}"
    )
