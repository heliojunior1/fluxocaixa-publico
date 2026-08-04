"""Steps BDD — modelo de saldo por fundo (spec saldo-por-fundo R1–R6).

Feature sem tela: os steps atacam o serviço de gravação, o banco e as views
diretamente (a UI chega na F2.4).
"""
from datetime import date
from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../saldo-por-fundo/modelo.feature")

D2 = lambda v: Decimal(str(v)).quantize(Decimal("0.01"))


@pytest.fixture()
def contexto():
    return {}


def _db():
    from fluxocaixa.models.base import db

    return db


def _gravar(conta, fundo, dat, valor, aplicacoes="0", resgates="0",
            tipo="MANUAL", sistema=None):
    from fluxocaixa.services.saldo_fundo_service import gravar_saldo

    return gravar_saldo(
        seq_conta=conta.seq_conta,
        seq_fundo=fundo.seq_fundo,
        dat_saldo=date.fromisoformat(dat),
        val_saldo=Decimal(valor),
        val_aplicacoes=Decimal(aplicacoes),
        val_resgates=Decimal(resgates),
        sigla_tipo_origem=tipo,
        sigla_sistema_origem=sistema,
    )


# --------------------------------------------------------------------------
# Dado
# --------------------------------------------------------------------------

@given(parsers.parse('uma conta de fundo "{ident}"'), target_fixture="conta")
def conta_de_fundo(app, ident):
    from fluxocaixa.models import ContaBancaria

    db = _db()
    db.session.rollback()
    banco, agencia, num = ident.split("/")
    existente = ContaBancaria.query.filter_by(
        cod_banco=banco, num_agencia=agencia, num_conta=num
    ).first()
    if existente:
        return existente
    conta = ContaBancaria(cod_banco=banco, num_agencia=agencia, num_conta=num,
                          dsc_conta=f"Conta fundo {ident}")
    db.session.add(conta)
    db.session.commit()
    return conta


@given(parsers.parse('um fundo "{cod}" de origem "{sigla_tipo}"'), target_fixture="fundo")
def fundo_de_origem(app, contexto, cod, sigla_tipo):
    from fluxocaixa.models import Fundo, TipoOrigemSaldo

    db = _db()
    existente = Fundo.query.filter_by(cod_fundo=cod).first()
    if existente:
        contexto.setdefault("fundos", {})[cod] = existente
        return existente
    tipo = TipoOrigemSaldo.query.filter_by(txt_sigla=sigla_tipo).first()
    fundo = Fundo(cod_fundo=cod, dsc_fundo=f"Fundo {cod}",
                  seq_tipo_origem=tipo.seq_tipo_origem_saldo)
    db.session.add(fundo)
    db.session.commit()
    contexto.setdefault("fundos", {})[cod] = fundo
    return fundo


@given(parsers.parse('um sistema de origem "{sigla}" cadastrado'))
def sistema_cadastrado(app, sigla):
    from fluxocaixa.models import SistemaOrigem

    db = _db()
    if not SistemaOrigem.query.filter_by(txt_sigla=sigla).first():
        db.session.add(SistemaOrigem(txt_sigla=sigla, dsc_sistema_origem=f"Sistema {sigla}"))
        db.session.commit()


@given(parsers.parse('um saldo gravado de "{valor}" para essa conta e fundo em "{dat}"'))
def saldo_gravado(conta, fundo, valor, dat):
    _gravar(conta, fundo, dat, valor)


@given(parsers.parse('um saldo gravado de "{valor}" com aplicações "{apl}" e resgates "{resg}" em "{dat}"'))
def saldo_gravado_movimentos(conta, fundo, valor, apl, resg, dat):
    _gravar(conta, fundo, dat, valor, aplicacoes=apl, resgates=resg)


@given(parsers.parse('um saldo gravado de "{valor}" para o fundo "{cod}" dessa conta em "{dat}"'))
def saldo_gravado_fundo(contexto, conta, valor, cod, dat):
    _gravar(conta, contexto["fundos"][cod], dat, valor)


@given(parsers.parse('um saldo importado de "{valor}" para o fundo "{cod}" dessa conta em "{dat}"'))
def saldo_importado_fundo(contexto, conta, valor, cod, dat):
    _gravar(conta, contexto["fundos"][cod], dat, valor, tipo="IMPORTADO")


@given(parsers.parse('gravo "{valor}" para a mesma chave'))
@when(parsers.parse('gravo "{valor}" para a mesma chave'))
def regrava_mesma_chave(conta, fundo, contexto, valor):
    contexto["ultima_data"] = contexto.get("ultima_data", "2026-07-10")
    _gravar(conta, fundo, contexto["ultima_data"], valor)


# --------------------------------------------------------------------------
# Quando
# --------------------------------------------------------------------------

@when("o seed de domínio executa novamente")
def executa_seed(app, contexto):
    from fluxocaixa.models import SistemaOrigem
    from fluxocaixa.services.seed_dominio import seed_dominio

    contexto["sistemas_antes"] = SistemaOrigem.query.count()
    seed_dominio()


@when("insiro diretamente outra linha ativa para a mesma chave")
def insere_duplicata_direta(conta, fundo, contexto):
    import sqlalchemy.exc

    from fluxocaixa.models import SaldoContaFundo, TipoOrigemSaldo

    db = _db()
    tipo = TipoOrigemSaldo.query.filter_by(txt_sigla='MANUAL').first()
    db.session.add(
        SaldoContaFundo(
            seq_conta=conta.seq_conta,
            seq_fundo=fundo.seq_fundo,
            dat_saldo=date(2026, 7, 10),
            val_saldo=Decimal("555.00"),
            seq_tipo_origem=tipo.seq_tipo_origem_saldo,
            ind_status='A',
        )
    )
    try:
        db.session.commit()
        contexto["violacao"] = False
    except sqlalchemy.exc.IntegrityError:
        db.session.rollback()
        contexto["violacao"] = True


@when(parsers.parse('gravo um saldo com tipo "{tipo}" e sem sistema de origem'))
def grava_sem_sistema(conta, fundo, contexto, tipo):
    from fluxocaixa.services.validacao import RegraNegocioError

    try:
        _gravar(conta, fundo, "2026-07-10", "100.00", tipo=tipo)
        contexto["erro"] = None
    except RegraNegocioError as exc:
        contexto["erro"] = exc.mensagem


@when(parsers.parse('gravo um saldo com tipo "{tipo}" e sistema "{sistema}"'))
def grava_com_sistema(conta, fundo, contexto, tipo, sistema):
    from fluxocaixa.services.validacao import RegraNegocioError

    try:
        _gravar(conta, fundo, "2026-07-10", "100.00", tipo=tipo, sistema=sistema)
        contexto["erro"] = None
    except RegraNegocioError as exc:
        contexto["erro"] = exc.mensagem


@when(parsers.parse('consulto a view de cálculo em "{dat}"'))
def consulta_view_calc(conta, fundo, contexto, dat):
    from fluxocaixa.repositories.saldo_fundo_repository import calc_por_periodo

    dia = date.fromisoformat(dat)
    contexto["linhas"] = calc_por_periodo(
        data_inicio=dia, data_fim=dia, seq_conta=conta.seq_conta, seq_fundo=fundo.seq_fundo
    )


@when(parsers.parse('consulto o agregado da conta em "{dat}"'))
def consulta_agregado(conta, contexto, dat):
    from fluxocaixa.repositories.saldo_fundo_repository import agregado_por_conta

    dia = date.fromisoformat(dat)
    linhas = agregado_por_conta(data_inicio=dia, data_fim=dia, seq_conta=conta.seq_conta)
    assert len(linhas) == 1, f"esperava 1 linha agregada, veio {len(linhas)}"
    contexto["agregado"] = linhas[0]


# --------------------------------------------------------------------------
# Então
# --------------------------------------------------------------------------

@then("as tabelas do saldo por fundo existem")
def tabelas_existem(app):
    from sqlalchemy import inspect

    from fluxocaixa.models.base import engine

    tabelas = set(inspect(engine).get_table_names())
    esperadas = {"flc_fundo", "flc_saldo_conta_fundo", "flc_tipo_origem_saldo", "flc_sistema_origem"}
    assert esperadas <= tabelas, esperadas - tabelas


@then(parsers.parse('os tipos de origem "{lista}" estão seedados'))
def tipos_seedados(app, lista):
    from fluxocaixa.models import TipoOrigemSaldo

    existentes = {t.txt_sigla for t in TipoOrigemSaldo.query.all()}
    assert set(lista.split(",")) <= existentes


@then("nenhum sistema de origem novo é criado pelo seed")
def seed_nao_cria_sistemas(contexto):
    from fluxocaixa.models import SistemaOrigem

    assert SistemaOrigem.query.count() == contexto["sistemas_antes"]


@then("o banco rejeita com violação de unicidade")
def banco_rejeita(contexto):
    assert contexto["violacao"] is True, "índice único parcial não bloqueou a 2ª linha ativa"


@then(parsers.parse('existe exatamente 1 linha ativa com valor "{valor}" para a chave'))
def uma_ativa(conta, fundo, valor):
    from fluxocaixa.models import SaldoContaFundo

    ativas = SaldoContaFundo.query.filter_by(
        seq_conta=conta.seq_conta, seq_fundo=fundo.seq_fundo, ind_status='A'
    ).all()
    assert len(ativas) == 1
    assert D2(ativas[0].val_saldo) == D2(valor)


@then(parsers.parse('existe {qtd:d} linha inativa com valor "{valor}" para a chave'))
def inativas_com_valor(conta, fundo, qtd, valor):
    from fluxocaixa.models import SaldoContaFundo

    inativas = [
        s
        for s in SaldoContaFundo.query.filter_by(
            seq_conta=conta.seq_conta, seq_fundo=fundo.seq_fundo, ind_status='I'
        )
        if D2(s.val_saldo) == D2(valor)
    ]
    assert len(inativas) == qtd


@then(parsers.parse('a gravação é rejeitada com a mensagem "{mensagem}"'))
def gravacao_rejeitada(contexto, mensagem):
    assert contexto["erro"] == mensagem, f"esperava {mensagem!r}, veio {contexto['erro']!r}"


@then(parsers.parse('o saldo inicial derivado é "{valor}"'))
def saldo_inicial_derivado(contexto, valor):
    assert len(contexto["linhas"]) == 1
    assert D2(contexto["linhas"][0]["val_saldo_inicial_derivado"]) == D2(valor)


@then(parsers.parse('o rendimento calculado é "{valor}"'))
def rendimento_calculado(contexto, valor):
    assert D2(contexto["linhas"][0]["val_rendimento_calculado"]) == D2(valor)


@then(parsers.parse('a view retorna {qtd:d} linha com valor "{valor}"'))
def view_retorna(contexto, qtd, valor):
    assert len(contexto["linhas"]) == qtd
    assert D2(contexto["linhas"][0]["val_saldo"]) == D2(valor)


@then(parsers.parse('o saldo agregado é "{valor}"'))
def saldo_agregado(contexto, valor):
    assert D2(contexto["agregado"]["val_saldo"]) == D2(valor)


@then(parsers.parse('a origem consolidada é "{rotulo}"'))
def origem_consolidada(contexto, rotulo):
    assert contexto["agregado"]["dsc_origem_consolidada"] == rotulo
