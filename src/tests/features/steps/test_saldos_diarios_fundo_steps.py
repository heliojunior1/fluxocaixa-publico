"""Steps BDD — relatório de saldos diários por fundo (spec relatorios R14–R16).

Ataque na camada de serviço (`get_saldos_diarios_data`); a página é coberta
pelo Playwright. Ilha de datas 2037 e contas fictícias próprias (o restante
da suíte usa 2022–2036).
"""
from datetime import date
from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../relatorios/saldos_diarios_fundo.feature")

FUNDO_PADRAO = "9900"


@pytest.fixture()
def contexto():
    return {}


def _db():
    from fluxocaixa.models.base import db

    return db


def _dec(v) -> Decimal:
    return Decimal(str(v)).quantize(Decimal("0.01"))


def _conta(ident: str):
    from fluxocaixa.models import ContaBancaria

    db = _db()
    db.session.rollback()
    banco, agencia, num = ident.split("/")
    conta = ContaBancaria.query.filter_by(
        cod_banco=banco, num_agencia=agencia, num_conta=num
    ).first()
    if conta is None:
        conta = ContaBancaria(cod_banco=banco, num_agencia=agencia,
                              num_conta=num, dsc_conta=f"Conta diária {ident}")
        db.session.add(conta)
        db.session.commit()
    return conta


def _fundo(cod: str):
    from fluxocaixa.models import Fundo, TipoOrigemSaldo

    db = _db()
    fundo = Fundo.query.filter_by(cod_fundo=cod).first()
    if fundo is None:
        tipo = TipoOrigemSaldo.query.filter_by(txt_sigla="MANUAL").first()
        fundo = Fundo(cod_fundo=cod, dsc_fundo=f"Fundo diário {cod}",
                      seq_tipo_origem=tipo.seq_tipo_origem_saldo)
        db.session.add(fundo)
        db.session.commit()
    return fundo


def _gravar(ident: str, cod_fundo: str, dat: str, valor: str):
    from fluxocaixa.services.saldo_fundo_service import gravar_saldo

    gravar_saldo(
        seq_conta=_conta(ident).seq_conta,
        seq_fundo=_fundo(cod_fundo).seq_fundo,
        dat_saldo=date.fromisoformat(dat),
        val_saldo=Decimal(valor),
        val_aplicacoes=Decimal("0"),
        val_resgates=Decimal("0"),
        sigla_tipo_origem="MANUAL",
        sigla_sistema_origem=None,
    )


def _linha_conta(contexto, ident: str) -> dict:
    banco, agencia, num = ident.split("/")
    linhas = [
        linha for linha in contexto["dados"]["rows"]
        if linha["conta"].cod_banco == banco
        and linha["conta"].num_agencia == agencia
        and linha["conta"].num_conta == num
    ]
    assert linhas, f"conta {ident} ausente do modo agregado"
    return linhas[0]


def _linhas_fundo(contexto, ident: str, cod_fundo: str | None = None) -> list[dict]:
    banco, agencia, num = ident.split("/")
    return [
        linha for linha in contexto["dados"]["rows_fundo"]
        if linha["conta"].cod_banco == banco
        and linha["conta"].num_agencia == agencia
        and linha["conta"].num_conta == num
        and (cod_fundo is None or linha["fundo"].cod_fundo == cod_fundo)
    ]


# --------------------------------------------------------------------------
# Dado
# --------------------------------------------------------------------------

@given(parsers.parse('uma conta diária "{ident}" com saldo por fundo de "{valor}" em "{dat}"'))
@given(parsers.parse('a conta diária "{ident}" com saldo por fundo de "{valor}" em "{dat}"'))
def conta_com_saldo(app, ident, valor, dat):
    _gravar(ident, FUNDO_PADRAO, dat, valor)


@given(parsers.parse('uma conta diária "{ident}" com saldo do fundo "{fundo}" de "{valor}" em "{dat}"'))
@given(parsers.parse('a conta diária "{ident}" com saldo do fundo "{fundo}" de "{valor}" em "{dat}"'))
def conta_com_saldo_fundo(app, ident, fundo, valor, dat):
    _gravar(ident, fundo, dat, valor)


@given(parsers.parse('um lançamento de entrada de "{valor}" para a conta "{ident}" em "{dat}"'))
def lancamento_entrada(app, valor, ident, dat):
    from fluxocaixa.models import Lancamento, Qualificador
    from fluxocaixa.services.dominio_lancamento import (
        TIPO_ENTRADA, resolver_origem, resolver_tipo,
    )

    db = _db()
    qual = Qualificador.query.filter_by(num_qualificador="1.98.1").first()
    if qual is None:
        raiz = Qualificador.query.filter_by(num_qualificador="1").first()
        pai = Qualificador(num_qualificador="1.98", dsc_qualificador="Grupo diário",
                           cod_qualificador_pai=raiz.seq_qualificador if raiz else None)
        db.session.add(pai)
        db.session.commit()
        qual = Qualificador(num_qualificador="1.98.1", dsc_qualificador="Rubrica diária",
                            cod_qualificador_pai=pai.seq_qualificador)
        db.session.add(qual)
        db.session.commit()
    db.session.add(Lancamento(
        dat_lancamento=date.fromisoformat(dat),
        seq_qualificador=qual.seq_qualificador,
        val_lancamento=Decimal(valor),
        cod_tipo_lancamento=resolver_tipo(TIPO_ENTRADA).cod_tipo_lancamento,
        cod_origem_lancamento=resolver_origem("Manual").cod_origem_lancamento,
        seq_conta=_conta(ident).seq_conta,
        cod_pessoa_inclusao=1,
        ind_status='A',
    ))
    db.session.commit()


# --------------------------------------------------------------------------
# Quando
# --------------------------------------------------------------------------

@when(parsers.parse('consulto os saldos diários de "{dat}" no modo "{visao}"'))
def consulta(app, contexto, dat, visao):
    from fluxocaixa.services.relatorio.saldos_service import get_saldos_diarios_data

    contexto["dados"] = get_saldos_diarios_data(
        date.fromisoformat(dat), visao=visao
    )


@when(parsers.parse('consulto os saldos diários de "{dat}" no modo "{visao}" filtrando pela conta "{ident}"'))
def consulta_filtrada(app, contexto, dat, visao, ident):
    from fluxocaixa.services.relatorio.saldos_service import get_saldos_diarios_data

    contexto["dados"] = get_saldos_diarios_data(
        date.fromisoformat(dat), visao=visao, seq_conta=_conta(ident).seq_conta
    )


# --------------------------------------------------------------------------
# Então
# --------------------------------------------------------------------------

@then(parsers.parse('a linha da conta "{ident}" tem saldo inicial "{valor}"'))
def linha_saldo_inicial(contexto, ident, valor):
    assert _dec(_linha_conta(contexto, ident)["saldo_inicial"]) == Decimal(valor)


@then(parsers.parse('a linha da conta "{ident}" tem saldo inicial nulo'))
def linha_saldo_inicial_nulo(contexto, ident):
    assert _linha_conta(contexto, ident)["saldo_inicial"] is None


@then(parsers.parse('a linha da conta "{ident}" tem rendimento do dia "{valor}"'))
def linha_rendimento(contexto, ident, valor):
    assert _dec(_linha_conta(contexto, ident)["rendimento_dia"]) == Decimal(valor)


@then(parsers.parse('a linha da conta "{ident}" tem saldo registrado "{valor}"'))
def linha_saldo_registrado(contexto, ident, valor):
    assert _dec(_linha_conta(contexto, ident)["saldo_registrado"]) == Decimal(valor)


@then(parsers.parse('a linha da conta "{ident}" tem origem consolidada "{origem}"'))
def linha_origem(contexto, ident, origem):
    assert _linha_conta(contexto, ident)["origem_consolidada"] == origem


@then(parsers.parse('a linha da conta "{ident}" tem saldo final calculado "{valor}"'))
def linha_saldo_final(contexto, ident, valor):
    assert _dec(_linha_conta(contexto, ident)["saldo_final"]) == Decimal(valor)


@then(parsers.parse('a linha da conta "{ident}" tem divergência "{valor}"'))
def linha_divergencia(contexto, ident, valor):
    assert _dec(_linha_conta(contexto, ident)["divergencia"]) == Decimal(valor)


@then(parsers.parse('a linha da conta "{ident}" tem divergência nula'))
def linha_divergencia_nula(contexto, ident):
    assert _linha_conta(contexto, ident)["divergencia"] is None


@then(parsers.parse('a linha do fundo "{fundo}" da conta "{ident}" tem saldo inicial "{valor}"'))
def fundo_saldo_inicial(contexto, fundo, ident, valor):
    linhas = _linhas_fundo(contexto, ident, fundo)
    assert linhas, f"linha do fundo {fundo} ausente"
    assert _dec(linhas[0]["saldo_inicial"]) == Decimal(valor)


@then(parsers.parse('a linha do fundo "{fundo}" da conta "{ident}" tem rendimento "{valor}"'))
def fundo_rendimento(contexto, fundo, ident, valor):
    assert _dec(_linhas_fundo(contexto, ident, fundo)[0]["rendimento"]) == Decimal(valor)


@then(parsers.parse('a linha do fundo "{fundo}" da conta "{ident}" tem saldo "{valor}"'))
def fundo_saldo(contexto, fundo, ident, valor):
    assert _dec(_linhas_fundo(contexto, ident, fundo)[0]["saldo"]) == Decimal(valor)


@then(parsers.parse('não há linha do fundo "{fundo}" para a conta "{ident}"'))
def fundo_sem_linha(contexto, fundo, ident):
    assert _linhas_fundo(contexto, ident, fundo) == []


@then(parsers.parse('o total de saldo do modo fundo é "{valor}"'))
def total_fundo(contexto, valor):
    assert _dec(contexto["dados"]["totais_fundo"]["saldo"]) == Decimal(valor)


@then(parsers.parse('apenas a conta "{ident}" aparece nas linhas'))
def apenas_conta(contexto, ident):
    banco, agencia, num = ident.split("/")
    for linha in contexto["dados"]["rows"]:
        conta = linha["conta"]
        assert (conta.cod_banco, conta.num_agencia, conta.num_conta) == (banco, agencia, num)
    assert contexto["dados"]["rows"], "modo agregado sem linhas"


@then(parsers.parse('todas as linhas por fundo são da conta "{ident}"'))
def linhas_fundo_da_conta(contexto, ident):
    banco, agencia, num = ident.split("/")
    linhas = contexto["dados"]["rows_fundo"]
    assert linhas, "modo fundo sem linhas"
    for linha in linhas:
        conta = linha["conta"]
        assert (conta.cod_banco, conta.num_agencia, conta.num_conta) == (banco, agencia, num)


@then(parsers.parse('a série de evolução tem {qtd:d} pontos terminando em "{dat}"'))
def evolucao_pontos(contexto, qtd, dat):
    labels = contexto["dados"]["evolucao_labels"]
    assert len(labels) == qtd
    assert labels[-1] == dat
