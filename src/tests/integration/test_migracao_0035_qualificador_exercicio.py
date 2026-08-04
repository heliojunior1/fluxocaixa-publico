"""Migração 0035: qualificador por exercício e identidade estável (R25–R27).

Backfill: toda linha pré-existente ganha `num_ano_exercicio` (ano corrente do
upgrade — vira o plano base) e `cod_rubrica_raiz` = próprio seq (o código era
único global, então o histórico nasce costurado de graça — D-B da concepção).
SEM replicação e SEM repoint (decisão D1 do design): registro continua
apontando para o qualificador que já apontava.
"""
import sqlite3
from datetime import date

from sqlalchemy import create_engine, inspect

from alembic import command

from .test_migracoes import _cfg


def _preparar_0034(tmp_path):
    db_file = tmp_path / "qualificador_exercicio.db"
    url = f"sqlite:///{db_file}"
    command.upgrade(_cfg(url), "0034")
    con = sqlite3.connect(db_file)
    con.executemany(
        "INSERT INTO flc_qualificador "
        "(seq_qualificador, num_qualificador, dsc_qualificador, ind_status, dat_inclusao) "
        "VALUES (?, ?, ?, 'A', date('now'))",
        [
            (901, "8.1", "Bloco Legado"),
            (902, "8.1.1", "Folha Legada"),
        ],
    )
    con.commit()
    con.close()
    return db_file, url


def test_backfill_preenche_ano_e_raiz(tmp_path):
    db_file, url = _preparar_0034(tmp_path)
    command.upgrade(_cfg(url), "0035")

    con = sqlite3.connect(db_file)
    linhas = con.execute(
        "SELECT seq_qualificador, num_ano_exercicio, cod_rubrica_raiz "
        "FROM flc_qualificador ORDER BY seq_qualificador"
    ).fetchall()
    con.close()

    assert linhas == [
        (901, date.today().year, 901),
        (902, date.today().year, 902),
    ]


def test_unicidade_passa_a_ser_por_exercicio(tmp_path):
    """O mesmo código convive em exercícios diferentes; no mesmo exercício,
    entre ativos, é recusado pelo índice único parcial."""
    db_file, url = _preparar_0034(tmp_path)
    command.upgrade(_cfg(url), "0035")

    con = sqlite3.connect(db_file)
    # mesmo código em OUTRO exercício: aceito
    con.execute(
        "INSERT INTO flc_qualificador "
        "(seq_qualificador, num_qualificador, dsc_qualificador, ind_status, "
        " dat_inclusao, num_ano_exercicio, cod_rubrica_raiz) "
        "VALUES (903, '8.1', 'Bloco Ano Novo', 'A', date('now'), 2071, 901)"
    )
    con.commit()
    # mesmo código no MESMO exercício, ativo: recusado
    try:
        con.execute(
            "INSERT INTO flc_qualificador "
            "(seq_qualificador, num_qualificador, dsc_qualificador, ind_status, "
            " dat_inclusao, num_ano_exercicio, cod_rubrica_raiz) "
            "VALUES (904, '8.1', 'Duplicata', 'A', date('now'), 2071, 904)"
        )
        con.commit()
        duplicou = True
    except sqlite3.IntegrityError:
        duplicou = False
    # inativo com o mesmo código no mesmo exercício: aceito (índice parcial)
    con.execute(
        "INSERT INTO flc_qualificador "
        "(seq_qualificador, num_qualificador, dsc_qualificador, ind_status, "
        " dat_inclusao, num_ano_exercicio, cod_rubrica_raiz) "
        "VALUES (905, '8.1', 'Inativa Convive', 'I', date('now'), 2071, 905)"
    )
    con.commit()
    con.close()

    assert not duplicou, "o índice único parcial deveria recusar a duplicata ativa"


def test_downgrade_remove_colunas_e_restaura_unique_global(tmp_path):
    db_file, url = _preparar_0034(tmp_path)
    command.upgrade(_cfg(url), "0035")
    command.downgrade(_cfg(url), "0034")

    engine = create_engine(url)
    try:
        colunas = {c['name'] for c in inspect(engine).get_columns('flc_qualificador')}
    finally:
        engine.dispose()
    assert 'num_ano_exercicio' not in colunas
    assert 'cod_rubrica_raiz' not in colunas

    con = sqlite3.connect(db_file)
    try:
        con.execute(
            "INSERT INTO flc_qualificador "
            "(seq_qualificador, num_qualificador, dsc_qualificador, ind_status, dat_inclusao) "
            "VALUES (906, '8.1', 'Duplicata Global', 'A', date('now'))"
        )
        con.commit()
        duplicou = True
    except sqlite3.IntegrityError:
        duplicou = False
    con.close()
    assert not duplicou, "a unique global deveria voltar no downgrade"
