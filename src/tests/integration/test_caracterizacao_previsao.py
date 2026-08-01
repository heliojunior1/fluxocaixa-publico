"""Rede de caracterização da previsão (spec previsao R4).

Gerada sobre o modelo ANTIGO (quatro tabelas) e comparada depois da
unificação: é a prova de que colapsar os ramos espelhados de
`executar_simulacao` não moveu número nenhum.

Regerar deliberadamente (só quando a mudança de número for intencional):

    PYTHONPATH=src REGERAR_GOLDEN=1 pytest src/tests/integration/test_caracterizacao_previsao.py
"""
import os

import pytest

from .. import caracterizacao_previsao as prev


@pytest.fixture()
def massa(app):
    prev.montar_historico()
    yield
    prev.limpar_massa()


def test_golden_da_previsao_nao_mudou(massa):
    snapshot = prev.coletar_snapshot()

    if os.getenv("REGERAR_GOLDEN") == "1":
        prev.salvar_golden(snapshot)
        pytest.skip("golden regenerada por REGERAR_GOLDEN=1")

    if not prev.caminho_golden().exists():
        prev.salvar_golden(snapshot)
        pytest.skip("golden inexistente — criada agora; rode de novo para comparar")

    divergencias = prev.diferencas(prev.carregar_golden(), snapshot)
    assert not divergencias, (
        "a previsão mudou:\n  " + "\n  ".join(divergencias[:40])
        + (f"\n  … e outras {len(divergencias) - 40}" if len(divergencias) > 40 else "")
    )


def test_serie_de_entrada_tem_o_sinal_correto(massa):
    """Nível 1 da rede — é por aqui que o resíduo da F6.1b passou.

    A série que alimenta os modelos traz o valor COM SINAL: despesa negativa.
    Se alguém voltar a ler a coluna crua (sempre positiva desde a F6.1b), este
    teste acusa antes que a golden precise.
    """
    series = prev.coletar_series()

    assert series[prev.QUAL_RECEITA], "série de receita vazia"
    assert all(float(p["valor"]) > 0 for p in series[prev.QUAL_RECEITA])
    assert series[prev.QUAL_DESPESA], "série de despesa vazia"
    assert all(float(p["valor"]) < 0 for p in series[prev.QUAL_DESPESA]), (
        "série de despesa deveria vir NEGATIVA (valor com sinal); positiva "
        "significa leitura da coluna crua — o resíduo da F6.1b de volta"
    )
    assert all(float(p["valor"]) < 0 for p in series["agregado_despesa"])


def test_simulacoes_deterministicas_cobertas(massa):
    simulacoes = prev.coletar_simulacoes()
    for modelo in prev.MODELOS_DETERMINISTICOS:
        assert modelo in simulacoes, f"modelo {modelo} fora da rede"
        assert simulacoes[modelo] is not None, f"simulação de {modelo} falhou"
