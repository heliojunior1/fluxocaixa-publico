"""Migração 0004: dedupe de contas bancárias + unique constraint.

Spec cadastros-nucleo R5 — instalações legadas podem ter contas duplicadas
(banco, agência, conta) criadas pela importação; a migração mantém a de menor
seq_conta, reaponta lançamentos e saldos, e então cria a constraint.
"""
import sqlite3

import pytest
from sqlalchemy import create_engine, inspect

from alembic import command

from .test_migracoes import _cfg


@pytest.fixture()
def banco_com_duplicatas(tmp_path):
    """Banco na revisão 0003 com contas duplicadas e dados apontando para elas."""
    db_file = tmp_path / "dedupe.db"
    url = f"sqlite:///{db_file}"
    command.upgrade(_cfg(url), "0003")

    con = sqlite3.connect(db_file)
    con.executescript(
        """
        INSERT INTO flc_conta_bancaria (seq_conta, cod_banco, num_agencia, num_conta, dsc_conta, ind_status, dat_cadastro)
        VALUES (1, '001', '1234', '56789-0', 'Original', 'A', date('now')),
               (7, '001', '1234', '56789-0', 'Duplicada', 'A', date('now')),
               (9, '104', '9999', '11111-1', 'Sem duplicata', 'A', date('now'));

        INSERT INTO flc_tipo_lancamento (cod_tipo_lancamento, dsc_tipo_lancamento) VALUES (1, 'Entrada');
        INSERT INTO flc_origem_lancamento (cod_origem_lancamento, dsc_origem_lancamento, ind_status)
        VALUES (1, 'Manual', 'A');
        INSERT INTO flc_qualificador (seq_qualificador, num_qualificador, dsc_qualificador, dat_inclusao, ind_status)
        VALUES (1, '1.1.1', 'Rubrica', date('now'), 'A');

        INSERT INTO flc_lancamento (dat_lancamento, seq_qualificador, val_lancamento,
                                    cod_tipo_lancamento, cod_origem_lancamento,
                                    dat_inclusao, cod_pessoa_inclusao, ind_status, seq_conta)
        VALUES ('2026-07-01', 1, 100, 1, 1, date('now'), 1, 'A', 1),
               ('2026-07-02', 1, 200, 1, 1, date('now'), 1, 'A', 7);

        INSERT INTO flc_saldo_conta (seq_conta, dat_saldo, val_saldo, dat_inclusao, cod_pessoa_inclusao)
        VALUES (1, '2026-07-01', 1000, date('now'), 1),
               (7, '2026-07-02', 2000, date('now'), 1);
        """
    )
    con.commit()
    con.close()
    return db_file, url


def test_migracao_deduplica_e_reaponta(banco_com_duplicatas):
    db_file, url = banco_com_duplicatas
    command.upgrade(_cfg(url), "0004")

    con = sqlite3.connect(db_file)
    contas = con.execute(
        "SELECT seq_conta FROM flc_conta_bancaria WHERE cod_banco='001' AND num_agencia='1234' AND num_conta='56789-0'"
    ).fetchall()
    assert contas == [(1,)], f"Deveria restar só a conta seq 1: {contas}"

    lancs = con.execute("SELECT DISTINCT seq_conta FROM flc_lancamento").fetchall()
    assert lancs == [(1,)], f"Lançamentos deveriam apontar para a conta 1: {lancs}"

    saldos = con.execute("SELECT seq_conta, val_saldo FROM flc_saldo_conta ORDER BY dat_saldo").fetchall()
    assert saldos == [(1, 1000), (1, 2000)], saldos

    total = con.execute("SELECT COUNT(*) FROM flc_conta_bancaria").fetchone()[0]
    assert total == 2, "Conta sem duplicata deve permanecer"
    con.close()


def test_constraint_impede_nova_duplicata(banco_com_duplicatas):
    db_file, url = banco_com_duplicatas
    command.upgrade(_cfg(url), "0004")

    insp = inspect(create_engine(url))
    uniques = insp.get_unique_constraints("flc_conta_bancaria")
    colunas = [tuple(u["column_names"]) for u in uniques]
    assert ("cod_banco", "num_agencia", "num_conta") in colunas, colunas

    con = sqlite3.connect(db_file)
    with pytest.raises(sqlite3.IntegrityError):
        con.execute(
            "INSERT INTO flc_conta_bancaria (cod_banco, num_agencia, num_conta, dsc_conta) "
            "VALUES ('001', '1234', '56789-0', 'Nova duplicata')"
        )
    con.close()
