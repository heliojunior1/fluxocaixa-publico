"""Steps BDD — apropriação pagamento ↔ liberação (spec desembolso R6–R8).

Ilha 2038, órgão 70002, qualificadores 2.8.x, fontes 1.580/1.581 — fictícios.
"""
from datetime import date
from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .conftest_regra import garantir_qualificador

scenarios("../desembolso/apropriacao.feature")

USUARIO_SESSAO = 12345


@pytest.fixture()
def contexto():
    return {}


def _db():
    from fluxocaixa.models.base import db

    return db


def _fonte(codigo: str, vigencia: int):
    from fluxocaixa.models import FonteRecurso

    ident, fonte = codigo.split(".", 1)
    return FonteRecurso.query.filter_by(
        cod_identificador_exercicio=ident, cod_fonte_stn=fonte,
        num_exercicio_vigencia=vigencia, ind_status='A').first()


def _executar(contexto, fn):
    from fluxocaixa.services.validacao import RegraNegocioError

    try:
        contexto["resultado"] = fn()
        contexto["erro"] = None
    except RegraNegocioError as exc:
        contexto["erro"] = exc.mensagem


# --------------------------------------------------------------------------
# Dado
# --------------------------------------------------------------------------

@given("que estou autenticado como administrador")
def autenticado_admin(app, _admin_pronto):
    from fluxocaixa.auth.contexto import definir_usuario_corrente

    definir_usuario_corrente(USUARIO_SESSAO)


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


@given(parsers.parse('um qualificador folha de despesa "{num}"'))
def qualificador_despesa(app, num):
    garantir_qualificador(num)


@given(parsers.parse('uma liberação confirmada de {valor} em "{dat}" no órgão "{cod:d}", qualificador "{num}" e fonte "{codigo}" da vigência {vigencia:d}'),
       target_fixture="liberacao_atual")
def liberacao_confirmada(app, valor, dat, cod, num, codigo, vigencia):
    from fluxocaixa.services.liberacao_service import confirmar_liberacao, criar_liberacao

    q = garantir_qualificador(num)
    fonte = _fonte(codigo, vigencia)
    liberacao = criar_liberacao(
        dat_liberacao=date.fromisoformat(dat), cod_orgao=cod,
        seq_qualificador=q.seq_qualificador,
        seq_fonte_recurso=fonte.seq_fonte_recurso,
        val_liberacao=Decimal(valor))
    return confirmar_liberacao(liberacao.seq_liberacao)


@given(parsers.parse('um pagamento de {valor} em "{dat}" no órgão "{cod:d}" e qualificador "{num}"'),
       target_fixture="pagamento_atual")
def pagamento_criado(app, valor, dat, cod, num):
    from fluxocaixa.domain import PagamentoCreate
    from fluxocaixa.models import Pagamento
    from fluxocaixa.services.pagamento_service import create_pagamento

    q = garantir_qualificador(num)
    out = create_pagamento(PagamentoCreate(
        dat_pagamento=date.fromisoformat(dat), cod_orgao=cod,
        seq_qualificador=q.seq_qualificador, val_pagamento=Decimal(valor)))
    return Pagamento.query.get(out.seq_pagamento)


@given(parsers.parse('aproprio {valor} dessa liberação nesse pagamento'))
@when(parsers.parse('aproprio {valor} dessa liberação nesse pagamento'))
def aproprio(app, contexto, liberacao_atual, pagamento_atual, valor):
    from fluxocaixa.services.pagamento_service import apropriar_pagamento

    _executar(contexto, lambda: apropriar_pagamento(
        pagamento_atual.seq_pagamento,
        [(liberacao_atual.seq_liberacao, Decimal(valor))]))


# --------------------------------------------------------------------------
# Quando
# --------------------------------------------------------------------------

@when(parsers.parse('tento registrar um pagamento de {valor} em "{dat}" sem qualificador'))
def pagamento_sem_qualificador(app, contexto, valor, dat):
    from fluxocaixa.domain import PagamentoCreate
    from fluxocaixa.services.pagamento_service import create_pagamento

    _executar(contexto, lambda: create_pagamento(PagamentoCreate(
        dat_pagamento=date.fromisoformat(dat), cod_orgao=70002,
        seq_qualificador=None, val_pagamento=Decimal(valor))))


@when("estorno a última apropriação desse pagamento")
def estorno_ultima(app, contexto, pagamento_atual):
    from fluxocaixa.models import PagamentoLiberacao
    from fluxocaixa.services.pagamento_service import estornar_apropriacao

    ultima = (PagamentoLiberacao.query
              .filter_by(seq_pagamento=pagamento_atual.seq_pagamento,
                         cod_tipo_evento='A')
              .order_by(PagamentoLiberacao.seq_pagamento_liberacao.desc())
              .first())
    _executar(contexto, lambda: estornar_apropriacao(ultima.seq_pagamento_liberacao))


@when("tento excluir esse pagamento com confirmação explícita")
def tenta_excluir(app, contexto, pagamento_atual):
    from fluxocaixa.services.pagamento_service import excluir_pagamento

    _executar(contexto, lambda: excluir_pagamento(
        pagamento_atual.seq_pagamento, confirmado=True))


@when(parsers.parse('tento alterar o valor desse pagamento para {valor}'))
def tenta_alterar(app, contexto, pagamento_atual, valor):
    from fluxocaixa.services.pagamento_service import alterar_pagamento

    _executar(contexto, lambda: alterar_pagamento(
        pagamento_atual.seq_pagamento, val_pagamento=Decimal(valor)))


@when("abro a lista de pagamentos como administrador")
def abre_lista(client, contexto):
    contexto["resp"] = client.get("/pagamentos")


# --------------------------------------------------------------------------
# Então
# --------------------------------------------------------------------------

@then(parsers.parse('a operação de pagamento é rejeitada com a mensagem "{mensagem}"'))
def pagamento_rejeitado(contexto, mensagem):
    assert contexto["erro"] == mensagem, f"esperava {mensagem!r}, veio {contexto['erro']!r}"


@then(parsers.parse('o saldo restante dessa liberação é {valor}'))
def saldo_restante(liberacao_atual, valor):
    from fluxocaixa.services.liberacao_service import consumo_da_liberacao

    _db().session.expire_all()
    saldo = Decimal(liberacao_atual.val_liberacao) - consumo_da_liberacao(
        liberacao_atual.seq_liberacao)
    assert saldo == Decimal(valor).quantize(Decimal("0.01")), saldo


@then(parsers.parse('o pagamento referencia a fonte "{codigo}" da vigência {vigencia:d}'))
def pagamento_com_fonte(pagamento_atual, codigo, vigencia):
    _db().session.expire_all()
    fonte = _fonte(codigo, vigencia)
    assert pagamento_atual.seq_fonte_recurso == fonte.seq_fonte_recurso


@then("o pagamento não referencia fonte alguma")
def pagamento_sem_fonte(pagamento_atual):
    _db().session.expire_all()
    assert pagamento_atual.seq_fonte_recurso is None


@then("esse pagamento aparece com o destaque de sem apropriação")
def destaque_sem_apropriacao(contexto, pagamento_atual):
    assert contexto["resp"].status_code == 200
    assert f'badge-sem-apropriacao-{pagamento_atual.seq_pagamento}' in contexto["resp"].text
