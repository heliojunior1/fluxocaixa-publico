"""Steps BDD — herança da rubrica raiz (cadastros-nucleo R30, F10.5).

Imports de app sempre tardios (isolamento de banco da suíte).
"""
from datetime import date
from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../cadastros-nucleo/heranca_raiz.feature")

RAMOS = ("7.11", "7.12", "7.13")
ANOS_ILHA = (2090, 2091)


@pytest.fixture()
def contexto():
    return {}


def _db():
    from fluxocaixa.models.base import db

    return db


def _limpar():
    from sqlalchemy import or_

    from fluxocaixa.models import Lancamento, Qualificador

    db = _db()
    db.session.rollback()
    filtros = [Qualificador.num_qualificador.like(f"{r}%") for r in RAMOS]
    quals = Qualificador.query.filter(or_(*filtros)).all()
    if quals:
        seqs = [q.seq_qualificador for q in quals]
        Lancamento.query.filter(
            Lancamento.seq_qualificador.in_(seqs)
        ).delete(synchronize_session=False)
        db.session.commit()
        for q in quals:
            db.session.delete(q)
        db.session.commit()


@pytest.fixture(autouse=True)
def _ilha(app):
    _limpar()
    yield
    _limpar()


@given(parsers.parse(
    'a rubrica de origem "{num}" chamada "{dsc}" no exercício {ano:d} com lançamento de {valor}'))
def dado_origem(num, dsc, ano, valor, contexto):
    from fluxocaixa.models import Lancamento
    from fluxocaixa.services import qualificador_service as svc
    from fluxocaixa.services.dominio_lancamento import (
        resolver_origem,
        resolver_tipo,
    )

    q = svc.create_qualificador(num, dsc, num_ano_exercicio=ano)
    db = _db()
    db.session.add(Lancamento(
        dat_lancamento=date(ano, 5, 10),
        seq_qualificador=q.seq_qualificador,
        val_lancamento=Decimal(valor),
        cod_tipo_lancamento=resolver_tipo("Entrada").cod_tipo_lancamento,
        cod_origem_lancamento=resolver_origem("Manual").cod_origem_lancamento,
        cod_pessoa_inclusao=1, ind_status='A',
    ))
    db.session.commit()
    contexto["origem"] = q
    contexto["ano_origem"] = ano


@given("a rubrica de origem inativada")
def dado_origem_inativada(contexto):
    contexto["origem"].ind_status = 'I'
    _db().session.commit()


def _criar(num, dsc, ano, raiz=None):
    from fluxocaixa.services import qualificador_service as svc

    return svc.create_qualificador(
        num, dsc, num_ano_exercicio=ano, cod_rubrica_raiz=raiz)


@when(parsers.parse(
    'crio "{num}" chamada "{dsc}" no exercício {ano:d} herdando a raiz da origem'))
def quando_crio_herdando(num, dsc, ano, contexto):
    contexto["criada"] = _criar(
        num, dsc, ano, raiz=contexto["origem"].cod_rubrica_raiz)


@when(parsers.parse(
    'crio "{num}" chamada "{dsc}" no exercício {ano:d} sem herdar raiz'))
def quando_crio_sem_heranca(num, dsc, ano, contexto):
    contexto["criada"] = _criar(num, dsc, ano)


@when(parsers.parse(
    'tento criar "{num}" chamada "{dsc}" no exercício {ano:d} herdando a raiz da origem'))
def quando_tento_criar_herdando(num, dsc, ano, contexto):
    from fluxocaixa.services.validacao import RegraNegocioError

    try:
        _criar(num, dsc, ano, raiz=contexto["origem"].cod_rubrica_raiz)
        contexto["erro"] = None
    except RegraNegocioError as e:
        contexto["erro"] = str(e)


@when(parsers.parse(
    'tento criar "{num}" chamada "{dsc}" no exercício {ano:d} herdando a raiz {raiz:d}'))
def quando_tento_criar_raiz_fixa(num, dsc, ano, raiz, contexto):
    from fluxocaixa.services.validacao import RegraNegocioError

    try:
        _criar(num, dsc, ano, raiz=raiz)
        contexto["erro"] = None
    except RegraNegocioError as e:
        contexto["erro"] = str(e)


def _serie(qualificador):
    from fluxocaixa.services.modelos_economicos_service import (
        obter_dados_historicos,
    )

    return obter_dados_historicos(
        qualificador.seq_qualificador,
        date(min(ANOS_ILHA), 1, 1), date(max(ANOS_ILHA), 12, 31))


@then(parsers.parse('a série histórica da herdeira contém o lançamento de {ano:d}'))
def entao_serie_herdada(ano, contexto):
    serie = _serie(contexto["criada"])
    anos = {d.year for d in serie["data"]}
    assert ano in anos, anos


@then("a rubrica criada tem raiz própria e série vazia")
def entao_raiz_propria_serie_vazia(contexto):
    criada = contexto["criada"]
    _db().session.refresh(criada)
    assert criada.cod_rubrica_raiz == criada.seq_qualificador
    assert len(_serie(criada)) == 0


@then(parsers.parse('a criação é recusada com mensagem contendo "{trecho}"'))
def entao_recusada(trecho, contexto):
    assert contexto["erro"], "a criação deveria ter sido recusada"
    assert trecho.lower() in contexto["erro"].lower(), contexto["erro"]
