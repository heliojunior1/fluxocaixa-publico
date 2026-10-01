"""Correspondência de rubricas — unitários puros (previsao R30/R31).

A expansão da série por correspondência é exercitada com estados em memória
(sem banco): fusão, rateio encadeado, pendência resolvida só pelo grupo
inteiro e guarda de ciclo. Import tardio de `fluxocaixa`.
"""
from datetime import date
from decimal import Decimal

import pytest


def _estado(seq, tipo, ano, origens, destinos, rateio=None):
    from fluxocaixa.services.correspondencia_rubrica_service import EstadoCorrespondencia

    return EstadoCorrespondencia(
        seq=seq, tipo=tipo, ano_vigencia=ano, origens=tuple(origens),
        destinos={d: None for d in destinos},
        rateio={k: Decimal(v) for k, v in rateio.items()} if rateio else None)


def _expandir(estados, raizes):
    from fluxocaixa.services.serie_historica import _Expansao

    return _Expansao(estados).executar(set(raizes))


def _por_raiz(expansao):
    return {(c.raiz, round(c.fator, 6), c.ate, c.estimado) for c in expansao.componentes}


def test_fusao_soma_as_origens_com_corte_na_vigencia():
    exp = _expandir([_estado(1, 'F', 2084, [10, 20], [30])], [30])
    assert _por_raiz(exp) == {(30, 1.0, None, False),
                              (10, 1.0, date(2084, 1, 1), False),
                              (20, 1.0, date(2084, 1, 1), False)}
    assert exp.nao_resolvidos == []


def test_rateio_encadeado_multiplica_pelo_caminho():
    # 10 → (40% 31, 60% 32) em 2083; 31 + 33 → 39 em 2084
    estados = [_estado(1, 'D', 2083, [10], [31, 32], {31: '40', 32: '60'}),
               _estado(2, 'F', 2084, [31, 33], [39])]
    comps = _por_raiz(_expandir(estados, [39]))
    assert (10, 0.4, date(2083, 1, 1), True) in comps   # corte mais cedo vence
    assert (31, 1.0, date(2084, 1, 1), False) in comps
    assert (33, 1.0, date(2084, 1, 1), False) in comps


def test_pendente_nao_entra_na_rubrica_sozinha():
    exp = _expandir([_estado(1, 'D', 2084, [10], [31, 32])], [31])
    assert {c.raiz for c in exp.componentes} == {31}
    assert exp.nao_resolvidos == [{'correspondencia': 1, 'faltam': [32]}]


def test_pendente_entra_uma_vez_no_grupo_inteiro():
    exp = _expandir([_estado(1, 'D', 2084, [10], [31, 32])], [31, 32])
    origens = [c for c in exp.componentes if c.raiz == 10]
    assert len(origens) == 1 and origens[0].fator == 1.0
    assert exp.nao_resolvidos == []


def test_ciclo_termina():
    # dado inconsistente (o cadastro recusa): 10 → 20 e 20 → 10
    estados = [_estado(1, 'F', 2084, [10, 11], [20]), _estado(2, 'F', 2085, [20, 12], [10])]
    exp = _expandir(estados, [20])
    assert {c.raiz for c in exp.componentes} == {20, 10, 11, 12}


def test_antecessoras_detecta_o_caminho():
    from fluxocaixa.services.correspondencia_rubrica_service import _antecessoras

    por_destino = {30: [_estado(1, 'F', 2084, [10, 20], [30])],
                   10: [_estado(2, 'D', 2083, [5], [10, 11])]}
    assert _antecessoras(30, por_destino) == {10, 20, 5}


@pytest.mark.parametrize("entrada,esperado", [
    ("30", Decimal("30.0000")), ("33,3333", Decimal("33.3333")),
    ("0", Decimal("0.0000")), ("100", Decimal("100.0000")),
])
def test_percentual_aceita_virgula_e_quatro_casas(entrada, esperado):
    from fluxocaixa.services.correspondencia_rubrica_service import _percentual

    assert _percentual(entrada, "8.7.3") == esperado


@pytest.mark.parametrize("entrada", ["-1", "100.01", "abc", ""])
def test_percentual_recusa_fora_da_faixa(entrada):
    from fluxocaixa.services.correspondencia_rubrica_service import _percentual
    from fluxocaixa.services.validacao import RegraNegocioError

    with pytest.raises(RegraNegocioError):
        _percentual(entrada, "8.7.3")
