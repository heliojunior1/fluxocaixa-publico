"""Steps BDD — série histórica por raiz (spec previsao R17, F10.2).

Imports de app sempre tardios (isolamento de banco da suíte).
"""
from datetime import date
from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../previsao/serie_por_raiz.feature")

RAMO = "7.7"
ANO_A, ANO_B = 2072, 2073


@pytest.fixture()
def contexto():
    return {}


def _db():
    from fluxocaixa.models.base import db

    return db


def _limpar():
    from fluxocaixa.models import Lancamento, Qualificador

    db = _db()
    db.session.rollback()
    quals = Qualificador.query.filter(
        Qualificador.num_qualificador.like(f"{RAMO}%")).all()
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


def _criar_qualificador(num, dsc, ano, raiz=None):
    from fluxocaixa.services import qualificador_service

    return qualificador_service.create_qualificador(
        num, dsc, num_ano_exercicio=ano, cod_rubrica_raiz=raiz)


def _criar_lancamento(qualificador, valor, ano):
    from fluxocaixa.models import Lancamento
    from fluxocaixa.services.dominio_lancamento import (
        resolver_origem,
        resolver_tipo,
    )

    db = _db()
    lanc = Lancamento(
        dat_lancamento=date(ano, 6, 15),
        seq_qualificador=qualificador.seq_qualificador,
        val_lancamento=Decimal(str(valor)),
        cod_tipo_lancamento=resolver_tipo("Entrada").cod_tipo_lancamento,
        cod_origem_lancamento=resolver_origem("Manual").cod_origem_lancamento,
        cod_pessoa_inclusao=1,
        ind_status='A',
    )
    db.session.add(lanc)
    db.session.commit()
    return lanc


@given(parsers.parse(
    'a rubrica "{num}" no exercício {ano:d} com lançamento de {valor} em {ano_lanc:d}'))
def dado_rubrica_com_lancamento(num, ano, valor, ano_lanc, contexto):
    q = _criar_qualificador(num, f"Rubrica {num} de {ano}", ano)
    _criar_lancamento(q, valor, ano_lanc)
    contexto[(num, ano)] = q


@given(parsers.parse(
    'o espelho renumerado "{num}" no exercício {ano:d} herdando a raiz de "{origem}" com lançamento de {valor} em {ano_lanc:d}'))
def dado_espelho_renumerado(num, ano, origem, valor, ano_lanc, contexto):
    original = next(q for (n, _a), q in contexto.items()
                    if isinstance(n, str) and n == origem)
    q = _criar_qualificador(num, f"Espelho {num} de {ano}", ano,
                            raiz=original.cod_rubrica_raiz)
    _criar_lancamento(q, valor, ano_lanc)
    contexto["espelho"] = q


@given(parsers.parse(
    'a rubrica nova "{num}" no exercício {ano:d} com raiz própria e lançamento de {valor} em {ano_lanc:d}'))
def dado_rubrica_nova(num, ano, valor, ano_lanc, contexto):
    q = _criar_qualificador(num, f"Rubrica nova {num} de {ano}", ano)
    _criar_lancamento(q, valor, ano_lanc)
    contexto["nova"] = q


@given(parsers.parse('a rubrica "{num}" no exercício {ano:d} sem lançamentos'))
def dado_rubrica_vazia(num, ano, contexto):
    contexto[(num, ano)] = _criar_qualificador(num, f"Rubrica vazia {num}", ano)


def _dados_historicos(qualificador):
    from fluxocaixa.services.modelos_economicos_service import (
        obter_dados_historicos,
    )

    return obter_dados_historicos(
        qualificador.seq_qualificador,
        date(ANO_A, 1, 1), date(ANO_B, 12, 31))


@when("consulto os dados históricos do espelho de 2073")
def quando_consulto_espelho(contexto):
    contexto["serie"] = _dados_historicos(contexto["espelho"])


@when("consulto os dados históricos da rubrica nova de 2073")
def quando_consulto_nova(contexto):
    contexto["serie"] = _dados_historicos(contexto["nova"])


@when(parsers.parse('peço a projeção de média histórica da rubrica "{num}" de {ano:d}'))
def quando_projecao_media(num, ano, contexto):
    from fluxocaixa.services.modelos_economicos_service import calcular_projecao
    from fluxocaixa.services.validacao import RegraNegocioError

    q = contexto[(num, ano)]
    try:
        calcular_projecao('MEDIA_HISTORICA', [q.seq_qualificador], 12,
                          ano + 1, {})
        contexto["erro"] = None
    except RegraNegocioError as e:
        contexto["erro"] = str(e)


@when(parsers.parse(
    'peço a projeção de média histórica da rubrica "{num}" de {ano:d} para o ano seguinte'))
def quando_projecao_media_ok(num, ano, contexto):
    from fluxocaixa.services.modelos_economicos_service import calcular_projecao

    q = contexto[(num, ano)]
    contexto["projecao"] = calcular_projecao(
        'MEDIA_HISTORICA', [q.seq_qualificador], 12, ano + 1, {})


@then(parsers.parse('a série contém os anos {ano_a:d} e {ano_b:d}'))
def entao_serie_dois_anos(ano_a, ano_b, contexto):
    anos = sorted({d.year for d in contexto["serie"]["data"]})
    assert anos == [ano_a, ano_b], anos


@then(parsers.parse('a série contém apenas o ano {ano:d}'))
def entao_serie_um_ano(ano, contexto):
    anos = sorted({d.year for d in contexto["serie"]["data"]})
    assert anos == [ano], anos


@then(parsers.parse('a projeção é recusada citando "{trecho}"'))
def entao_projecao_recusada(trecho, contexto):
    assert contexto["erro"], "a projeção deveria ter sido recusada"
    assert trecho in contexto["erro"], contexto["erro"]


@then("o resultado declara os pontos e anos da série treinada")
def entao_resultado_declara(contexto):
    info = contexto["projecao"].attrs.get("serie_info")
    assert info, "a projeção deveria carregar serie_info"
    assert info["pontos"] >= 1
    assert ANO_A in info["anos"]
