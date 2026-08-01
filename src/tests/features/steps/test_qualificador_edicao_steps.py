"""Steps BDD — edição de qualificador (spec cadastros-nucleo R18).

⚠️ O caminho de SUCESSO de `update_qualificador` não tinha teste algum. Este
arquivo existe para fechar essa lacuna, não só para cobrir a feature nova.
"""
import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../cadastros-nucleo/qualificador_edicao.feature")

RAMO = "7.2"


@pytest.fixture()
def contexto():
    return {}


def _db():
    from fluxocaixa.models.base import db

    return db


def _limpar():
    from fluxocaixa.models import Lancamento, Qualificador

    db = _db()
    db.session.rollback()
    quals = Qualificador.query.filter(
        Qualificador.num_qualificador.like(f"{RAMO}%")
    ).all()
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


def _no(num, dsc, pai_num=None, sigla=None):
    from fluxocaixa.models import CategoriaFiscal, Qualificador

    db = _db()
    pai = (Qualificador.query.filter_by(num_qualificador=pai_num).first()
           if pai_num else None)
    q = Qualificador(num_qualificador=num, dsc_qualificador=dsc, ind_status='A',
                     cod_qualificador_pai=pai.seq_qualificador if pai else None)
    if sigla:
        cat = CategoriaFiscal.query.filter_by(txt_sigla=sigla).first()
        assert cat is not None, sigla
        q.cod_categoria_fiscal = cat.seq_categoria_fiscal
    db.session.add(q)
    db.session.commit()
    return q


def _buscar(num):
    from fluxocaixa.models import Qualificador

    _db().session.expire_all()
    return Qualificador.query.filter_by(num_qualificador=num).first()


# --------------------------------------------------------------------------
# Dado
# --------------------------------------------------------------------------

@given(parsers.parse('o qualificador "{num}" chamado "{dsc}"'))
def dado_no(app, contexto, num, dsc):
    _no(num, dsc)


@given(parsers.parse('o qualificador "{num}" chamado "{dsc}" sob "{pai}"'))
def dado_no_sob(app, contexto, num, dsc, pai):
    _no(num, dsc, pai_num=pai)


@given(parsers.parse('o qualificador "{num}" chamado "{dsc}" sob "{pai}" com categoria "{sigla}"'))
def dado_no_sob_com_categoria(app, contexto, num, dsc, pai, sigla):
    _no(num, dsc, pai_num=pai, sigla=sigla)


# --------------------------------------------------------------------------
# Quando
# --------------------------------------------------------------------------

def _alterar(num, dsc, sigla=None):
    from fluxocaixa.models import CategoriaFiscal
    from fluxocaixa.services.qualificador_service import update_qualificador

    alvo = _buscar(num)
    cod_cat = None
    if sigla:
        cod_cat = CategoriaFiscal.query.filter_by(
            txt_sigla=sigla).first().seq_categoria_fiscal
    return update_qualificador(
        alvo.seq_qualificador, alvo.num_qualificador, dsc,
        alvo.cod_qualificador_pai, cod_categoria_fiscal=cod_cat,
    )


@when(parsers.parse('altero "{num}" para descrição "{dsc}" com categoria "{sigla}"'))
def quando_altero_com_categoria(app, contexto, num, dsc, sigla):
    _alterar(num, dsc, sigla)


@when(parsers.parse('altero "{num}" para descrição "{dsc}" sem categoria'))
def quando_altero_sem_categoria(app, contexto, num, dsc):
    _alterar(num, dsc)


# --------------------------------------------------------------------------
# Então
# --------------------------------------------------------------------------

@then(parsers.parse('o qualificador "{num}" tem descrição "{dsc}"'))
def entao_descricao(contexto, num, dsc):
    assert _buscar(num).dsc_qualificador == dsc


@then(parsers.parse('o qualificador "{num}" tem categoria própria "{sigla}"'))
def entao_categoria(contexto, num, sigla):
    q = _buscar(num)
    assert q.cod_categoria_fiscal is not None, "sem marcação própria"
    assert q.categoria_fiscal.txt_sigla == sigla


@then(parsers.parse('o qualificador "{num}" não tem categoria própria'))
def entao_sem_categoria(contexto, num):
    assert _buscar(num).cod_categoria_fiscal is None


@then(parsers.parse('o qualificador "{num}" tem pai "{pai}"'))
def entao_pai(contexto, num, pai):
    q = _buscar(num)
    assert q.pai is not None and q.pai.num_qualificador == pai
