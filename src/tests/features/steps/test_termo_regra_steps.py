"""Steps BDD — dicionário de termos de regra (spec automacao-lancamentos R5)."""
import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .conftest_regra import criar_termo, termo_por_nome

scenarios("../automacao-lancamentos/termo_regra.feature")


@pytest.fixture()
def contexto():
    return {}


@pytest.fixture(autouse=True)
def _termos_limpos(app):
    """Este módulo é o dono do cadastro de termos: parte de um dicionário vazio.

    Sem isso, os termos criados por outro módulo da suíte (que os cria como
    pano de fundo) fazem o cadastro daqui bater em duplicidade.
    """
    from fluxocaixa.models import TermoRegra
    from fluxocaixa.models.base import db

    db.session.rollback()
    db.session.query(TermoRegra).delete()
    db.session.commit()


@given("que estou autenticado como administrador")
def autenticado_admin(app, _admin_pronto):
    from fluxocaixa.auth.contexto import definir_usuario_corrente

    definir_usuario_corrente(777)


@given(parsers.parse('o termo "{nom}" cadastrado para o atributo "{campo}"'))
def termo_existente(app, nom, campo):
    # idempotente: o banco persiste entre cenários do mesmo módulo
    if termo_por_nome(nom) is None:
        criar_termo(nom, "ATRIBUTO", campo, "TEXTO")


def _cadastrar(contexto, nom, origem, campo, tipo):
    from fluxocaixa.services.validacao import RegraNegocioError

    try:
        criar_termo(nom, origem, campo, tipo)
        contexto["erro"] = None
    except RegraNegocioError as exc:
        contexto["erro"] = exc.mensagem


@when(parsers.parse('cadastro o termo "{nom}" para o atributo "{campo}" do tipo "{tipo}"'))
def cadastra_atributo(app, contexto, nom, campo, tipo):
    _cadastrar(contexto, nom, "ATRIBUTO", campo, tipo)


@when(parsers.parse('cadastro o termo "{nom}" para a coluna "{campo}" do tipo "{tipo}"'))
def cadastra_coluna(app, contexto, nom, campo, tipo):
    _cadastrar(contexto, nom, "COLUNA", campo, tipo)


@then(parsers.parse('o termo "{nom}" existe ativo apontando para o atributo "{campo}"'))
def termo_ok_atributo(contexto, nom, campo):
    assert contexto.get("erro") is None, f"rejeitado: {contexto.get('erro')!r}"
    t = termo_por_nome(nom)
    assert t is not None and t.ind_status == 'A'
    assert (t.cod_origem_campo, t.nom_campo) == ("ATRIBUTO", campo)


@then(parsers.parse('o termo "{nom}" existe ativo apontando para a coluna "{campo}"'))
def termo_ok_coluna(contexto, nom, campo):
    assert contexto.get("erro") is None, f"rejeitado: {contexto.get('erro')!r}"
    t = termo_por_nome(nom)
    assert t is not None and t.ind_status == 'A'
    assert (t.cod_origem_campo, t.nom_campo) == ("COLUNA", campo)


@then(parsers.parse('o cadastro do termo é rejeitado com mensagem contendo "{trecho}"'))
def termo_rejeitado(contexto, trecho):
    assert contexto["erro"] is not None, "esperava rejeição"
    assert trecho.lower() in contexto["erro"].lower(), contexto["erro"]


@then(parsers.parse('o termo "{nom}" não existe'))
def termo_ausente(nom):
    assert termo_por_nome(nom) is None
