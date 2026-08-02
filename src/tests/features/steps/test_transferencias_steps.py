"""Steps BDD — transferências internas (spec desembolso R13). Ilha 2041."""
from datetime import date
from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../desembolso/transferencias.feature")


@pytest.fixture()
def contexto():
    return {}


def _db():
    from fluxocaixa.models.base import db

    return db


def _conta(ident):
    from fluxocaixa.models import ContaBancaria

    banco, agencia, num = ident.split("/")
    return ContaBancaria.query.filter_by(
        cod_banco=banco, num_agencia=agencia, num_conta=num).first()


@given("que estou autenticado como administrador")
def autenticado_admin(app, _admin_pronto):
    from fluxocaixa.auth.contexto import definir_usuario_corrente

    definir_usuario_corrente(12345)


@given(parsers.parse('uma conta de transferência "{ident}"'))
def conta_transferencia(app, ident):
    from fluxocaixa.models import ContaBancaria

    db = _db()
    db.session.rollback()
    if _conta(ident) is None:
        banco, agencia, num = ident.split("/")
        db.session.add(ContaBancaria(cod_banco=banco, num_agencia=agencia,
                                     num_conta=num, dsc_conta=f"Conta {ident}"))
        db.session.commit()


@when(parsers.parse('registro uma transferência de {valor} de "{origem}" para "{destino}" em "{dat}"'))
def registra(app, contexto, valor, origem, destino, dat):
    from fluxocaixa.services.transferencia_service import criar_transferencia
    from fluxocaixa.services.validacao import RegraNegocioError

    try:
        contexto["transferencia"] = criar_transferencia(
            dat_transferencia=date.fromisoformat(dat),
            seq_conta_origem=_conta(origem).seq_conta,
            seq_conta_destino=_conta(destino).seq_conta,
            val_transferencia=Decimal(valor))
        contexto["erro"] = None
    except RegraNegocioError as exc:
        contexto["erro"] = exc.mensagem


@when("inativo essa transferência")
def inativa(app, contexto):
    from fluxocaixa.services.transferencia_service import inativar_transferencia

    inativar_transferencia(contexto["transferencia"].seq_transferencia)


@then(parsers.parse('o total de transferências de "{dat}" é {valor}'))
def total_do_dia(dat, valor):
    from fluxocaixa.services.transferencia_service import total_do_dia

    _db().session.expire_all()
    assert total_do_dia(date.fromisoformat(dat)) == Decimal(valor).quantize(Decimal("0.01"))


@then(parsers.parse('a operação de transferência é rejeitada com a mensagem "{mensagem}"'))
def rejeitada(contexto, mensagem):
    assert contexto["erro"] == mensagem, f"esperava {mensagem!r}, veio {contexto['erro']!r}"
