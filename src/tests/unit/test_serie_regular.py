"""Série mensal regular (previsao R18, change corrigir-motores-de-previsao).

Unitários puros de `_serie_mensal_regular`: lançamentos fictícios em memória,
sem banco. Import tardio de `fluxocaixa` (regra do conftest).
"""
from datetime import date
from types import SimpleNamespace

JANELA = (date(2082, 1, 1), date(2084, 12, 31))


def _lancamentos(*pares):
    return [SimpleNamespace(dat_lancamento=d, valor_com_sinal=v) for d, v in pares]


def _serie(pares, hoje, janela=JANELA):
    from fluxocaixa.services.modelos_economicos_service import _serie_mensal_regular

    df = _serie_mensal_regular(_lancamentos(*pares), janela[0], janela[1], hoje)
    return [(d.year, d.month, round(float(v), 2)) for d, v in zip(df["data"], df["valor"])]


def test_buraco_no_meio_vira_zero_e_janela_encerrada_completa_ate_dezembro():
    serie = _serie([(date(2084, 1, 10), 100.0), (date(2084, 3, 5), 50.0),
                    (date(2084, 3, 20), -20.0)], hoje=date(2085, 2, 1))
    assert serie[0] == (2084, 1, 100.0)
    assert serie[1] == (2084, 2, 0.0)
    assert serie[2] == (2084, 3, 30.0)  # soma COM sinal do mês
    assert serie[-1] == (2084, 12, 0.0)
    assert len(serie) == 12


def test_rubrica_que_comeca_no_meio_da_janela_nao_ganha_zeros_a_esquerda():
    serie = _serie([(date(2083, 6, 1), 10.0)], hoje=date(2085, 1, 1))
    assert serie[0][:2] == (2083, 6)


def test_execucao_dentro_da_janela_corta_o_mes_em_curso():
    serie = _serie([(date(2084, 9, 15), 10.0), (date(2084, 10, 1), 99.0)],
                   hoje=date(2084, 10, 1))
    assert serie[-1] == (2084, 9, 10.0)  # outubro, parcial, fica de fora


def test_virada_de_ano_janela_recem_encerrada_vai_ate_dezembro():
    serie = _serie([(date(2084, 11, 15), 10.0)], hoje=date(2085, 1, 5))
    assert serie[-1] == (2084, 12, 0.0)


def test_janeiro_dentro_da_janela_so_com_janeiro_da_serie_vazia():
    serie = _serie([(date(2084, 1, 3), 10.0)], hoje=date(2084, 1, 10),
                   janela=(date(2084, 1, 1), date(2084, 12, 31)))
    assert serie == []


def test_janela_inteira_depois_da_execucao_termina_no_ultimo_mes_com_movimento():
    serie = _serie([(date(2082, 3, 1), 10.0), (date(2082, 5, 1), 5.0)],
                   hoje=date(2026, 9, 29))
    assert serie == [(2082, 3, 10.0), (2082, 4, 0.0), (2082, 5, 5.0)]


def test_janela_do_ano_base_comeca_em_primeiro_de_janeiro():
    from fluxocaixa.services.modelos_economicos_service import janela_do_ano_base

    assert janela_do_ano_base(2085, 3) == (date(2082, 1, 1), date(2084, 12, 31))


def test_serie_de_treino_da_origem_unica_e_magnitude_e_a_leitura_crua_tem_sinal(monkeypatch):
    """R20: `obter_serie_do_ano_base` (origem única das três portas) entrega
    magnitude; `obter_dados_historicos` continua COM sinal — caracterização,
    backtest e fórmulas fazem a própria conversão."""
    from fluxocaixa.services import modelos_economicos_service as modelos

    saidas = _lancamentos((date(2083, 1, 10), -300.0), (date(2083, 2, 10), -200.0),
                          (date(2083, 2, 20), 50.0))  # estorno reduz o mês
    monkeypatch.setattr(modelos, "_lancamentos_da_serie", lambda *a, **k: saidas)

    crua = modelos.obter_dados_historicos(1, date(2083, 1, 1), date(2083, 12, 31),
                                          hoje=date(2090, 1, 1))
    treino = modelos.obter_serie_do_ano_base([1], 2084, 1, hoje=date(2090, 1, 1))

    assert [round(float(v), 2) for v in crua["valor"][:2]] == [-300.0, -150.0]
    assert [round(float(v), 2) for v in treino["valor"][:2]] == [300.0, 150.0]
    assert len(treino) == 12
