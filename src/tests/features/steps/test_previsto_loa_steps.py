"""Steps BDD — previsto da LOA e teto (spec desembolso R17–R18).

Ilhas 2043 (fallback/teto) e 2052–2053 (perfil) — anos sem LOA nem realizado
de outros módulos.
"""
from datetime import date
from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .conftest_regra import garantir_qualificador

scenarios("../desembolso/previsto_loa.feature")


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
    from fluxocaixa.models.base import db

    q = garantir_qualificador(num)
    if not Loa.query.filter_by(num_ano=ano, seq_qualificador=q.seq_qualificador).first():
        db.session.add(Loa(num_ano=ano, seq_qualificador=q.seq_qualificador,
                           val_loa=Decimal(valor), ind_status='A'))
        db.session.commit()


@given(parsers.parse('um qualificador folha de despesa "{num}"'))
def qualificador_simples(app, num):
    garantir_qualificador(num)


@given(parsers.parse('uma saída realizada de {valor} em "{dat}" no qualificador "{num}"'))
def saida_realizada(app, valor, dat, num):
    from fluxocaixa.models import Lancamento, OrigemLancamento
    from fluxocaixa.models.base import db

    q = garantir_qualificador(num)
    origem = OrigemLancamento.query.filter_by(dsc_origem_lancamento='Manual').first()
    db.session.add(Lancamento(
        dat_lancamento=date.fromisoformat(dat), seq_qualificador=q.seq_qualificador,
        val_lancamento=Decimal(valor), cod_tipo_lancamento='D',
        cod_origem_lancamento=origem.cod_origem_lancamento,
        cod_pessoa_inclusao=1, ind_status='A'))
    db.session.commit()


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
    return confirmar_liberacao(liberacao.seq_liberacao, confirmado=True)


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


@when(parsers.parse('consulto o previsto mensal de {ano:d}'))
def consulta_previsto(app, contexto, ano):
    from fluxocaixa.services.previsto_loa_service import previsto_mensal

    contexto["previsto"] = previsto_mensal(ano)


@when("confirmo essa liberação sem confirmação explícita do teto")
def confirma_sem(app, contexto, liberacao_atual):
    from fluxocaixa.services.liberacao_service import confirmar_liberacao
    from fluxocaixa.services.validacao import RegraNegocioError

    try:
        confirmar_liberacao(liberacao_atual.seq_liberacao)
        contexto["erro"] = None
    except RegraNegocioError as exc:
        contexto["erro"] = exc.mensagem


@when("confirmo essa liberação com confirmação explícita do teto")
def confirma_com(app, contexto, liberacao_atual):
    from fluxocaixa.services.liberacao_service import confirmar_liberacao

    confirmar_liberacao(liberacao_atual.seq_liberacao, confirmado=True)


@then(parsers.parse('o previsto do mês {mes:d} de {ano:d} é {valor}'))
def previsto_do_mes(contexto, mes, ano, valor):
    assert contexto["previsto"][mes] == Decimal(valor).quantize(Decimal("0.01")), \
        contexto["previsto"]


@then(parsers.parse('a operação do teto é rejeitada com a mensagem "{mensagem}"'))
def teto_rejeitado(contexto, mensagem):
    assert contexto["erro"] == mensagem, f"esperava {mensagem!r}, veio {contexto['erro']!r}"


@then(parsers.parse('essa liberação está confirmada e o evento registra o excedente "{texto}"'))
def confirmada_com_excedente(liberacao_atual, texto):
    from fluxocaixa.models import LiberacaoEvento

    _db().session.expire_all()
    assert liberacao_atual.cod_situacao == 'C'
    evento = (LiberacaoEvento.query
              .filter_by(seq_liberacao=liberacao_atual.seq_liberacao,
                         cod_tipo_evento='CONFIRMACAO').first())
    assert evento is not None and evento.dsc_justificativa == texto


@then("essa liberação está confirmada sem exigência extra")
def confirmada_sem_exigencia(contexto, liberacao_atual):
    _db().session.expire_all()
    assert contexto["erro"] is None
    assert liberacao_atual.cod_situacao == 'C'
