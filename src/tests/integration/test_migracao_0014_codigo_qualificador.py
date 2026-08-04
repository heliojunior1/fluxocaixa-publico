"""Migração 0014: num_qualificador comporta 6 níveis (spec cadastros-nucleo R12).

⚠️ Estes testes rodam em **SQLite**, que NÃO impõe tamanho de VARCHAR. Um teste
que só gravasse e relesse o código passaria mesmo com a coluna curta — é
justamente por isso que o bug sobreviveu até aqui. Por isso o que se afere é o
**tipo declarado** no schema, que é o que PostgreSQL cobra, e não apenas o
round-trip do valor.
"""
import sqlite3

from sqlalchemy import create_engine, inspect

from alembic import command

from .test_migracoes import _cfg

CODIGO_6_NIVEIS = "1.100.200.300.400.500"  # 21 caracteres


def _tamanho_declarado(url: str) -> int:
    engine = create_engine(url)
    try:
        for coluna in inspect(engine).get_columns('flc_qualificador'):
            if coluna['name'] == 'num_qualificador':
                return coluna['type'].length
    finally:
        engine.dispose()
    raise AssertionError("coluna num_qualificador não encontrada")


def _preparar_0013(tmp_path):
    db_file = tmp_path / "qualificador.db"
    url = f"sqlite:///{db_file}"
    command.upgrade(_cfg(url), "0013")
    con = sqlite3.connect(db_file)
    con.execute(
        "INSERT INTO flc_qualificador "
        "(seq_qualificador, num_qualificador, dsc_qualificador, ind_status, dat_inclusao) "
        "VALUES (801, '1.7', 'Rubrica curta', 'A', date('now'))"
    )
    con.commit()
    con.close()
    return db_file, url


def test_antes_da_migracao_a_coluna_nao_comporta_6_niveis(tmp_path):
    """Fixa o motivo da migração existir — sem isto ela vira ruído."""
    _db_file, url = _preparar_0013(tmp_path)
    assert _tamanho_declarado(url) < len(CODIGO_6_NIVEIS)


def test_depois_da_migracao_a_coluna_comporta_6_niveis(tmp_path):
    _db_file, url = _preparar_0013(tmp_path)
    command.upgrade(_cfg(url), "0014")
    assert _tamanho_declarado(url) >= len(CODIGO_6_NIVEIS)


def test_codigo_de_6_niveis_sobrevive_ao_round_trip(tmp_path):
    db_file, url = _preparar_0013(tmp_path)
    command.upgrade(_cfg(url), "0014")

    con = sqlite3.connect(db_file)
    con.execute(
        "INSERT INTO flc_qualificador "
        "(seq_qualificador, num_qualificador, dsc_qualificador, ind_status, dat_inclusao) "
        "VALUES (802, ?, 'Rubrica de 6 niveis', 'A', date('now'))",
        (CODIGO_6_NIVEIS,),
    )
    con.commit()
    gravado = con.execute(
        "SELECT num_qualificador FROM flc_qualificador WHERE seq_qualificador = 802"
    ).fetchone()[0]
    con.close()
    assert gravado == CODIGO_6_NIVEIS


def test_dados_existentes_sobrevivem_a_migracao(tmp_path):
    db_file, url = _preparar_0013(tmp_path)
    command.upgrade(_cfg(url), "0014")

    con = sqlite3.connect(db_file)
    assert con.execute(
        "SELECT num_qualificador, dsc_qualificador FROM flc_qualificador "
        "WHERE seq_qualificador = 801"
    ).fetchone() == ('1.7', 'Rubrica curta')
    con.close()


def test_downgrade_volta_o_tamanho_anterior(tmp_path):
    _db_file, url = _preparar_0013(tmp_path)
    command.upgrade(_cfg(url), "0014")
    command.downgrade(_cfg(url), "0013")
    assert _tamanho_declarado(url) < len(CODIGO_6_NIVEIS)
