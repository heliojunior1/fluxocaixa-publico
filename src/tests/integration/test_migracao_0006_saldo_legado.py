"""Migração 0006: saldo legado → fundo GERAL + DROP da tabela (spec R17).

Cenários: dados legados migram para GERAL preservando valores; banco sem
saldos legados não cria GERAL; downgrade recria a tabela e repovoa do GERAL.
"""
import sqlite3

import pytest
from sqlalchemy import create_engine, inspect

from alembic import command

from .test_migracoes import _cfg


def _preparar_0005_com_saldos(tmp_path, com_saldos: bool):
    """Banco na revisão 0005 (legado ainda existe), opcionalmente com saldos."""
    db_file = tmp_path / ("com.db" if com_saldos else "vazio.db")
    url = f"sqlite:///{db_file}"
    command.upgrade(_cfg(url), "0005")
    con = sqlite3.connect(db_file)
    con.executescript(
        """
        INSERT INTO flc_conta_bancaria (seq_conta, cod_banco, num_agencia, num_conta, dsc_conta, ind_status, dat_cadastro)
        VALUES (1, '111', '0001', 'A-1', 'Conta 1', 'A', date('now')),
               (2, '222', '0002', 'B-2', 'Conta 2', 'A', date('now'));
        """
    )
    if com_saldos:
        con.executescript(
            """
            INSERT INTO flc_saldo_conta (seq_conta, dat_saldo, val_saldo, dat_inclusao, cod_pessoa_inclusao)
            VALUES (1, '2025-03-10', 1000.00, date('now'), 1),
                   (2, '2025-03-10', 2000.00, date('now'), 1),
                   (1, '2025-03-11', 1500.00, date('now'), 1);
            """
        )
    con.commit()
    con.close()
    return db_file, url


def test_dados_legados_migram_para_geral(tmp_path):
    db_file, url = _preparar_0005_com_saldos(tmp_path, com_saldos=True)
    command.upgrade(_cfg(url), "head")

    con = sqlite3.connect(db_file)
    # tabela legada removida
    tabelas = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    assert "flc_saldo_conta" not in tabelas

    # fundo GERAL criado, aprovado, tipo MANUAL
    fundo = con.execute(
        "SELECT f.ind_pendente_revisao, t.txt_sigla "
        "FROM flc_fundo f JOIN flc_tipo_origem_saldo t ON t.seq_tipo_origem_saldo = f.seq_tipo_origem "
        "WHERE f.cod_fundo = 'GERAL'"
    ).fetchone()
    assert fundo == ('N', 'MANUAL')

    # 3 saldos migrados com os mesmos valores
    saldos = con.execute(
        "SELECT s.seq_conta, s.dat_saldo, s.val_saldo FROM flc_saldo_conta_fundo s "
        "JOIN flc_fundo f ON f.seq_fundo = s.seq_fundo "
        "WHERE f.cod_fundo = 'GERAL' AND s.ind_status = 'A' ORDER BY s.seq_conta, s.dat_saldo"
    ).fetchall()
    assert saldos == [(1, '2025-03-10', 1000.0), (1, '2025-03-11', 1500.0), (2, '2025-03-10', 2000.0)]
    con.close()


def test_banco_sem_saldos_nao_cria_geral(tmp_path):
    db_file, url = _preparar_0005_com_saldos(tmp_path, com_saldos=False)
    command.upgrade(_cfg(url), "head")

    con = sqlite3.connect(db_file)
    tabelas = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    assert "flc_saldo_conta" not in tabelas
    geral = con.execute("SELECT COUNT(*) FROM flc_fundo WHERE cod_fundo = 'GERAL'").fetchone()[0]
    assert geral == 0
    con.close()


def test_downgrade_repovoa_do_geral(tmp_path):
    db_file, url = _preparar_0005_com_saldos(tmp_path, com_saldos=True)
    command.upgrade(_cfg(url), "head")
    command.downgrade(_cfg(url), "0005")

    insp = inspect(create_engine(url))
    assert "flc_saldo_conta" in insp.get_table_names()
    con = sqlite3.connect(db_file)
    linhas = con.execute(
        "SELECT seq_conta, dat_saldo, val_saldo FROM flc_saldo_conta ORDER BY seq_conta, dat_saldo"
    ).fetchall()
    assert linhas == [(1, '2025-03-10', 1000.0), (1, '2025-03-11', 1500.0), (2, '2025-03-10', 2000.0)]
    con.close()
