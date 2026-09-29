"""Unitários — tradução da projeção para o plano do ano consultado
(previsao R21, design D5: `dfc_projecao._traduzir_para_o_plano`).

Imports de app sempre tardios (isolamento de banco da suíte).
"""
from decimal import Decimal

import pytest

ANOS = (2111, 2112, 2113)


@pytest.fixture(autouse=True)
def _ilha(app):
    _limpar()
    yield
    _limpar()


def _limpar():
    from fluxocaixa.models import Qualificador
    from fluxocaixa.models.base import db

    db.session.rollback()
    for q in Qualificador.query.filter(Qualificador.num_ano_exercicio.in_(ANOS)).all():
        db.session.delete(q)
    db.session.commit()


def _criar(num, ano, raiz=None):
    from fluxocaixa.services import qualificador_service

    return qualificador_service.create_qualificador(
        num, f"Traducao {num} {ano}", num_ano_exercicio=ano, cod_rubrica_raiz=raiz)


def test_seqs_de_outros_exercicios_somam_no_qualificador_do_plano():
    from fluxocaixa.services.relatorio.dfc_projecao import _traduzir_para_o_plano

    antiga = _criar("1.86", 2111)
    intermediaria = _criar("1.86", 2112, raiz=antiga.cod_rubrica_raiz)
    atual = _criar("1.86", 2113, raiz=antiga.cod_rubrica_raiz)

    traduzido = _traduzir_para_o_plano({
        (antiga.seq_qualificador, 'C', 1): Decimal("10.00"),
        (intermediaria.seq_qualificador, 'C', 1): Decimal("5.00"),
        (None, 'C', 1): Decimal("1.00"),
    }, 2113)

    assert traduzido == {(atual.seq_qualificador, 'C', 1): Decimal("15.00"),
                         (None, 'C', 1): Decimal("1.00")}


def test_sem_correspondente_no_plano_mantem_o_seq_gravado():
    from fluxocaixa.services.relatorio.dfc_projecao import _traduzir_para_o_plano

    extinta = _criar("1.86", 2112)
    _criar("1.87", 2113)  # o plano de 2113 existe, mas sem a raiz da extinta

    bruto = {(extinta.seq_qualificador, 'D', 3): Decimal("7.00")}
    assert _traduzir_para_o_plano(bruto, 2113) == bruto
