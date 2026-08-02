"""Steps BDD — dotação e créditos adicionais (spec execucao-orcamentaria R1–R3).

Ilha 2047 — o teto do autorizado compara Σ das confirmadas do ANO inteiro do
qualificador, então LOA/dotação/liberações deste módulo vivem num ano só dele.
"""
from datetime import date
from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .conftest_regra import garantir_qualificador

scenarios("../execucao-orcamentaria/dotacao.feature")


@pytest.fixture()
def contexto():
    return {}


def _db():
    from fluxocaixa.models.base import db

    return db


def _dotacao(num, ano):
    from fluxocaixa.services.dotacao_service import dotacao_de

    q = garantir_qualificador(num)
    return dotacao_de(ano, q.seq_qualificador)


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


@given(parsers.parse('a fonte "{codigo}" cadastrada na vigência {vigencia:d} como "{vinculada}"'))
def fonte_cadastrada(app, codigo, vigencia, vinculada):
    from fluxocaixa.services.fonte_recurso_service import criar_fonte

    _db().session.rollback()
    if _fonte(codigo, vigencia) is None:
        ident, fonte = codigo.split(".", 1)
        criar_fonte(ident, fonte, f"Fonte de teste {codigo}", vigencia,
                    vinculada='L' if vinculada == 'livre' else 'V')


@given(parsers.parse('um qualificador folha de despesa "{num}" com LOA de {valor} no ano {ano:d}'))
def qualificador_com_loa(app, num, valor, ano):
    from fluxocaixa.models import Loa

    q = garantir_qualificador(num)
    if not Loa.query.filter_by(num_ano=ano, seq_qualificador=q.seq_qualificador).first():
        _db().session.add(Loa(num_ano=ano, seq_qualificador=q.seq_qualificador,
                              val_loa=Decimal(valor), ind_status='A'))
        _db().session.commit()


@given(parsers.parse('um qualificador folha de despesa "{num}" com dotação inicial de {valor} em {ano:d}'))
def qualificador_com_dotacao(app, num, valor, ano):
    from fluxocaixa.services.dotacao_service import criar_dotacao

    q = garantir_qualificador(num)
    if _dotacao(num, ano) is None:
        criar_dotacao(ano, q.seq_qualificador, Decimal(valor))


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


@when(parsers.parse('registro um crédito "{tipo}" de {valor} na dotação do qualificador "{num}" de {ano:d} com o ato "{ato}"'))
def registra_credito(app, contexto, tipo, valor, num, ano, ato):
    from fluxocaixa.services.dotacao_service import registrar_credito
    from fluxocaixa.services.validacao import RegraNegocioError

    dotacao = _dotacao(num, ano)
    try:
        registrar_credito(dotacao.seq_dotacao, tipo, Decimal(valor),
                          date(ano, 1, 15), ato)
        contexto["erro"] = None
    except RegraNegocioError as exc:
        contexto["erro"] = exc.mensagem


@when(parsers.parse('registro um crédito "{tipo}" de {valor} na dotação do qualificador "{num}" de {ano:d} sem ato'))
def registra_credito_sem_ato(app, contexto, tipo, valor, num, ano):
    from fluxocaixa.services.dotacao_service import registrar_credito
    from fluxocaixa.services.validacao import RegraNegocioError

    dotacao = _dotacao(num, ano)
    try:
        registrar_credito(dotacao.seq_dotacao, tipo, Decimal(valor),
                          date(ano, 1, 15), "")
        contexto["erro"] = None
    except RegraNegocioError as exc:
        contexto["erro"] = exc.mensagem


@when("confirmo essa liberação sem confirmação explícita do teto")
def confirma_sem(app, contexto, liberacao_atual):
    from fluxocaixa.services.liberacao_service import confirmar_liberacao
    from fluxocaixa.services.validacao import RegraNegocioError

    try:
        confirmar_liberacao(liberacao_atual.seq_liberacao)
        contexto["erro"] = None
    except RegraNegocioError as exc:
        contexto["erro"] = exc.mensagem


@then(parsers.parse('a dotação atualizada do qualificador "{num}" em {ano:d} é {valor}'))
def atualizada_e(app, num, ano, valor):
    from fluxocaixa.services.dotacao_service import dotacao_atualizada

    _db().session.expire_all()
    assert dotacao_atualizada(_dotacao(num, ano)) == \
        Decimal(valor).quantize(Decimal("0.01"))


@then(parsers.parse('a dotação do qualificador "{num}" em {ano:d} tem {qtd:d} eventos de crédito'))
def qtd_eventos(app, num, ano, qtd):
    from fluxocaixa.models import CreditoAdicional

    dotacao = _dotacao(num, ano)
    eventos = CreditoAdicional.query.filter_by(
        seq_dotacao=dotacao.seq_dotacao, ind_status='A').all()
    assert len(eventos) == qtd, f"esperava {qtd} eventos, veio {len(eventos)}"


@then(parsers.parse('a operação de dotação é rejeitada com a mensagem "{mensagem}"'))
def operacao_rejeitada(contexto, mensagem):
    assert contexto["erro"] == mensagem, f"esperava {mensagem!r}, veio {contexto['erro']!r}"


@then("essa liberação está confirmada sem exigência extra")
def confirmada_sem_exigencia(contexto, liberacao_atual):
    _db().session.expire_all()
    assert contexto["erro"] is None
    assert liberacao_atual.cod_situacao == 'C'
