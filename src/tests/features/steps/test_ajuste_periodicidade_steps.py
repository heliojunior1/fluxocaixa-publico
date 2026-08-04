"""Steps BDD — ajuste rateado por periodicidade (spec previsao R15).

Ilha 2069 (ano-ref 2068). Import tardio de `fluxocaixa`.
"""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../previsao/ajuste_periodicidade.feature")

QUAL = "1.74.1"


@pytest.fixture()
def contexto():
    return {"ajustes": []}


def _db():
    from fluxocaixa.models.base import db

    return db


def _limpar():
    from fluxocaixa.models import Lancamento, Qualificador

    db = _db()
    db.session.rollback()
    q = Qualificador.query.filter_by(num_qualificador=QUAL).first()
    if q is not None:
        Lancamento.query.filter_by(seq_qualificador=q.seq_qualificador).delete()
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
        q = Qualificador(num_qualificador=QUAL,
                         dsc_qualificador="Rubrica Ajuste Q15",
                         ind_status='A')
        db.session.add(q)
        db.session.commit()
    return q


@given(parsers.parse("um ajuste de valor de {valor} no mês {mes:d} para o "
                     "qualificador de ajuste"))
def ajuste_valor(app, contexto, valor, mes):
    q = _qualificador()
    contexto["ajustes"].append(SimpleNamespace(
        mes=mes, seq_qualificador=q.seq_qualificador,
        cod_tipo_ajuste='V', val_ajuste=Decimal(valor)))


@given(parsers.parse("um ajuste percentual de {p:d} no mês {mes:d} para o "
                     "qualificador de ajuste"))
def ajuste_percentual(app, contexto, p, mes):
    q = _qualificador()
    contexto["ajustes"].append(SimpleNamespace(
        mes=mes, seq_qualificador=q.seq_qualificador,
        cod_tipo_ajuste='P', val_ajuste=Decimal(p)))


@given(parsers.parse("realizado de {valor} em janeiro de {ano:d} no "
                     "qualificador de ajuste"))
def realizado_anterior(app, valor, ano):
    from fluxocaixa.models import Lancamento
    from fluxocaixa.services.dominio_lancamento import resolver_origem, resolver_tipo

    q = _qualificador()
    db = _db()
    db.session.add(Lancamento(
        dat_lancamento=date(ano, 1, 15),
        seq_qualificador=q.seq_qualificador,
        val_lancamento=Decimal(valor),
        cod_tipo_lancamento=resolver_tipo("Entrada").cod_tipo_lancamento,
        cod_origem_lancamento=resolver_origem("Manual").cod_origem_lancamento,
        cod_pessoa_inclusao=1, ind_status='A'))
    db.session.commit()


def _executa(contexto, periodicidade, ano, n):
    from fluxocaixa.services.simulador_cenario_service import (
        _executar_cenario_manual,
    )

    contexto["df"] = _executar_cenario_manual(
        contexto["ajustes"], ano, n, periodicidade)


@when(parsers.parse("executo o cenário manual quinzenal de {ano:d} com "
                    "{n:d} períodos"))
def executa_quinzenal(app, contexto, ano, n):
    _executa(contexto, "QUINZENAL", ano, n)


@when(parsers.parse("executo o cenário manual mensal de {ano:d} com "
                    "{n:d} períodos"))
def executa_mensal(app, contexto, ano, n):
    _executa(contexto, "MENSAL", ano, n)


@then(parsers.parse("a soma dos períodos do mês {mes:d} é {valor}"))
def soma_do_mes(contexto, mes, valor):
    df = contexto["df"]
    do_mes = df[df["data"].map(lambda d: d.month == mes)]
    soma = float(do_mes["valor_projetado"].sum())
    assert soma == pytest.approx(float(valor)), (
        f"{soma} — o ajuste mensal foi replicado em cada período em vez de "
        "rateado (R$ do mês multiplicado pelos períodos)")
