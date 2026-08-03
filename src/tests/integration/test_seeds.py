"""Testes de integração dos seeds de boot.

Cobre a spec `infraestrutura-banco` (change adotar-alembic-migrations):
R5 (SEED_DEMO_DATA controla o seed de demonstração) e
R6 (seed de dado de domínio idempotente e não destrutivo).

Boots rodam em subprocess (engine criado em import-time — ver
test_migracoes.py). Verificações de dados via sqlite3 direto no arquivo.
"""
import sqlite3
from pathlib import Path

import pytest

from .test_migracoes import boot


def _q(db_file: Path, sql: str):
    con = sqlite3.connect(db_file)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def _count(db_file: Path, sql: str) -> int:
    return _q(db_file, sql)[0][0]


@pytest.fixture()
def banco(tmp_path):
    db_file = tmp_path / "seed.db"
    return db_file, f"sqlite:///{db_file}"


# --------------------------------------------------------------------------
# R5 — Seed de demonstração controlado por SEED_DEMO_DATA
# --------------------------------------------------------------------------

def test_demo_ligada_por_default(banco):
    db_file, url = banco
    res = boot(url)
    assert res.returncode == 0, res.stderr[-3000:]

    assert _count(db_file, "SELECT COUNT(*) FROM flc_qualificador") > 0
    assert _count(db_file, "SELECT COUNT(*) FROM flc_lancamento") > 0
    assert _count(db_file, "SELECT COUNT(*) FROM flc_conta_bancaria") > 0


def test_seed_demo_false_nao_cria_dados_de_exemplo(banco):
    db_file, url = banco
    res = boot(url, SEED_DEMO_DATA="false")
    assert res.returncode == 0, res.stderr[-3000:]

    assert _count(db_file, "SELECT COUNT(*) FROM flc_qualificador") == 0
    assert _count(db_file, "SELECT COUNT(*) FROM flc_lancamento") == 0


def test_seed_demo_false_nao_remove_dados_reais(banco):
    db_file, url = banco
    res = boot(url, SEED_DEMO_DATA="false")
    assert res.returncode == 0, res.stderr[-3000:]

    con = sqlite3.connect(db_file)
    con.execute(
        "INSERT INTO flc_qualificador "
        "(num_qualificador, dsc_qualificador, dat_inclusao, ind_status) "
        "VALUES ('9.9.9', 'Rubrica cadastrada pelo usuário', date('now'), 'A')"
    )
    con.commit()
    con.close()

    res = boot(url, SEED_DEMO_DATA="false")
    assert res.returncode == 0, res.stderr[-3000:]

    linhas = _q(
        db_file,
        "SELECT dsc_qualificador FROM flc_qualificador WHERE num_qualificador = '9.9.9'",
    )
    assert linhas == [("Rubrica cadastrada pelo usuário",)], "Dado real não pode ser removido/alterado"
    assert _count(db_file, "SELECT COUNT(*) FROM flc_qualificador") == 1


# --------------------------------------------------------------------------
# R6 — Seed de dado de domínio idempotente e não destrutivo
# --------------------------------------------------------------------------

def test_dominio_semeado_mesmo_sem_demo(banco):
    db_file, url = banco
    res = boot(url, SEED_DEMO_DATA="false")
    assert res.returncode == 0, res.stderr[-3000:]

    tipos = {r[0] for r in _q(db_file, "SELECT dsc_tipo_lancamento FROM flc_tipo_lancamento")}
    assert tipos == {"Entrada", "Saída"}

    origens = {
        r[0] for r in _q(db_file, "SELECT dsc_origem_lancamento FROM flc_origem_lancamento")
    }
    assert origens == {"Manual", "Automático", "Importado"}

    assert (
        _count(db_file, "SELECT COUNT(*) FROM flc_parametro_global WHERE nom_parametro='ipca'")
        == 1
    )


def test_dominio_e_idempotente(banco):
    db_file, url = banco
    for _ in range(2):
        res = boot(url, SEED_DEMO_DATA="false")
        assert res.returncode == 0, res.stderr[-3000:]

    assert _count(db_file, "SELECT COUNT(*) FROM flc_tipo_lancamento") == 2
    assert _count(db_file, "SELECT COUNT(*) FROM flc_origem_lancamento") == 3
    params = _q(
        db_file,
        "SELECT nom_parametro, COUNT(*) FROM flc_parametro_global "
        "GROUP BY nom_parametro HAVING COUNT(*) > 1",
    )
    assert params == [], f"Parâmetros duplicados após reboot: {params}"


def test_dominio_preserva_descricao_editada_pelo_usuario(banco):
    db_file, url = banco
    res = boot(url, SEED_DEMO_DATA="false")
    assert res.returncode == 0, res.stderr[-3000:]

    con = sqlite3.connect(db_file)
    con.execute(
        "UPDATE flc_parametro_global "
        "SET dsc_parametro = 'IPCA revisado pelo usuário' WHERE nom_parametro = 'ipca'"
    )
    con.commit()
    con.close()

    res = boot(url, SEED_DEMO_DATA="false")
    assert res.returncode == 0, res.stderr[-3000:]

    linhas = _q(
        db_file,
        "SELECT dsc_parametro FROM flc_parametro_global WHERE nom_parametro = 'ipca'",
    )
    assert linhas == [("IPCA revisado pelo usuário",)], (
        "Seed de domínio não pode sobrescrever edições do usuário"
    )


# --------------------------------------------------------------------------
# DEMO_MODE — como o administrador inicial nasce
# --------------------------------------------------------------------------

def test_admin_nasce_com_troca_obrigatoria(banco):
    """Comportamento padrão: instalação real exige trocar a senha inicial."""
    db_file, url = banco
    res = boot(url, SEED_DEMO_DATA="false")
    assert res.returncode == 0, res.stderr[-3000:]

    assert _q(
        db_file,
        "SELECT ind_troca_senha FROM flc_usuario WHERE nom_usuario = 'admin'",
    ) == [("S",)]


def test_admin_em_modo_demo_nasce_sem_troca_obrigatoria(banco):
    """Numa demo pública a troca obrigatória trancaria o acesso: o primeiro
    visitante definiria a senha e os seguintes ficariam de fora."""
    db_file, url = banco
    # SEED_DEMO_DATA=true junto: "modo demo com dados de demo" é a
    # combinação legítima. A inversa (demo sobre dados reais) passou a
    # abortar o boot — infraestrutura-banco R10.
    res = boot(url, SEED_DEMO_DATA="true", DEMO_MODE="true")
    assert res.returncode == 0, res.stderr[-3000:]

    assert _q(
        db_file,
        "SELECT ind_troca_senha FROM flc_usuario WHERE nom_usuario = 'admin'",
    ) == [("N",)]
