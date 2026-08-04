"""Unitários dos filtros sargáveis (infraestrutura-banco R12).

As bordas do calendário são o risco real do refactor extract→faixa:
off-by-one em 31/12 ou fevereiro mudaria totais em silêncio.
Import tardio de `fluxocaixa`.
"""


def _bordas(clausula):
    """Extrai (inicio, fim) do BETWEEN compilado com binds literais."""
    sql = str(clausula.compile(compile_kwargs={"literal_binds": True}))
    assert "BETWEEN" in sql, sql
    return sql


def test_no_ano_cobre_o_ano_inteiro():
    from fluxocaixa.repositories.lancamento_repository import _no_ano

    sql = _bordas(_no_ano(2064))
    assert "2064-01-01" in sql and "2064-12-31" in sql, sql


def test_no_mes_fevereiro_bissexto():
    from fluxocaixa.repositories.lancamento_repository import _no_mes

    sql = _bordas(_no_mes(2064, 2))
    assert "2064-02-01" in sql and "2064-02-29" in sql, sql


def test_no_mes_fevereiro_nao_bissexto():
    from fluxocaixa.repositories.lancamento_repository import _no_mes

    sql = _bordas(_no_mes(2063, 2))
    assert "2063-02-28" in sql, sql


def test_no_mes_meses_de_30_e_31_dias():
    from fluxocaixa.repositories.lancamento_repository import _no_mes

    assert "2064-04-30" in _bordas(_no_mes(2064, 4))
    assert "2064-12-31" in _bordas(_no_mes(2064, 12))


def test_nos_anos_vira_or_de_faixas():
    from fluxocaixa.repositories.lancamento_repository import _nos_anos

    sql = str(_nos_anos([2063, 2064]).compile(
        compile_kwargs={"literal_binds": True}))
    assert "OR" in sql and "2063-01-01" in sql and "2064-12-31" in sql, sql
    assert "extract" not in sql.lower(), sql
