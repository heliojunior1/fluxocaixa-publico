"""Migração 0013: mês da projeção → período da periodicidade (spec previsao R10).

Os dois casos do D2, que NÃO são a mesma transformação:

    MENSAL → num_periodo = mes                 (1:1, exato)
    ANUAL  → num_periodo = 1, val = SUM(mês)   (as 12 linhas colapsam)

O critério do ANUAL é o **total do ano preservado** — a forma muda, o número
não. É o mesmo critério que a golden da previsão cobra do lado do código.
"""
import sqlite3

from alembic import command

from .test_migracoes import _cfg


def _preparar_0012(tmp_path):
    """Banco na 0012 com um cenário MENSAL e um ANUAL, ambos com projeção."""
    db_file = tmp_path / "projecao.db"
    url = f"sqlite:///{db_file}"
    command.upgrade(_cfg(url), "0012")

    con = sqlite3.connect(db_file)
    con.executescript(
        """
        INSERT INTO flc_qualificador (seq_qualificador, num_qualificador, dsc_qualificador, ind_status, dat_inclusao)
        VALUES (901, '9.99.1', 'Rubrica migração', 'A', date('now'));

        INSERT INTO flc_simulador_cenario
          (seq_simulador_cenario, nom_cenario, ano_base, meses_projecao,
           cod_periodicidade, cod_metodo_base, ind_status, dat_criacao,
           dat_inclusao, cod_pessoa_inclusao)
        VALUES (901, 'CEN_MIG_MENSAL', 2015, 12, 'MENSAL', 'MANUAL', 'A', date('now'), date('now'), 1),
               (902, 'CEN_MIG_ANUAL', 2015, 1, 'ANUAL', 'MANUAL', 'A', date('now'), date('now'), 1);

        INSERT INTO flc_projecao_versao
          (seq_projecao_versao, seq_simulador_cenario, nom_versao, dat_versao, ind_publicado)
        VALUES (901, 901, 'v mensal', datetime('now'), 'S'),
               (902, 902, 'v anual', datetime('now'), 'S');
        """
    )
    # 12 meses em cada cenário: o MENSAL é a granularidade real; o ANUAL é a
    # DISTRIBUIÇÃO de um total anual, e é ela que colapsa.
    for mes in range(1, 13):
        con.execute(
            "INSERT INTO flc_projecao_valor "
            "(seq_projecao_versao, seq_qualificador, cod_tipo, ano, mes, val_projetado, val_realizado) "
            "VALUES (901, 901, 'C', 2015, ?, ?, ?)",
            (mes, mes * 100.0, mes * 10.0),
        )
        con.execute(
            "INSERT INTO flc_projecao_valor "
            "(seq_projecao_versao, seq_qualificador, cod_tipo, ano, mes, val_projetado, val_realizado) "
            "VALUES (902, 901, 'D', 2015, ?, ?, ?)",
            (mes, 50.0, 5.0),
        )
    con.commit()
    con.close()
    return db_file, url


def test_mensal_mapeia_periodo_para_o_mes(tmp_path):
    db_file, url = _preparar_0012(tmp_path)
    command.upgrade(_cfg(url), "0013")

    con = sqlite3.connect(db_file)
    linhas = con.execute(
        "SELECT num_periodo, val_projetado, val_realizado FROM flc_projecao_valor "
        "WHERE seq_projecao_versao = 901 ORDER BY num_periodo"
    ).fetchall()
    assert linhas == [(m, m * 100.0, m * 10.0) for m in range(1, 13)]

    colunas = [r[1] for r in con.execute("PRAGMA table_info(flc_projecao_valor)")]
    assert 'mes' not in colunas and 'num_periodo' in colunas
    con.close()


def test_anual_colapsa_preservando_o_total_do_ano(tmp_path):
    db_file, url = _preparar_0012(tmp_path)
    command.upgrade(_cfg(url), "0013")

    con = sqlite3.connect(db_file)
    linhas = con.execute(
        "SELECT num_periodo, val_projetado, val_realizado FROM flc_projecao_valor "
        "WHERE seq_projecao_versao = 902"
    ).fetchall()
    # 12 linhas viraram UMA, com o total do ano intacto (12 × 50 e 12 × 5).
    assert linhas == [(1, 600.0, 60.0)]
    con.close()


def test_rename_de_meses_projecao(tmp_path):
    db_file, url = _preparar_0012(tmp_path)
    command.upgrade(_cfg(url), "0013")

    con = sqlite3.connect(db_file)
    colunas = [r[1] for r in con.execute("PRAGMA table_info(flc_simulador_cenario)")]
    assert 'meses_projecao' not in colunas and 'num_periodos' in colunas
    assert con.execute(
        "SELECT num_periodos FROM flc_simulador_cenario WHERE seq_simulador_cenario = 901"
    ).fetchone() == (12,)
    con.close()


def test_downgrade_volta_o_mes_com_o_total_do_ano_preservado(tmp_path):
    db_file, url = _preparar_0012(tmp_path)
    command.upgrade(_cfg(url), "0013")
    command.downgrade(_cfg(url), "0012")

    con = sqlite3.connect(db_file)
    colunas = [r[1] for r in con.execute("PRAGMA table_info(flc_projecao_valor)")]
    assert 'mes' in colunas and 'num_periodo' not in colunas

    # MENSAL volta idêntico
    assert con.execute(
        "SELECT mes, val_projetado FROM flc_projecao_valor "
        "WHERE seq_projecao_versao = 901 ORDER BY mes"
    ).fetchall() == [(m, m * 100.0) for m in range(1, 13)]

    # ANUAL reexpande em 12 meses: a DISTRIBUIÇÃO original não volta (perda
    # documentada na migração), mas o total do ano sim.
    anual = con.execute(
        "SELECT mes, val_projetado FROM flc_projecao_valor "
        "WHERE seq_projecao_versao = 902 ORDER BY mes"
    ).fetchall()
    assert [m for m, _ in anual] == list(range(1, 13))
    assert round(sum(v for _, v in anual), 2) == 600.0
    con.close()
