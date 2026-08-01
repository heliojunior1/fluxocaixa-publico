"""Steps BDD — categoria fiscal herdada pela árvore (spec cadastros-nucleo R15).

Ramo `2.7`/`2.8` sob a raiz de DESPESA: as metas fiscais só olham despesa, e o
`tipo_fluxo` deriva do código da raiz — um ramo inventado não passaria por lá.
"""
import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../cadastros-nucleo/categoria_fiscal.feature")

RAMOS = ("2.7", "2.8")


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
    filtro = Qualificador.num_qualificador.like(f"{RAMOS[0]}%")
    for ramo in RAMOS[1:]:
        filtro = filtro | Qualificador.num_qualificador.like(f"{ramo}%")
    quals = Qualificador.query.filter(filtro).all()
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


def _categoria(sigla):
    from fluxocaixa.models import CategoriaFiscal

    return CategoriaFiscal.query.filter_by(txt_sigla=sigla).first()


def _no(num, dsc=None, pai_num=None, sigla=None):
    from fluxocaixa.models import Qualificador

    db = _db()
    pai = (Qualificador.query.filter_by(num_qualificador=pai_num).first()
           if pai_num else None)
    q = Qualificador.query.filter_by(num_qualificador=num).first()
    if q is None:
        q = Qualificador(num_qualificador=num,
                         dsc_qualificador=dsc or f"Rubrica {num}",
                         ind_status='A')
        db.session.add(q)
    q.cod_qualificador_pai = pai.seq_qualificador if pai else None
    if sigla:
        cat = _categoria(sigla)
        assert cat is not None, f"categoria {sigla} não semeada"
        q.cod_categoria_fiscal = cat.seq_categoria_fiscal
    db.session.commit()
    return q


def _resolver(qualificador):
    from fluxocaixa.services.categoria_fiscal_service import categoria_resolvida

    return categoria_resolvida(qualificador)


# --------------------------------------------------------------------------
# Dado
# --------------------------------------------------------------------------

@given(parsers.parse('o bloco "{num}" marcado como "{sigla}"'))
def dado_bloco_marcado(app, contexto, num, sigla):
    _no(num, sigla=sigla)


@given(parsers.parse('o bloco "{num}" marcado como "{sigla}" sob "{pai}"'))
def dado_bloco_marcado_sob(app, contexto, num, sigla, pai):
    _no(num, pai_num=pai, sigla=sigla)


@given(parsers.parse('o bloco "{num}" sem marcação'))
def dado_bloco_sem_marcacao(app, contexto, num):
    _no(num)


@given(parsers.parse('a folha "{num}" sem marcação sob "{pai}"'))
def dado_folha_sem_marcacao(app, contexto, num, pai):
    contexto["folha"] = _no(num, pai_num=pai)


@given(parsers.parse('a folha "{num}" marcada como "{sigla}" sob "{pai}"'))
def dado_folha_marcada(app, contexto, num, sigla, pai):
    contexto["folha"] = _no(num, pai_num=pai, sigla=sigla)


# --------------------------------------------------------------------------
# Quando
# --------------------------------------------------------------------------

@when(parsers.parse('consulto a categoria resolvida de "{num}"'))
def quando_consulto(contexto, num):
    from fluxocaixa.models import Qualificador

    q = Qualificador.query.filter_by(num_qualificador=num).first()
    contexto["resolvida"] = _resolver(q)


@when(parsers.parse('reaponto "{num}" para o bloco "{pai}"'))
def quando_reaponto(contexto, num, pai):
    from fluxocaixa.models import Qualificador

    db = _db()
    alvo = Qualificador.query.filter_by(num_qualificador=num).first()
    novo_pai = Qualificador.query.filter_by(num_qualificador=pai).first()
    alvo.cod_qualificador_pai = novo_pai.seq_qualificador
    db.session.commit()
    contexto["folha"] = alvo


@when("consulto a categoria resolvida dessa folha")
def quando_consulto_a_folha(contexto):
    _db().session.expire_all()
    contexto["resolvida"] = _resolver(contexto["folha"])


@when(parsers.parse('marco "{num}" como "{sigla}"'))
def quando_marco(contexto, num, sigla):
    from fluxocaixa.services.validacao import RegraNegocioError

    contexto.pop("erro", None)
    try:
        _no(num, sigla=sigla)
        contexto["marcado"] = True
    except RegraNegocioError as erro:
        contexto["erro"] = erro
        contexto["marcado"] = False


# --------------------------------------------------------------------------
# Então
# --------------------------------------------------------------------------

@then(parsers.parse('a categoria é "{sigla}"'))
def entao_categoria(contexto, sigla):
    resolvida = contexto["resolvida"]
    assert resolvida is not None, "esperava categoria, veio None"
    assert resolvida.txt_sigla == sigla, resolvida.txt_sigla


@then("não há categoria")
def entao_sem_categoria(contexto):
    assert contexto["resolvida"] is None, contexto["resolvida"]


@then("a marcação é aceita")
def entao_marcacao_aceita(contexto):
    assert "erro" not in contexto, str(contexto.get("erro"))
    assert contexto["marcado"] is True


@then(parsers.parse('a categoria resolvida de "{num}" é "{sigla}"'))
def entao_resolvida_de(contexto, num, sigla):
    from fluxocaixa.models import Qualificador

    _db().session.expire_all()
    q = Qualificador.query.filter_by(num_qualificador=num).first()
    resolvida = _resolver(q)
    assert resolvida is not None and resolvida.txt_sigla == sigla, resolvida
