"""Steps BDD — execução orçamentária E/L/P (spec execucao-orcamentaria R4–R7).

Ilha 2050 — documentos, fontes auto-cadastradas e funil num ano só deste
módulo.
"""
from datetime import date
from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .conftest_regra import garantir_qualificador

scenarios("../execucao-orcamentaria/execucao.feature")


@pytest.fixture()
def contexto():
    return {}


def _db():
    from fluxocaixa.models.base import db

    return db


def _documento(estagio, numero, ano):
    from fluxocaixa.models import ExecucaoOrcamentaria

    return ExecucaoOrcamentaria.query.filter_by(
        cod_estagio=estagio, num_documento=numero, num_ano=ano,
        ind_status='A').first()


def _fonte(codigo, vigencia):
    from fluxocaixa.models import FonteRecurso

    ident, fonte = codigo.split(".", 1)
    return FonteRecurso.query.filter_by(
        cod_identificador_exercicio=ident, cod_fonte_stn=fonte,
        num_exercicio_vigencia=vigencia, ind_status='A').first()


def _registrar(contexto, **kwargs):
    from fluxocaixa.services.execucao_orcamentaria_service import registrar_documento
    from fluxocaixa.services.validacao import RegraNegocioError

    try:
        registrar_documento(**kwargs)
        contexto["erro"] = None
    except RegraNegocioError as exc:
        contexto["erro"] = exc.mensagem


@given("que estou autenticado como administrador")
def autenticado_admin(app, _admin_pronto):
    from fluxocaixa.auth.contexto import definir_usuario_corrente

    definir_usuario_corrente(12345)


@given(parsers.parse('um órgão "{cod:d}" chamado "{nom}"'))
def orgao_cadastrado(app, cod, nom):
    from fluxocaixa.models import Orgao
    from fluxocaixa.services.orgao_service import criar_orgao

    _db().session.rollback()
    if Orgao.query.get(cod) is None:
        criar_orgao(cod, nom)


@given(parsers.parse('um qualificador folha de despesa "{num}"'))
def qualificador_simples(app, num):
    garantir_qualificador(num)


@given(parsers.parse('um empenho "{numero}" de {valor} em {ano:d} no órgão "{cod:d}" e qualificador "{num}"'))
def empenho_dado(app, contexto, numero, valor, ano, cod, num):
    q = garantir_qualificador(num)
    if _documento('E', numero, ano) is None:
        _registrar(contexto, cod_estagio='E', num_documento=numero, num_ano=ano,
                   cod_orgao=cod, seq_qualificador=q.seq_qualificador,
                   val_documento=Decimal(valor), dat_documento=date(ano, 1, 10))


@given(parsers.parse('um empenho "{numero}" de {valor} em {ano:d} no órgão "{cod:d}" e qualificador "{num}" com a fonte "{codigo}"'))
def empenho_com_fonte(app, contexto, numero, valor, ano, cod, num, codigo):
    q = garantir_qualificador(num)
    if _documento('E', numero, ano) is None:
        _registrar(contexto, cod_estagio='E', num_documento=numero, num_ano=ano,
                   cod_orgao=cod, seq_qualificador=q.seq_qualificador,
                   val_documento=Decimal(valor), dat_documento=date(ano, 1, 10),
                   codigo_fonte=codigo)


@when(parsers.parse('registro a liquidação "{numero}" de {valor} em {ano:d} vinculada a "{pai}"'))
def registra_liquidacao(app, contexto, numero, valor, ano, pai):
    empenho = _documento('E', pai, ano)
    _registrar(contexto, cod_estagio='L', num_documento=numero, num_ano=ano,
               cod_orgao=empenho.cod_orgao,
               seq_qualificador=empenho.seq_qualificador,
               val_documento=Decimal(valor), dat_documento=date(ano, 2, 10),
               num_documento_pai=pai)


@when(parsers.parse('registro o pagamento "{numero}" de {valor} em {ano:d} vinculado ao empenho "{pai}"'))
def registra_pagamento_no_empenho(app, contexto, numero, valor, ano, pai):
    empenho = _documento('E', pai, ano)
    _registrar(contexto, cod_estagio='P', num_documento=numero, num_ano=ano,
               cod_orgao=empenho.cod_orgao,
               seq_qualificador=empenho.seq_qualificador,
               val_documento=Decimal(valor), dat_documento=date(ano, 3, 10),
               num_documento_pai=pai)


@given(parsers.parse('o pagamento orçamentário "{numero}" de {valor} em {ano:d} vinculado à liquidação "{pai}"'))
def pagamento_na_liquidacao(app, contexto, numero, valor, ano, pai):
    liquidacao = _documento('L', pai, ano)
    if _documento('P', numero, ano) is None:
        _registrar(contexto, cod_estagio='P', num_documento=numero, num_ano=ano,
                   cod_orgao=liquidacao.cod_orgao,
                   seq_qualificador=liquidacao.seq_qualificador,
                   val_documento=Decimal(valor), dat_documento=date(ano, 3, 10),
                   num_documento_pai=pai)


@when(parsers.parse('registro uma anulação de {valor} no documento "{estagio}" "{numero}" de {ano:d}'))
def registra_anulacao(app, contexto, valor, estagio, numero, ano):
    from fluxocaixa.services.execucao_orcamentaria_service import registrar_evento
    from fluxocaixa.services.validacao import RegraNegocioError

    documento = _documento(estagio, numero, ano)
    try:
        registrar_evento(documento.seq_execucao, 'A', Decimal(valor),
                         date(ano, 4, 10))
        contexto["erro"] = None
    except RegraNegocioError as exc:
        contexto["erro"] = exc.mensagem


@when(parsers.parse('consulto o funil de {ano:d}'))
def consulta_funil(app, contexto, ano):
    from fluxocaixa.services.execucao_orcamentaria_service import funil_do_ano

    contexto["funil"] = funil_do_ano(ano)


@then(parsers.parse('o corrente do documento "{estagio}" "{numero}" de {ano:d} é {valor}'))
def corrente_e(app, estagio, numero, ano, valor):
    from fluxocaixa.services.execucao_orcamentaria_service import valor_corrente

    _db().session.expire_all()
    documento = _documento(estagio, numero, ano)
    assert documento is not None, f"documento {estagio} {numero} não existe"
    assert valor_corrente(documento.seq_execucao) == \
        Decimal(valor).quantize(Decimal("0.01"))


@then(parsers.parse('a operação de execução é rejeitada com a mensagem "{mensagem}"'))
def operacao_rejeitada(contexto, mensagem):
    assert contexto["erro"] == mensagem, f"esperava {mensagem!r}, veio {contexto['erro']!r}"


@then(parsers.parse('o liquidado não pago de {ano:d} é {valor}'))
def liquidado_nao_pago_e(contexto, ano, valor):
    assert contexto["funil"]["liquidado_nao_pago"] == \
        Decimal(valor).quantize(Decimal("0.01")), contexto["funil"]


@then(parsers.parse('o empenhado de {ano:d} é {valor}'))
def empenhado_e(contexto, ano, valor):
    assert contexto["funil"]["empenhado"] == Decimal(valor).quantize(Decimal("0.01"))


@then(parsers.parse('a fonte "{codigo}" da vigência {vigencia:d} existe vinculada e pendente de revisão'))
def fonte_pendente(app, codigo, vigencia):
    fonte = _fonte(codigo, vigencia)
    assert fonte is not None, f"fonte {codigo} não auto-cadastrada"
    assert fonte.ind_vinculada == 'V'
    assert fonte.ind_pendente_revisao == 'S'


@then(parsers.parse('o documento "{estagio}" "{numero}" de {ano:d} referencia a fonte "{codigo}" da vigência {vigencia:d}'))
def documento_referencia_fonte(app, estagio, numero, ano, codigo, vigencia):
    _db().session.expire_all()
    documento = _documento(estagio, numero, ano)
    fonte = _fonte(codigo, vigencia)
    assert documento.seq_fonte_recurso == fonte.seq_fonte_recurso