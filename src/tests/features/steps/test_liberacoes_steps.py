"""Steps BDD — liberações do desembolso (spec desembolso R1–R5).

Ilha de datas 2038, órgão 70001 e qualificadores 2.7.x (despesa) / 1.7.9
(receita) — todos fictícios. A apropriação usa o modelo direto (a UI é F7.1b).
"""
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

from ..conftest_permissoes import criar_usuario_com_perfil
from .conftest_regra import garantir_qualificador

scenarios("../desembolso/liberacoes.feature")

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


def _criar_liberacao(dat, cod_orgao, num_qualificador, seq_fonte, valor="1234.56"):
    from fluxocaixa.services.liberacao_service import criar_liberacao

    q = garantir_qualificador(num_qualificador)
    return criar_liberacao(
        dat_liberacao=date.fromisoformat(dat),
        cod_orgao=cod_orgao,
        seq_qualificador=q.seq_qualificador,
        seq_fonte_recurso=seq_fonte,
        val_liberacao=Decimal(valor),
    )


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
    orgao = Orgao.query.get(cod)
    if orgao is None:
        criar_orgao(cod, nom)
    elif orgao.ind_status != 'A':
        orgao.ind_status = 'A'
        _db().session.commit()


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
    assert num.startswith('2')
    garantir_qualificador(num)


@given(parsers.parse('um qualificador folha de receita "{num}"'))
def qualificador_receita(app, num):
    assert num.startswith('1')
    garantir_qualificador(num)


@given(parsers.parse('uma liberação em rascunho de {valor} em "{dat}" no qualificador "{num}" com a fonte "{codigo}" da vigência {vigencia:d}'),
       target_fixture="liberacao_atual")
def liberacao_rascunho(app, valor, dat, num, codigo, vigencia):
    fonte = _fonte(codigo, vigencia)
    return _criar_liberacao(dat, 70001, num, fonte.seq_fonte_recurso, valor)


@given(parsers.parse('uma liberação confirmada de {valor} em "{dat}" no qualificador "{num}" com a fonte "{codigo}" da vigência {vigencia:d}'),
       target_fixture="liberacao_atual")
def liberacao_confirmada(app, valor, dat, num, codigo, vigencia):
    from fluxocaixa.services.liberacao_service import confirmar_liberacao

    fonte = _fonte(codigo, vigencia)
    liberacao = _criar_liberacao(dat, 70001, num, fonte.seq_fonte_recurso, valor)
    return confirmar_liberacao(liberacao.seq_liberacao)


def _evento_apropriacao(liberacao, tipo, valor):
    from fluxocaixa.models import Pagamento, PagamentoLiberacao

    pagamento = Pagamento.query.first()
    if pagamento is None:
        pagamento = Pagamento(dat_pagamento=date(2038, 6, 1), cod_orgao=70001,
                              val_pagamento=Decimal("9999.99"))
        _db().session.add(pagamento)
        _db().session.flush()
    _db().session.add(PagamentoLiberacao(
        seq_pagamento=pagamento.seq_pagamento,
        seq_liberacao=liberacao.seq_liberacao,
        cod_tipo_evento=tipo,
        val_apropriado=Decimal(valor),
        dat_evento=date(2038, 6, 20),
    ))
    _db().session.commit()


@given(parsers.parse('uma apropriação de {valor} nessa liberação'))
def apropriacao(app, liberacao_atual, valor):
    _evento_apropriacao(liberacao_atual, 'A', valor)


@given(parsers.parse('um estorno de {valor} nessa liberação'))
def estorno(app, liberacao_atual, valor):
    _evento_apropriacao(liberacao_atual, 'E', valor)


@given(parsers.parse('um usuário do desembolso autenticado com o perfil "{perfil}"'),
       target_fixture="navegador")
def usuario_perfil(app, perfil):
    login, senha, seq = criar_usuario_com_perfil(perfil)
    tc = TestClient(app, follow_redirects=False, headers={"Accept": "text/html"})
    resp = tc.post("/login", data={"usuario": login, "senha": senha})
    assert resp.status_code in (302, 303)
    return tc


# --------------------------------------------------------------------------
# Quando
# --------------------------------------------------------------------------

@when(parsers.parse('crio uma liberação de {valor} em "{dat}" para o órgão "{cod:d}", qualificador "{num}" e fonte "{codigo}" da vigência {vigencia:d}'),
      target_fixture="liberacao_atual")
def cria_liberacao(app, contexto, valor, dat, cod, num, codigo, vigencia):
    fonte = _fonte(codigo, vigencia)
    _executar(contexto, lambda: _criar_liberacao(dat, cod, num, fonte.seq_fonte_recurso, valor))
    return contexto.get("resultado")


@when(parsers.parse('tento criar uma liberação em "{dat}" no qualificador "{num}" com a fonte "{codigo}" da vigência {vigencia:d}'))
def tenta_criar(app, contexto, dat, num, codigo, vigencia):
    fonte = _fonte(codigo, vigencia)
    _executar(contexto, lambda: _criar_liberacao(dat, 70001, num, fonte.seq_fonte_recurso))


@when(parsers.parse('tento criar uma liberação em "{dat}" no qualificador "{num}" sem fonte'))
def tenta_criar_sem_fonte(app, contexto, dat, num):
    _executar(contexto, lambda: _criar_liberacao(dat, 70001, num, None))


@when(parsers.parse('tento criar uma liberação de valor {valor} em "{dat}" no qualificador "{num}" com a fonte "{codigo}" da vigência {vigencia:d}'))
def tenta_criar_valor(app, contexto, valor, dat, num, codigo, vigencia):
    fonte = _fonte(codigo, vigencia)
    _executar(contexto, lambda: _criar_liberacao(dat, 70001, num, fonte.seq_fonte_recurso, valor))


@when("confirmo essa liberação")
def confirma(app, contexto, liberacao_atual):
    from fluxocaixa.services.liberacao_service import confirmar_liberacao

    _executar(contexto, lambda: confirmar_liberacao(liberacao_atual.seq_liberacao))


@when("cancelo essa liberação sem confirmação explícita")
def cancela_sem_confirmado(app, contexto, liberacao_atual):
    from fluxocaixa.services.liberacao_service import cancelar_liberacao

    _executar(contexto, lambda: cancelar_liberacao(
        liberacao_atual.seq_liberacao, confirmado=False))


@when("cancelo essa liberação com confirmação explícita")
def cancela_com_confirmado(app, contexto, liberacao_atual):
    from fluxocaixa.services.liberacao_service import cancelar_liberacao

    _executar(contexto, lambda: cancelar_liberacao(
        liberacao_atual.seq_liberacao, justificativa="teste", confirmado=True))


@when(parsers.parse('consulto a visão semanal de "{dat}"'))
def consulta_visao(app, contexto, dat):
    from fluxocaixa.services.liberacao_service import visao_semanal

    contexto["visao"] = visao_semanal(date.fromisoformat(dat))


@when(parsers.parse('tento inativar o órgão "{cod:d}"'))
def tenta_inativar_orgao(app, contexto, cod):
    from fluxocaixa.services.orgao_service import inativar_orgao

    _executar(contexto, lambda: inativar_orgao(cod))


@when("esse usuário tenta confirmar essa liberação pela rota")
def confirma_pela_rota(navegador, contexto, liberacao_atual):
    contexto["resp"] = navegador.post(
        f"/liberacoes/{liberacao_atual.seq_liberacao}/confirmar")


# --------------------------------------------------------------------------
# Então
# --------------------------------------------------------------------------

@then(parsers.parse('a liberação existe em rascunho com natureza "{natureza}"'))
def liberacao_em_rascunho(liberacao_atual, natureza):
    _db().session.expire_all()
    assert liberacao_atual is not None
    assert liberacao_atual.cod_situacao == 'R'
    assert liberacao_atual.cod_natureza_obrigacao == natureza


@then(parsers.parse('a liberação tem um evento "{tipo}"'))
def liberacao_tem_evento(liberacao_atual, tipo):
    from fluxocaixa.models import LiberacaoEvento

    _db().session.expire_all()
    eventos = LiberacaoEvento.query.filter_by(
        seq_liberacao=liberacao_atual.seq_liberacao, cod_tipo_evento=tipo).all()
    assert eventos, f"sem evento {tipo}"
    assert all(e.dat_evento is not None for e in eventos)


@then(parsers.parse('a operação de liberação é rejeitada com a mensagem "{mensagem}"'))
def operacao_rejeitada(contexto, mensagem):
    assert contexto["erro"] == mensagem, f"esperava {mensagem!r}, veio {contexto['erro']!r}"


@then(parsers.parse('a situação dessa liberação é "{situacao}"'))
def situacao_da_liberacao(liberacao_atual, situacao):
    _db().session.expire_all()
    assert liberacao_atual.cod_situacao == situacao


@then(parsers.parse('o pendente do qualificador "{num}" é {valor}'))
def pendente_do_qualificador(num, valor):
    from fluxocaixa.models import Qualificador
    from fluxocaixa.services.liberacao_service import saldo_liberado_pendente

    _db().session.expire_all()
    q = Qualificador.query.filter_by(num_qualificador=num).first()
    pendente = saldo_liberado_pendente(seq_qualificador=q.seq_qualificador)
    assert pendente == Decimal(valor).quantize(Decimal("0.01")), pendente


@then(parsers.parse('o pendente da fonte "{codigo}" da vigência {vigencia:d} é {valor}'))
def pendente_da_fonte(codigo, vigencia, valor):
    from fluxocaixa.services.liberacao_service import saldo_liberado_pendente

    _db().session.expire_all()
    fonte = _fonte(codigo, vigencia)
    pendente = saldo_liberado_pendente(seq_fonte_recurso=fonte.seq_fonte_recurso)
    assert pendente == Decimal(valor).quantize(Decimal("0.01")), pendente


@then(parsers.parse('o total do dia "{dat}" na semana é {valor}'))
def total_do_dia(contexto, dat, valor):
    totais = contexto["visao"]["totais_dia"]
    assert totais[date.fromisoformat(dat)] == Decimal(valor).quantize(Decimal("0.01"))


@then(parsers.parse('a confirmação é negada com status {status:d}'))
def confirmacao_negada(contexto, status):
    assert contexto["resp"].status_code == status
