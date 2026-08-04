"""Steps BDD — derivação de (ano, período) (spec previsao R7–R10).

R7/R8 são Python puro (sem banco). R9/R10 tocam a projeção, na ilha 2015.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../previsao/periodo_resolver.feature")

ANO = 2015
QUAL = "1.95.1"


@pytest.fixture()
def contexto():
    return {}


def _pr():
    from fluxocaixa.services import periodo_resolver

    return periodo_resolver


def _db():
    from fluxocaixa.models.base import db

    return db


def _limpar():
    from fluxocaixa.models import SimuladorCenario

    db = _db()
    db.session.rollback()
    for c in SimuladorCenario.query.filter(
        SimuladorCenario.nom_cenario.like("CEN_%")
    ).all():
        db.session.delete(c)
    db.session.commit()


@pytest.fixture(autouse=True)
def _ilha(app):
    _limpar()
    yield
    _limpar()


def _qualificador():
    from fluxocaixa.models import Qualificador

    db = _db()
    q = Qualificador.query.filter_by(num_qualificador=QUAL).first()
    if q is None:
        q = Qualificador(num_qualificador=QUAL, dsc_qualificador="Rubrica período")
        db.session.add(q)
        db.session.commit()
    return q


# --------------------------------------------------------------------------
# R7 / R8 — módulo puro
# --------------------------------------------------------------------------

@when(parsers.parse('resolvo a data "{data}" com periodicidade "{periodicidade}"'))
def resolve(app, contexto, data, periodicidade):
    from fluxocaixa.services.validacao import RegraNegocioError

    try:
        contexto["periodo"] = _pr().resolver(date.fromisoformat(data), periodicidade)
        contexto.pop("erro", None)
    except RegraNegocioError as erro:
        contexto["erro"] = erro


@when(parsers.parse('peço o mês do período {periodo:d} de {ano:d} com periodicidade "{periodicidade}"'))
def pede_mes(app, contexto, periodo, ano, periodicidade):
    contexto["mes"] = _pr().mes_do_periodo(periodicidade, ano, periodo)


@when(parsers.parse('valido o período {periodo:d} com periodicidade "{periodicidade}"'))
def valida(app, contexto, periodo, periodicidade):
    from fluxocaixa.services.validacao import RegraNegocioError

    try:
        _pr().validar_periodo(periodicidade, periodo)
        contexto["valido"] = True
    except RegraNegocioError as erro:
        contexto["valido"] = False
        contexto["erro"] = erro


@then(parsers.parse('o período resolvido é ano {ano:d} e período {periodo:d}'))
def periodo_resolvido(contexto, ano, periodo):
    assert tuple(contexto["periodo"]) == (ano, periodo), contexto["periodo"]


@then(parsers.parse('recebo erro de período mencionando "{trecho}"'))
def erro_periodo(contexto, trecho):
    assert "erro" in contexto, "esperava RegraNegocioError"
    assert trecho.lower() in str(contexto["erro"]).lower()


@then(parsers.parse('o mês é {mes:d}'))
def mes_confere(contexto, mes):
    assert contexto["mes"] == mes, contexto["mes"]


@then(parsers.parse('a validação {resultado}'))
def validacao_resultado(contexto, resultado):
    esperado = resultado.strip() == "passa"
    assert contexto["valido"] is esperado


# --------------------------------------------------------------------------
# R9 / R10 — projeção
# --------------------------------------------------------------------------

@given(parsers.parse('um cenário de período "{nome}" com periodicidade "{periodicidade}" e {qtd:d} períodos'),
       target_fixture="cenario")
def cenario_periodicidade(app, contexto, nome, periodicidade, qtd):
    from fluxocaixa.services.simulador_cenario_service import criar_simulador_cenario

    seq = _qualificador().seq_qualificador
    ajustes = {}
    for i in range(1, 25):
        ajustes[f"val_ajuste_{i}_{seq}"] = 100
        ajustes[f"cod_tipo_ajuste_{i}_{seq}"] = "V"
    cenario = criar_simulador_cenario(
        nom_cenario=nome, dsc_cenario="F6.3", ano_base=ANO, num_periodos=qtd,
        tipo_cenario_receita="MANUAL", config_receita={"seq_qualificadores": [seq]},
        tipo_cenario_despesa=None, config_despesa={},
        ajustes_receita=ajustes, user_id=1,
        cod_periodicidade=periodicidade,
    )
    contexto["cenario"] = cenario
    contexto["periodicidade"] = periodicidade
    return cenario


@given(parsers.parse('um lançamento realizado em "{data}" no qualificador do cenário'))
def lancamento_realizado(app, contexto, data):
    from fluxocaixa.models import Lancamento
    from fluxocaixa.models.lancamento import TIPO_CREDITO
    from fluxocaixa.services.dominio_lancamento import resolver_origem

    db = _db()
    db.session.add(Lancamento(
        dat_lancamento=date.fromisoformat(data),
        seq_qualificador=_qualificador().seq_qualificador,
        val_lancamento=Decimal("777.00"),
        cod_tipo_lancamento=TIPO_CREDITO,
        cod_origem_lancamento=resolver_origem("Manual").cod_origem_lancamento,
        cod_pessoa_inclusao=1, ind_status='A',
    ))
    db.session.commit()


@when("executo a simulação de período")
def executa(contexto, cenario):
    from fluxocaixa.services.simulador_cenario_service import executar_simulacao

    resultado = executar_simulacao(cenario.seq_simulador_cenario)
    contexto["datas"] = sorted(
        d.date() if hasattr(d, "date") else d
        for d in resultado["projecao_receita"]["data"].tolist()
    )


@when("salvo a projeção como versão")
def salva_versao(contexto, cenario):
    from fluxocaixa.services.projecao_versao_service import salvar_projecao_como_versao

    contexto["versao"] = salvar_projecao_como_versao(
        cenario.seq_simulador_cenario, "v1 período", publicar=True)


@when("apuro os realizados da versão")
def apura_realizados(contexto, cenario):
    from fluxocaixa.services.projecao_versao_service import (
        atualizar_realizados_de_lancamentos,
        salvar_projecao_como_versao,
    )

    versao = salvar_projecao_como_versao(
        cenario.seq_simulador_cenario, "v1 realizado", publicar=True)
    atualizar_realizados_de_lancamentos(versao.seq_projecao_versao)
    contexto["versao"] = versao


@then(parsers.parse('a projeção tem {qtd:d} pontos'))
def qtd_pontos(contexto, qtd):
    assert len(contexto["datas"]) == qtd, contexto["datas"]


@then("os pontos estão espaçados de 7 dias")
def espacados_semana(contexto):
    datas = contexto["datas"]
    assert all((b - a) == timedelta(days=7)
               for a, b in zip(datas, datas[1:])), datas


@then("os pontos caem dois em cada mês")
def dois_por_mes(contexto):
    from collections import Counter

    por_mes = Counter((d.year, d.month) for d in contexto["datas"])
    assert set(por_mes.values()) == {2}, por_mes


@then("os pontos estão espaçados de um mês")
def espacados_mes(contexto):
    datas = contexto["datas"]
    assert all(b.month != a.month or b.year != a.year
               for a, b in zip(datas, datas[1:])), datas
    assert all(d.day == datas[0].day for d in datas), datas


@then(parsers.parse('os valores gravados têm período entre {minimo:d} e {maximo:d}'))
def periodos_gravados(contexto, minimo, maximo):
    from fluxocaixa.models import ProjecaoValor

    valores = ProjecaoValor.query.filter_by(
        seq_projecao_versao=contexto["versao"].seq_projecao_versao).all()
    assert valores, "versão sem valores"
    assert all(minimo <= v.num_periodo <= maximo for v in valores), \
        [v.num_periodo for v in valores]


@then(parsers.parse('o realizado foi somado na quinzena {periodo:d}'))
def realizado_na_quinzena(contexto, periodo):
    from fluxocaixa.models import ProjecaoValor

    linhas = ProjecaoValor.query.filter_by(
        seq_projecao_versao=contexto["versao"].seq_projecao_versao,
        num_periodo=periodo).all()
    assert linhas, f"nenhuma linha no período {periodo}"
    assert any(l.val_realizado and Decimal(str(l.val_realizado)) == Decimal("777.00")
               for l in linhas), [str(l.val_realizado) for l in linhas]
