"""Steps BDD — tela do dicionário de termos (spec automacao-lancamentos R9)."""
import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from ..conftest_permissoes import criar_usuario_com_perfil
from .conftest_regra import criar_termo, termo_por_nome

scenarios("../automacao-lancamentos/tela_termos.feature")


@pytest.fixture()
def contexto():
    return {}


@pytest.fixture(autouse=True)
def _termos_limpos(app):
    """Este módulo é o dono do cadastro de termos: parte de um dicionário vazio."""
    from fluxocaixa.models import TermoRegra
    from fluxocaixa.models.base import db

    db.session.rollback()
    db.session.query(TermoRegra).delete()
    db.session.commit()


def _cliente_perfil(app, perfil):
    from fastapi.testclient import TestClient

    login, senha, _ = criar_usuario_com_perfil(perfil)
    tc = TestClient(app, follow_redirects=False, headers={"Accept": "text/html"})
    resp = tc.post("/login", data={"usuario": login, "senha": senha})
    assert resp.status_code in (302, 303), f"login do perfil {perfil} falhou"
    return tc


@given("que estou autenticado como administrador")
def autenticado_admin(app, client, contexto):
    # Accept text/html: é o que um browser manda, e é o que faz o handler
    # global devolver flash+redirect em vez de 400 JSON
    client.headers.update({"Accept": "text/html"})
    client.follow_redirects = False
    contexto["cliente"] = client


@given("que estou autenticado como usuário só de consulta")
def autenticado_consulta(app, contexto):
    contexto["cliente"] = _cliente_perfil(app, "CONSULTA")


@given(parsers.parse('o termo "{nom}" cadastrado para o atributo "{campo}"'))
def termo_existente(app, nom, campo):
    if termo_por_nome(nom) is None:
        criar_termo(nom, "ATRIBUTO", campo, "TEXTO")


@when(parsers.parse('cadastro pela tela o termo "{nom}" para o atributo "{campo}" '
                    'do tipo "{tipo}"'))
def cadastra_atributo(app, contexto, nom, campo, tipo):
    contexto["resp"] = contexto["cliente"].post('/termos-regra/add', data={
        'nom_termo': nom, 'cod_origem_campo': 'ATRIBUTO',
        'nom_campo': campo, 'cod_tipo': tipo,
    })


@when(parsers.parse('cadastro pela tela o termo "{nom}" para a coluna "{campo}" '
                    'do tipo "{tipo}"'))
def cadastra_coluna(app, contexto, nom, campo, tipo):
    contexto["resp"] = contexto["cliente"].post('/termos-regra/add', data={
        'nom_termo': nom, 'cod_origem_campo': 'COLUNA',
        'nom_campo': campo, 'cod_tipo': tipo,
    })


@when("abro a tela de termos")
def abre_tela(app, contexto):
    contexto["resp"] = contexto["cliente"].get('/termos-regra')


@when(parsers.parse('inativo pela tela o termo "{nom}"'))
def inativa(app, contexto, nom):
    seq = termo_por_nome(nom).seq_termo_regra
    contexto["resp"] = contexto["cliente"].post(
        f'/termos-regra/inativar/{seq}', data={'confirmado': 'true'})


def _html(contexto):
    resp = contexto["resp"]
    if resp.status_code in (302, 303):
        resp = contexto["cliente"].get(resp.headers['location'])
    return resp.text


@then(parsers.parse('a lista de termos mostra "{nom}" ativo'))
def lista_mostra(app, contexto, nom):
    termo = termo_por_nome(nom)
    assert termo is not None and termo.ind_status == 'A', "termo não foi criado"
    assert nom in contexto["cliente"].get('/termos-regra').text


@then(parsers.parse('a tela de termos mostra erro contendo "{trecho}"'))
def tela_mostra_erro(app, contexto, trecho):
    html = _html(contexto)
    assert 'flash-erro' in html, "esperava flash de erro"
    assert trecho.lower() in html.lower(), html[:400]


@then("as opções de coluna são exatamente a whitelist")
def opcoes_whitelist(app, contexto):
    from fluxocaixa.models.termo_regra import COLUNAS_PERMITIDAS

    html = contexto["resp"].text
    for coluna in COLUNAS_PERMITIDAS:
        assert coluna in html, f"faltou a coluna permitida {coluna}"
    # colunas de controle não podem ser oferecidas
    for proibida in ('ind_status_processamento', 'dsc_erro', 'seq_execucao_extracao'):
        assert proibida not in html, f"ofereceu coluna de controle: {proibida}"


@then(parsers.parse('a lista de termos não mostra "{nom}" entre os ativos'))
def lista_nao_mostra(app, nom):
    termo = termo_por_nome(nom)
    assert termo is not None, "o termo foi apagado em vez de inativado"
    assert termo.ind_status == 'I'


@then("não vejo a ação de novo termo")
def sem_acao_novo(app, contexto):
    assert 'data-testid="novo-termo"' not in contexto["resp"].text
