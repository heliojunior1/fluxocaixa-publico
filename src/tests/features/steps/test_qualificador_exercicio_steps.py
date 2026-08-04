"""Steps BDD — qualificador por exercício e identidade estável.

Spec `cadastros-nucleo` R25–R26 (change qualificador-exercicio-identidade,
F10.1). Imports de app sempre tardios (isolamento de banco da suíte).
"""
import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../cadastros-nucleo/qualificador_exercicio.feature")

RAMOS = ("7.4", "7.5", "7.6")
ANOS_ILHA = (2070, 2071, 2072)


@pytest.fixture()
def contexto():
    return {}


def _db():
    from fluxocaixa.models.base import db

    return db


def _limpar():
    from sqlalchemy import or_

    from fluxocaixa.models import Lancamento, Qualificador

    db = _db()
    db.session.rollback()
    filtros = [Qualificador.num_qualificador.like(f"{r}%") for r in RAMOS]
    quals = Qualificador.query.filter(or_(*filtros)).all()
    if quals:
        seqs = [q.seq_qualificador for q in quals]
        Lancamento.query.filter(
            Lancamento.seq_qualificador.in_(seqs)
        ).delete(synchronize_session=False)
        db.session.commit()
        for q in sorted(quals, key=lambda x: -x.num_qualificador.count('.')):
            db.session.delete(q)
        db.session.commit()


@pytest.fixture(autouse=True)
def _ilha(app):
    _limpar()
    yield
    _limpar()


def _buscar(num, ano):
    from fluxocaixa.models import Qualificador

    return Qualificador.query.filter_by(
        num_qualificador=num, num_ano_exercicio=ano
    ).first()


def _criar(num, dsc, ano, pai=None):
    from fluxocaixa.services import qualificador_service

    return qualificador_service.create_qualificador(
        num, dsc,
        cod_qualificador_pai=pai.seq_qualificador if pai else None,
        num_ano_exercicio=ano,
    )


@given(parsers.parse('o qualificador "{num}" chamado "{dsc}" no exercício {ano:d}'))
def dado_qualificador(num, dsc, ano, contexto):
    q = _criar(num, dsc, ano)
    contexto[(num, ano)] = q.seq_qualificador
    return q


@given(parsers.parse(
    'o qualificador "{num}" chamado "{dsc}" no exercício {ano:d} sob o "{pai_num}" de {pai_ano:d}'))
def dado_qualificador_sob(num, dsc, ano, pai_num, pai_ano, contexto):
    pai = _buscar(pai_num, pai_ano)
    q = _criar(num, dsc, ano, pai=pai)
    contexto[(num, ano)] = q.seq_qualificador
    return q


@when(parsers.parse('crio o qualificador "{num}" chamado "{dsc}" no exercício {ano:d}'))
def quando_crio(num, dsc, ano, contexto):
    q = _criar(num, dsc, ano)
    contexto[(num, ano)] = q.seq_qualificador


@when(parsers.parse('tento criar o qualificador "{num}" chamado "{dsc}" no exercício {ano:d}'))
def quando_tento_criar(num, dsc, ano, contexto):
    from fluxocaixa.services.validacao import RegraNegocioError

    try:
        _criar(num, dsc, ano)
        contexto["erro"] = None
    except RegraNegocioError as e:
        contexto["erro"] = str(e)


@when(parsers.parse(
    'tento criar o qualificador "{num}" chamado "{dsc}" no exercício {ano:d} sob o "{pai_num}" de {pai_ano:d}'))
def quando_tento_criar_sob(num, dsc, ano, pai_num, pai_ano, contexto):
    from fluxocaixa.services.validacao import RegraNegocioError

    pai = _buscar(pai_num, pai_ano)
    try:
        _criar(num, dsc, ano, pai=pai)
        contexto["erro"] = None
    except RegraNegocioError as e:
        contexto["erro"] = str(e)


@when(parsers.parse('tento reapontar o "{num}" de {ano:d} para o pai "{pai_num}" de {pai_ano:d}'))
def quando_tento_reapontar(num, ano, pai_num, pai_ano, contexto):
    from fluxocaixa.services import qualificador_service
    from fluxocaixa.services.validacao import RegraNegocioError

    filho = _buscar(num, ano)
    pai = _buscar(pai_num, pai_ano)
    try:
        qualificador_service.update_qualificador(
            filho.seq_qualificador, filho.num_qualificador,
            filho.dsc_qualificador,
            cod_qualificador_pai=pai.seq_qualificador,
            confirmado=True,
        )
        contexto["erro"] = None
    except RegraNegocioError as e:
        contexto["erro"] = str(e)


def _gravar_lancamento(ano_data, qualificador):
    from datetime import date
    from decimal import Decimal

    from fluxocaixa.domain.lancamento import LancamentoCreate
    from fluxocaixa.services import lancamento_service
    from fluxocaixa.services.dominio_lancamento import (
        resolver_origem,
        resolver_tipo,
    )

    data = LancamentoCreate(
        dat_lancamento=date(ano_data, 6, 15),
        seq_qualificador=qualificador.seq_qualificador,
        val_lancamento=Decimal("1234.56"),
        cod_tipo_lancamento=resolver_tipo("Entrada").cod_tipo_lancamento,
        cod_origem_lancamento=resolver_origem("Manual").cod_origem_lancamento,
        dsc_lancamento="Lancamento ilha F10.1",
    )
    return lancamento_service.create_lancamento(data)


@when(parsers.parse(
    'tento gravar um lançamento datado de {ano_data:d} no qualificador "{num}" de {ano_q:d}'))
def quando_tento_gravar_lancamento(ano_data, num, ano_q, contexto):
    from fluxocaixa.services.validacao import RegraNegocioError

    qualificador = _buscar(num, ano_q)
    try:
        _gravar_lancamento(ano_data, qualificador)
        contexto["erro"] = None
    except RegraNegocioError as e:
        contexto["erro"] = str(e)


@when(parsers.parse(
    'gravo um lançamento datado de {ano_data:d} no qualificador "{num}" de {ano_q:d}'))
def quando_gravo_lancamento(ano_data, num, ano_q, contexto):
    qualificador = _buscar(num, ano_q)
    contexto["lancamento"] = _gravar_lancamento(ano_data, qualificador)


@when(parsers.parse('renumero com confirmação o "{num}" de {ano:d} para "{novo}"'))
def quando_renumero(num, ano, novo, contexto):
    from fluxocaixa.services import qualificador_service

    q = _buscar(num, ano)
    subarvore = [q] + q.get_todos_filhos()
    contexto["raizes_antes"] = {
        n.seq_qualificador: n.cod_rubrica_raiz for n in subarvore
    }
    qualificador_service.update_qualificador(
        q.seq_qualificador, novo, q.dsc_qualificador,
        cod_qualificador_pai=q.cod_qualificador_pai, confirmado=True,
    )
    _db().session.commit()


@when(parsers.parse(
    'reaponto com confirmação o "{num}" de {ano:d} para o pai "{pai_num}" com código "{novo}"'))
def quando_reaponto(num, ano, pai_num, novo, contexto):
    from fluxocaixa.services import qualificador_service

    filho = _buscar(num, ano)
    pai = _buscar(pai_num, ano)
    contexto["raiz_antes"] = filho.cod_rubrica_raiz
    qualificador_service.update_qualificador(
        filho.seq_qualificador, novo, filho.dsc_qualificador,
        cod_qualificador_pai=pai.seq_qualificador, confirmado=True,
    )
    _db().session.commit()


@then(parsers.parse('o qualificador "{num}" existe nos exercícios {ano_a:d} e {ano_b:d}'))
def entao_existe_nos_dois(num, ano_a, ano_b):
    assert _buscar(num, ano_a) is not None
    assert _buscar(num, ano_b) is not None


@then(parsers.parse('a operação é recusada com mensagem contendo "{trecho}"'))
def entao_recusada(trecho, contexto):
    assert contexto["erro"], "a operação deveria ter sido recusada"
    assert trecho.lower() in contexto["erro"].lower(), contexto["erro"]


@then("o lançamento é gravado com sucesso")
def entao_lancamento_gravado(contexto):
    assert contexto.get("lancamento") is not None


@then(parsers.parse('a raiz do "{num}" de {ano:d} é o seu próprio seq'))
def entao_raiz_propria(num, ano):
    q = _buscar(num, ano)
    _db().session.refresh(q)
    assert q.cod_rubrica_raiz == q.seq_qualificador


@then(parsers.parse('as raízes da subárvore "{num}" de {ano:d} permanecem as originais'))
def entao_raizes_intactas(num, ano, contexto):
    q = _buscar(num, ano)
    subarvore = [q] + q.get_todos_filhos()
    for no in subarvore:
        _db().session.refresh(no)
        assert no.cod_rubrica_raiz == contexto["raizes_antes"][no.seq_qualificador]


@then(parsers.parse('a raiz do "{num}" de {ano:d} é a original do "{origem}"'))
def entao_raiz_original(num, ano, origem, contexto):
    q = _buscar(num, ano)
    _db().session.refresh(q)
    assert q.cod_rubrica_raiz == contexto["raiz_antes"]
