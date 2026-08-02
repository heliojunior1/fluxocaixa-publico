"""Steps BDD — repartição por fonte (spec fonte-recurso R8–R9).

Ilha de vigência 2039, qualificadores 1.8.1x (receita) / 2.8.11 (despesa).
"""
from datetime import date
from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .conftest_regra import garantir_qualificador

scenarios("../fonte-recurso/reparticao.feature")

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


def _qualificador(num):
    from fluxocaixa.models import Qualificador

    return Qualificador.query.filter_by(num_qualificador=num).first()


def _executar(contexto, fn):
    from fluxocaixa.services.validacao import RegraNegocioError

    try:
        contexto["resultado"] = fn()
        contexto["erro"] = None
    except RegraNegocioError as exc:
        contexto["erro"] = exc.mensagem


@given("que estou autenticado como administrador")
def autenticado_admin(app, _admin_pronto):
    from fluxocaixa.auth.contexto import definir_usuario_corrente

    definir_usuario_corrente(USUARIO_SESSAO)


@given(parsers.parse('a fonte "{codigo}" cadastrada na vigência {vigencia:d} como "{vinculada}"'))
def fonte_cadastrada(app, codigo, vigencia, vinculada):
    from fluxocaixa.services.fonte_recurso_service import criar_fonte

    _db().session.rollback()
    if _fonte(codigo, vigencia) is None:
        ident, fonte = codigo.split(".", 1)
        criar_fonte(ident, fonte, f"Fonte de teste {codigo}", vigencia,
                    vinculada='L' if vinculada == 'livre' else 'V')


@given(parsers.parse('um qualificador folha de receita "{num}"'))
@given(parsers.parse('um qualificador folha de despesa "{num}"'))
def qualificador_folha(app, num):
    garantir_qualificador(num)


def _definir(contexto, num, vigencia, itens):
    from fluxocaixa.services.reparticao_fonte_service import definir_reparticao

    q = _qualificador(num)
    _executar(contexto, lambda: definir_reparticao(q.seq_qualificador, vigencia, itens))


@given(parsers.parse('defino a repartição de "{num}" na vigência {vigencia:d} como {pct1} na fonte "{cod1}" e {pct2} na fonte "{cod2}"'))
@when(parsers.parse('defino a repartição de "{num}" na vigência {vigencia:d} como {pct1} na fonte "{cod1}" e {pct2} na fonte "{cod2}"'))
def define_duas(app, contexto, num, vigencia, pct1, cod1, pct2, cod2):
    _definir(contexto, num, vigencia, [
        (_fonte(cod1, vigencia).seq_fonte_recurso, Decimal(pct1)),
        (_fonte(cod2, vigencia).seq_fonte_recurso, Decimal(pct2)),
    ])


@when(parsers.parse('defino a repartição de "{num}" na vigência {vigencia:d} como {pct1} na fonte "{cod1}"'))
def define_uma(app, contexto, num, vigencia, pct1, cod1):
    _definir(contexto, num, vigencia, [
        (_fonte(cod1, vigencia).seq_fonte_recurso, Decimal(pct1)),
    ])


@given(parsers.parse('um lançamento de {valor} em "{num}" estampado na fonte "{codigo}" da vigência {vigencia:d}'))
def lancamento_estampado(app, valor, num, codigo, vigencia):
    from fluxocaixa.models import Lancamento, OrigemLancamento
    from fluxocaixa.models.base import db

    q = garantir_qualificador(num)
    fonte = _fonte(codigo, vigencia)
    origem = OrigemLancamento.query.filter_by(dsc_origem_lancamento='Manual').first()
    db.session.add(Lancamento(
        dat_lancamento=date(2039, 3, 10), seq_qualificador=q.seq_qualificador,
        val_lancamento=Decimal(valor), cod_tipo_lancamento='C',
        cod_origem_lancamento=origem.cod_origem_lancamento,
        seq_fonte_recurso=fonte.seq_fonte_recurso,
        cod_pessoa_inclusao=1, ind_status='A',
    ))
    db.session.commit()


@when(parsers.parse('reparto {valor} de "{num}" na vigência {vigencia:d}'))
def reparte(app, contexto, valor, num, vigencia):
    from fluxocaixa.services.reparticao_fonte_service import repartir_valor

    q = _qualificador(num)
    contexto["grupos"] = repartir_valor(q.seq_qualificador, vigencia, Decimal(valor))


@when(parsers.parse('consulto a sugestão do histórico de "{num}"'))
def consulta_sugestao(app, contexto, num):
    from fluxocaixa.services.reparticao_fonte_service import sugestao_do_historico

    q = _qualificador(num)
    contexto["sugestao"] = sugestao_do_historico(q.seq_qualificador)


@then(parsers.parse('a repartição de "{num}" na vigência {vigencia:d} tem {qtd:d} fontes'))
def reparticao_tem(num, vigencia, qtd):
    from fluxocaixa.services.reparticao_fonte_service import reparticoes_de

    _db().session.expire_all()
    q = _qualificador(num)
    assert len(reparticoes_de(q.seq_qualificador, vigencia)) == qtd


@then(parsers.parse('a operação de repartição é rejeitada com a mensagem "{mensagem}"'))
def reparticao_rejeitada(contexto, mensagem):
    assert contexto["erro"] == mensagem, f"esperava {mensagem!r}, veio {contexto['erro']!r}"


@then(parsers.parse('o grupo "{grupo}" da repartição recebe {valor}'))
def grupo_recebe(contexto, grupo, valor):
    assert contexto["grupos"][grupo] == Decimal(valor).quantize(Decimal("0.01")), \
        contexto["grupos"]


@then(parsers.parse('a sugestão traz {pct} para a fonte "{codigo}" da vigência {vigencia:d}'))
def sugestao_traz(contexto, pct, codigo, vigencia):
    fonte = _fonte(codigo, vigencia)
    entrada = next((s for s in contexto["sugestao"]
                    if s['seq_fonte_recurso'] == fonte.seq_fonte_recurso), None)
    assert entrada is not None, contexto["sugestao"]
    assert entrada['pct'] == Decimal(pct).quantize(Decimal("0.01"))
