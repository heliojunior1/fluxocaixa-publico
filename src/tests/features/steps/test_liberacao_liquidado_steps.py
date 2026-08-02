"""Steps BDD — liberação ancorada no liquidado (spec desembolso R23–R24).

Ilha 2056 (órgãos 70012/70013, qualificador 2.9.91) — os gates comparam a
liberação com o estoque do (ano, órgão, qualificador).
"""
from datetime import date
from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .conftest_regra import garantir_qualificador

scenarios("../desembolso/liberacao_liquidado.feature")


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


@given(parsers.parse('a fonte "{codigo}" cadastrada na vigência {vigencia:d} como "{vinculada}"'))
def fonte_cadastrada(app, codigo, vigencia, vinculada):
    from fluxocaixa.services.fonte_recurso_service import criar_fonte

    _db().session.rollback()
    if _fonte(codigo, vigencia) is None:
        ident, fonte = codigo.split(".", 1)
        criar_fonte(ident, fonte, f"Fonte de teste {codigo}", vigencia,
                    vinculada='L' if vinculada == 'livre' else 'V')


@given(parsers.parse('um empenho "{numero}" de {valor} em {ano:d} no órgão "{cod:d}" e qualificador "{num}" com a fonte "{codigo}"'))
def empenho_com_fonte(app, numero, valor, ano, cod, num, codigo):
    from fluxocaixa.services.execucao_orcamentaria_service import registrar_documento

    q = garantir_qualificador(num)
    if _documento('E', numero, ano) is None:
        registrar_documento(cod_estagio='E', num_documento=numero, num_ano=ano,
                            cod_orgao=cod, seq_qualificador=q.seq_qualificador,
                            val_documento=Decimal(valor),
                            dat_documento=date(ano, 1, 10), codigo_fonte=codigo)


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


@given(parsers.parse('uma liberação em rascunho de {valor} em "{dat}" no órgão "{cod:d}", qualificador "{num}" e fonte "{codigo}" da vigência {vigencia:d}'),
       target_fixture="liberacao_atual")
def liberacao_rascunho(app, valor, dat, cod, num, codigo, vigencia):
    from fluxocaixa.services.liberacao_service import criar_liberacao

    q = garantir_qualificador(num)
    fonte = _fonte(codigo, vigencia)
    return criar_liberacao(
        dat_liberacao=date.fromisoformat(dat), cod_orgao=cod,
        seq_qualificador=q.seq_qualificador,
        seq_fonte_recurso=fonte.seq_fonte_recurso,
        val_liberacao=Decimal(valor))


@when("confirmo essa liberação sem confirmação explícita")
def confirma_sem(app, contexto, liberacao_atual):
    from fluxocaixa.services.liberacao_service import confirmar_liberacao
    from fluxocaixa.services.validacao import RegraNegocioError

    try:
        confirmar_liberacao(liberacao_atual.seq_liberacao)
        contexto["erro"] = None
    except RegraNegocioError as exc:
        contexto["erro"] = exc.mensagem


@when("confirmo essa liberação com confirmação explícita")
def confirma_com(app, contexto, liberacao_atual):
    from fluxocaixa.services.liberacao_service import confirmar_liberacao

    confirmar_liberacao(liberacao_atual.seq_liberacao, confirmado=True)
    contexto["erro"] = None


@then(parsers.parse('a operação de liquidado é rejeitada com a mensagem "{mensagem}"'))
def operacao_rejeitada(contexto, mensagem):
    assert contexto["erro"] == mensagem, f"esperava {mensagem!r}, veio {contexto['erro']!r}"


@then("essa liberação está confirmada sem exigência extra")
def confirmada_sem_exigencia(contexto, liberacao_atual):
    _db().session.expire_all()
    assert contexto["erro"] is None
    assert liberacao_atual.cod_situacao == 'C'


@then(parsers.parse('essa liberação está confirmada e o evento registra "{texto}"'))
def confirmada_com_registro(liberacao_atual, texto):
    from fluxocaixa.models import LiberacaoEvento

    _db().session.expire_all()
    assert liberacao_atual.cod_situacao == 'C'
    evento = (LiberacaoEvento.query
              .filter_by(seq_liberacao=liberacao_atual.seq_liberacao,
                         cod_tipo_evento='CONFIRMACAO').first())
    assert evento is not None and evento.dsc_justificativa == texto, \
        evento.dsc_justificativa if evento else None
