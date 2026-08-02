"""Steps BDD — funil LOA→caixa e conciliação (spec execucao-orcamentaria R8–R9).

Ilha 2054 (órgãos 70010/70011, qualificadores 2.9.8x) — o funil e a
conciliação varrem o ANO inteiro.
"""
from datetime import date
from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .conftest_regra import garantir_qualificador

scenarios("../execucao-orcamentaria/funil.feature")


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


@given(parsers.parse('um qualificador folha de despesa "{num}" com dotação inicial de {valor} em {ano:d}'))
def qualificador_com_dotacao(app, num, valor, ano):
    from fluxocaixa.services.dotacao_service import criar_dotacao, dotacao_de

    q = garantir_qualificador(num)
    if dotacao_de(ano, q.seq_qualificador) is None:
        criar_dotacao(ano, q.seq_qualificador, Decimal(valor))


@given(parsers.parse('um qualificador folha de despesa "{num}" com LOA de {valor} no ano {ano:d}'))
def qualificador_com_loa(app, num, valor, ano):
    from fluxocaixa.models import Loa

    q = garantir_qualificador(num)
    if not Loa.query.filter_by(num_ano=ano, seq_qualificador=q.seq_qualificador).first():
        _db().session.add(Loa(num_ano=ano, seq_qualificador=q.seq_qualificador,
                              val_loa=Decimal(valor), ind_status='A'))
        _db().session.commit()


@given(parsers.parse('um empenho "{numero}" de {valor} em {ano:d} no órgão "{cod:d}" e qualificador "{num}"'))
def empenho_dado(app, numero, valor, ano, cod, num):
    from fluxocaixa.services.execucao_orcamentaria_service import registrar_documento

    q = garantir_qualificador(num)
    if _documento('E', numero, ano) is None:
        registrar_documento(cod_estagio='E', num_documento=numero, num_ano=ano,
                            cod_orgao=cod, seq_qualificador=q.seq_qualificador,
                            val_documento=Decimal(valor),
                            dat_documento=date(ano, 1, 10))


@given(parsers.parse('a liquidação "{numero}" de {valor} em {ano:d} vinculada a "{pai}"'))
def liquidacao_dada(app, numero, valor, ano, pai):
    from fluxocaixa.services.execucao_orcamentaria_service import registrar_documento

    empenho = _documento('E', pai, ano)
    if _documento('L', numero, ano) is None:
        registrar_documento(cod_estagio='L', num_documento=numero, num_ano=ano,
                            cod_orgao=empenho.cod_orgao,
                            seq_qualificador=empenho.seq_qualificador,
                            val_documento=Decimal(valor),
                            dat_documento=date(ano, 2, 10),
                            num_documento_pai=pai)


@given(parsers.parse('o pagamento orçamentário "{numero}" de {valor} em {ano:d} vinculado à liquidação "{pai}"'))
def pagamento_orcamentario_dado(app, numero, valor, ano, pai):
    from fluxocaixa.services.execucao_orcamentaria_service import registrar_documento

    liquidacao = _documento('L', pai, ano)
    if _documento('P', numero, ano) is None:
        registrar_documento(cod_estagio='P', num_documento=numero, num_ano=ano,
                            cod_orgao=liquidacao.cod_orgao,
                            seq_qualificador=liquidacao.seq_qualificador,
                            val_documento=Decimal(valor),
                            dat_documento=date(ano, 3, 10),
                            num_documento_pai=pai)


@given(parsers.parse('um desembolso financeiro de {valor} em "{dat}" no órgão "{cod:d}" e qualificador "{num}"'))
def desembolso_financeiro(app, valor, dat, cod, num):
    from fluxocaixa.models import Pagamento

    q = garantir_qualificador(num)
    _db().session.add(Pagamento(
        dat_pagamento=date.fromisoformat(dat), cod_orgao=cod,
        seq_qualificador=q.seq_qualificador,
        val_pagamento=Decimal(valor), dsc_pagamento="Desembolso de teste",
        cod_origem='M', ind_status='A', cod_pessoa_inclusao=1))
    _db().session.commit()


@when(parsers.parse('consulto o relatório do funil de {ano:d}'))
def consulta_funil(app, contexto, ano):
    from fluxocaixa.services.funil_service import relatorio_funil

    contexto["funil"] = relatorio_funil(ano)


@when(parsers.parse('consulto a conciliação de {ano:d}'))
def consulta_conciliacao(app, contexto, ano):
    from fluxocaixa.services.funil_service import conciliacao_orcamento_caixa

    contexto["conciliacao"] = conciliacao_orcamento_caixa(ano)


@then(parsers.parse('a linha do funil do qualificador "{num}" mostra autorizado {autorizado}, empenhado {empenhado}, liquidado {liquidado}, pago {pago} e liquidado não pago {pendente}'))
def linha_do_funil(contexto, num, autorizado, empenhado, liquidado, pago, pendente):
    linha = next((l for l in contexto["funil"]["linhas"]
                  if l["qualificador"].num_qualificador == num), None)
    assert linha is not None, f"qualificador {num} fora do funil"
    q2 = lambda v: Decimal(v).quantize(Decimal("0.01"))  # noqa: E731
    assert linha["autorizado"] == q2(autorizado), linha
    assert linha["empenhado"] == q2(empenhado), linha
    assert linha["liquidado"] == q2(liquidado), linha
    assert linha["pago"] == q2(pago), linha
    assert linha["liquidado_nao_pago"] == q2(pendente), linha


@then(parsers.parse('a conciliação do órgão "{cod:d}" mostra diferença {diferenca} com a direção "{direcao}"'))
def linha_da_conciliacao(contexto, cod, diferenca, direcao):
    linha = next((l for l in contexto["conciliacao"] if l["cod_orgao"] == cod), None)
    assert linha is not None, f"órgão {cod} fora da conciliação"
    assert linha["diferenca"] == Decimal(diferenca).quantize(Decimal("0.01")), linha
    assert linha["direcao"] == direcao, linha
