"""Steps BDD — abertura de exercício (cadastros-nucleo R29, F10.3).

Imports de app sempre tardios (isolamento de banco da suíte).
"""
from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../cadastros-nucleo/abertura_exercicio.feature")

RAMO = "7.9"
ANO_ORIGEM, ANO_NOVO = 2084, 2085


@pytest.fixture()
def contexto():
    return {}


def _db():
    from fluxocaixa.models.base import db

    return db


def _limpar():
    from fluxocaixa.models import Loa, Qualificador

    db = _db()
    db.session.rollback()
    quals = Qualificador.query.filter(
        Qualificador.num_ano_exercicio.in_((ANO_ORIGEM, ANO_NOVO))).all()
    if quals:
        seqs = [q.seq_qualificador for q in quals]
        Loa.query.filter(Loa.seq_qualificador.in_(seqs)).delete(
            synchronize_session=False)
        db.session.commit()
        for q in sorted(quals, key=lambda x: -x.num_qualificador.count('.')):
            db.session.delete(q)
        db.session.commit()


@pytest.fixture(autouse=True)
def _ilha(app):
    _limpar()
    yield
    _limpar()


def _plano(ano):
    from fluxocaixa.models import Qualificador

    return Qualificador.query.filter_by(num_ano_exercicio=ano).all()


@given(parsers.parse(
    'o plano de origem no exercício {ano:d} com bloco "{bloco}" marcado '
    '"{sigla}", folha "{folha}" e a folha inativa "{inativa}"'))
def dado_plano_origem(ano, bloco, sigla, folha, inativa, contexto):
    from fluxocaixa.models import CategoriaFiscal
    from fluxocaixa.services import qualificador_service as svc

    cat = CategoriaFiscal.query.filter_by(txt_sigla=sigla).first()
    q_bloco = svc.create_qualificador(
        bloco, f"Bloco Abertura {ano}", num_ano_exercicio=ano,
        cod_categoria_fiscal=cat.seq_categoria_fiscal)
    q_folha = svc.create_qualificador(
        folha, f"Folha Abertura {ano}",
        cod_qualificador_pai=q_bloco.seq_qualificador, num_ano_exercicio=ano)
    q_inativa = svc.create_qualificador(
        inativa, f"Folha Inativa {ano}",
        cod_qualificador_pai=q_bloco.seq_qualificador, num_ano_exercicio=ano)
    svc.delete_qualificador(q_inativa.seq_qualificador, confirmado=True)
    _db().session.commit()
    contexto["origem"] = {
        "bloco": q_bloco, "folha": q_folha, "inativa": q_inativa,
    }


@given(parsers.parse('uma LOA de {valor} para a folha "{folha}" de {ano:d}'))
def dado_loa(valor, folha, ano, contexto):
    from fluxocaixa.models import Loa

    db = _db()
    db.session.add(Loa(
        num_ano=ano,
        seq_qualificador=contexto["origem"]["folha"].seq_qualificador,
        val_loa=Decimal(valor),
    ))
    db.session.commit()


def _abrir(origem, novo, confirmado):
    from fluxocaixa.services.qualificador_service import abrir_exercicio

    return abrir_exercicio(origem, novo, confirmado=confirmado)


@when(parsers.parse('abro com confirmação o exercício {novo:d} a partir de {origem:d}'))
def quando_abro(novo, origem, contexto):
    _abrir(origem, novo, True)


@when(parsers.parse('tento abrir o exercício {novo:d} a partir de {origem:d}'))
def quando_tento_abrir(novo, origem, contexto):
    from fluxocaixa.services.validacao import RegraNegocioError

    try:
        _abrir(origem, novo, True)
        contexto["erro"] = None
    except RegraNegocioError as e:
        contexto["erro"] = str(e)


@when(parsers.parse('tento abrir sem confirmação o exercício {novo:d} a partir de {origem:d}'))
def quando_tento_abrir_sem_confirmacao(novo, origem, contexto):
    from fluxocaixa.services.validacao import RegraNegocioError

    try:
        _abrir(origem, novo, False)
        contexto["erro"] = None
    except RegraNegocioError as e:
        contexto["erro"] = str(e)


def _por_codigo(ano, num):
    from fluxocaixa.models import Qualificador

    return Qualificador.query.filter_by(
        num_ano_exercicio=ano, num_qualificador=num).first()


@then(parsers.parse('o plano de {ano:d} tem "{bloco}" e "{folha}" com pai remapeado'))
def entao_plano_copiado(ano, bloco, folha):
    novo_bloco = _por_codigo(ano, bloco)
    novo_folha = _por_codigo(ano, folha)
    assert novo_bloco is not None and novo_folha is not None
    assert novo_folha.cod_qualificador_pai == novo_bloco.seq_qualificador
    assert novo_bloco.num_ano_exercicio == ano


@then(parsers.parse('a marcação própria "{sigla}" do "{bloco}" de {ano:d} é preservada'))
def entao_marcacao_preservada(sigla, bloco, ano):
    from fluxocaixa.models import CategoriaFiscal

    novo = _por_codigo(ano, bloco)
    cat = CategoriaFiscal.query.get(novo.cod_categoria_fiscal)
    assert cat is not None and cat.txt_sigla == sigla


@then(parsers.parse('as raízes do plano de {ano_novo:d} são as mesmas do plano de {ano_origem:d}'))
def entao_raizes_propagadas(ano_novo, ano_origem):
    raizes_origem = {q.num_qualificador: q.cod_rubrica_raiz
                     for q in _plano(ano_origem) if q.ind_status == 'A'}
    raizes_novo = {q.num_qualificador: q.cod_rubrica_raiz
                   for q in _plano(ano_novo)}
    assert raizes_novo == raizes_origem


@then(parsers.parse('o plano de {ano:d} não contém "{num}"'))
def entao_nao_contem(ano, num):
    assert _por_codigo(ano, num) is None


@then(parsers.parse('a folha inativa "{num}" de {ano:d} permanece inativa'))
def entao_inativa_intacta(num, ano):
    q = _por_codigo(ano, num)
    assert q is not None and q.ind_status == 'I'


@then(parsers.parse('a abertura é recusada com mensagem contendo "{trecho}"'))
def entao_recusada(trecho, contexto):
    assert contexto["erro"], "a abertura deveria ter sido recusada"
    assert trecho.lower() in contexto["erro"].lower(), contexto["erro"]


@then(parsers.parse('o exercício {ano:d} não tem plano'))
def entao_sem_plano(ano):
    assert _plano(ano) == []


@then(parsers.parse('não existe LOA para o exercício {ano:d}'))
def entao_sem_loa(ano):
    from fluxocaixa.models import Loa

    assert Loa.query.filter_by(num_ano=ano).count() == 0
