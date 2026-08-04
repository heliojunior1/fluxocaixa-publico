"""Unitários — resolução do plano por exercício (cadastros-nucleo R28, F10.4).

Imports de app sempre tardios (isolamento de banco da suíte).
"""
import pytest

RAMO = "8.4"
ANO_A, ANO_B = 2081, 2083  # ilha própria, com lacuna (2082) para o fallback


@pytest.fixture(autouse=True)
def _ilha(client):
    _limpar()
    yield
    _limpar()


def _limpar():
    from fluxocaixa.models import Qualificador
    from fluxocaixa.models.base import db

    db.session.rollback()
    for q in Qualificador.query.filter(
            Qualificador.num_qualificador.like(f"{RAMO}%")).all():
        db.session.delete(q)
    db.session.commit()


def _criar(ano, dsc):
    from fluxocaixa.services import qualificador_service

    return qualificador_service.create_qualificador(
        RAMO, dsc, num_ano_exercicio=ano)


def test_ano_com_plano_resolve_para_ele_mesmo():
    from fluxocaixa.services.qualificador_service import (
        resolver_exercicio_do_plano,
    )

    _criar(ANO_A, "Plano A")
    assert resolver_exercicio_do_plano(ANO_A) == ANO_A


def test_lacuna_resolve_para_o_anterior_mais_recente():
    from fluxocaixa.services.qualificador_service import (
        resolver_exercicio_do_plano,
    )

    _criar(ANO_A, "Plano A")
    _criar(ANO_B, "Plano B")
    # 2082 não tem plano: o anterior mais recente é 2081
    assert resolver_exercicio_do_plano(ANO_A + 1) == ANO_A


def test_listagens_recortam_por_exercicio():
    from fluxocaixa.services.qualificador_service import (
        list_active_qualificadores,
    )

    a = _criar(ANO_A, "Plano A")
    b = _criar(ANO_B, "Plano B")
    seqs_a = {q.seq_qualificador for q in list_active_qualificadores(ANO_A)}
    assert a.seq_qualificador in seqs_a
    assert b.seq_qualificador not in seqs_a
    # sem filtro: comportamento histórico (todos)
    seqs_todos = {q.seq_qualificador for q in list_active_qualificadores()}
    assert {a.seq_qualificador, b.seq_qualificador} <= seqs_todos


def test_plano_inativo_nao_conta_como_exercicio():
    from fluxocaixa.models.base import db
    from fluxocaixa.services import qualificador_service
    from fluxocaixa.services.qualificador_service import exercicios_com_plano

    q = _criar(ANO_A, "Plano Que Sai")
    qualificador_service.delete_qualificador(q.seq_qualificador,
                                             confirmado=True)
    db.session.commit()
    assert ANO_A not in exercicios_com_plano()
