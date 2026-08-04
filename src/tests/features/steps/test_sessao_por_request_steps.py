"""Steps BDD — sessão por request (spec infraestrutura-banco R13).

O TestClient roda a aplicação numa thread própria (portal): a scoped_session
daquela thread é exatamente a que vazava entre requests. A alteração "por
fora" usa uma conexão crua do engine — nunca a sessão — para simular outro
worker/script alterando o banco.
"""
from sqlalchemy import text

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../infraestrutura-banco/sessao_por_request.feature")

QUAL = "1.66.1"


@pytest.fixture()
def contexto():
    return {}


def _limpar():
    from fluxocaixa.models import Qualificador
    from fluxocaixa.models.base import db

    db.session.rollback()
    q = Qualificador.query.filter_by(num_qualificador=QUAL).first()
    if q is not None:
        db.session.delete(q)
        db.session.commit()


@pytest.fixture(autouse=True)
def _ilha(app):
    _limpar()
    yield
    _limpar()


@given(parsers.parse('um qualificador de sessão com descrição "{descricao}"'))
def qualificador(app, descricao):
    from fluxocaixa.models import Qualificador
    from fluxocaixa.models.base import db

    db.session.add(Qualificador(num_qualificador=QUAL,
                                dsc_qualificador=descricao, ind_status='A'))
    db.session.commit()


@given(parsers.parse('que a página de qualificadores já foi aberta exibindo '
                     'essa descrição'))
def pagina_aberta(client, contexto):
    resp = client.get("/qualificadores")
    assert resp.status_code == 200
    assert "DESCRICAO SESSAO ANTES" in resp.text


@when(parsers.parse('a descrição é alterada diretamente no banco para '
                    '"{descricao}"'))
def altera_por_fora(app, descricao):
    from fluxocaixa.models.base import engine

    with engine.begin() as conexao:
        conexao.execute(
            text("UPDATE flc_qualificador SET dsc_qualificador = :d "
                 "WHERE num_qualificador = :n"),
            {"d": descricao, "n": QUAL})


@when("abro a página de qualificadores de novo")
def abre_de_novo(client, contexto):
    contexto["resp"] = client.get("/qualificadores")
    assert contexto["resp"].status_code == 200


@when("inspeciono a pilha de middlewares da aplicação")
def inspeciona_middlewares(app, contexto):
    contexto["middlewares"] = [m.cls.__name__ for m in app.user_middleware]


@then(parsers.parse('a página exibe "{descricao}"'))
def exibe(contexto, descricao):
    assert descricao in contexto["resp"].text


@then(parsers.parse('não exibe mais "{descricao}"'))
def nao_exibe(contexto, descricao):
    assert descricao not in contexto["resp"].text, (
        "a página devolveu a descrição do identity map antigo — a sessão "
        "não foi removida entre os requests")


@then("o middleware de sessão-por-request está registrado")
def middleware_registrado(contexto):
    assert "SessaoPorRequestMiddleware" in contexto["middlewares"], (
        contexto["middlewares"])
