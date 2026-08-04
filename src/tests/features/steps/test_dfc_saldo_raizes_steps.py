"""Steps BDD — saldo inicial e raízes do DFC (spec relatorios R22).

Ilha 2071. Import tardio de `fluxocaixa`.
"""
from datetime import date
from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../relatorios/dfc_saldo_raizes.feature")

CONTA = ("777", "0001", "Q11-1")


@pytest.fixture()
def contexto():
    return {}


def _db():
    from fluxocaixa.models.base import db

    return db


def _limpar():
    from fluxocaixa.models import ContaBancaria, SaldoContaFundo

    db = _db()
    db.session.rollback()
    conta = ContaBancaria.query.filter_by(
        cod_banco=CONTA[0], num_agencia=CONTA[1], num_conta=CONTA[2]).first()
    if conta is not None:
        SaldoContaFundo.query.filter_by(seq_conta=conta.seq_conta).delete()
        db.session.delete(conta)
        db.session.commit()


@pytest.fixture(autouse=True)
def _ilha(app):
    _limpar()
    yield
    _limpar()


def _conta():
    from fluxocaixa.models import ContaBancaria

    db = _db()
    conta = ContaBancaria.query.filter_by(
        cod_banco=CONTA[0], num_agencia=CONTA[1], num_conta=CONTA[2]).first()
    if conta is None:
        conta = ContaBancaria(cod_banco=CONTA[0], num_agencia=CONTA[1],
                              num_conta=CONTA[2], dsc_conta="Conta Q11",
                              cod_pessoa_inclusao=1)
        db.session.add(conta)
        db.session.commit()
    return conta


def _registrar_saldo(conta, dia, valor):
    from fluxocaixa.services.fundo_service import garantir_fundo_geral
    from fluxocaixa.services.saldo_fundo_service import gravar_saldo

    fundo_geral = garantir_fundo_geral()
    gravar_saldo(seq_conta=conta.seq_conta, seq_fundo=fundo_geral.seq_fundo,
                 dat_saldo=dia, val_saldo=Decimal(valor))


@given(parsers.parse("uma conta da ilha com saldo registrado de {valor} em "
                     "25/06/2071"))
def saldo_dias_antes(app, valor):
    _registrar_saldo(_conta(), date(2071, 6, 25), valor)


@given(parsers.parse("saldo registrado de {valor} em 30/06/2071"))
def saldo_vespera(app, valor):
    _registrar_saldo(_conta(), date(2071, 6, 30), valor)


@given("que a árvore de qualificadores só tem raiz de despesa",
       target_fixture="_so_despesa")
def so_raiz_despesa(app, monkeypatch):
    from fluxocaixa.models import Qualificador
    from fluxocaixa.repositories import qualificador_repository

    raiz_despesa = [q for q in qualificador_repository.get_root_qualificadores()
                    if isinstance(q, Qualificador) and q.tipo_fluxo == 'despesa']
    # F10.4: a assinatura real aceita o exercício opcional — o stub também.
    monkeypatch.setattr(qualificador_repository, "get_root_qualificadores",
                        lambda num_ano_exercicio=None: raiz_despesa)
    return True


@when(parsers.parse("consulto o saldo total de {dia:d}/{mes:d}/{ano:d}"))
def consulta_saldo(app, contexto, dia, mes, ano):
    from fluxocaixa.repositories.saldo_conta_repository import SaldoContaRepository

    contexto["saldo"] = SaldoContaRepository().get_saldo_total_by_date(
        date(ano, mes, dia))


def _dfc(contexto, ano, mes):
    from fluxocaixa.services.relatorio.dfc_service import get_dfc_data
    from fluxocaixa.services.validacao import RegraNegocioError

    try:
        contexto["dfc"] = get_dfc_data(
            periodo="mes", ano_selecionado=ano, mes_selecionado=mes,
            meses_selecionados=list(range(1, 13)), estrategia="realizado",
            cenario_selecionado_id=None)
        contexto["erro"] = None
    except RegraNegocioError as exc:
        contexto["erro"] = exc


@when(parsers.parse("calculo o DFC de junho de {ano:d}"))
def calcula_dfc(app, contexto, ano):
    _dfc(contexto, ano, 6)


@when(parsers.parse("calculo o DFC de julho de {ano:d}"))
def calcula_dfc_julho(app, contexto, ano):
    _dfc(contexto, ano, 7)


@then(parsers.parse("o saldo inicial do DFC é {valor}"))
def saldo_inicial_dfc(contexto, valor):
    assert contexto["erro"] is None, contexto["erro"]
    inicial = contexto["dfc"]["saldos_banco_anterior"][0]
    assert inicial == pytest.approx(float(valor)), (
        f"{inicial} — o zero registrado na véspera foi trocado pelo carry "
        "do último saldo não-zero")


@then("o saldo total é nulo")
def saldo_nulo(contexto):
    assert contexto["saldo"] is None, (
        f"{contexto['saldo']} — ausência de registro virou zero e o "
        "fallback de carry nunca dispara")


@then("recebo erro de negócio do DFC citando a raiz ausente")
def erro_do_dfc(contexto):
    assert contexto["erro"] is not None, (
        "o DFC devolveu relatório com totais zerados em vez de acusar a "
        "raiz ausente")
    assert "receita" in str(contexto["erro"]).lower()
