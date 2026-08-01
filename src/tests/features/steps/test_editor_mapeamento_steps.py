"""Steps BDD — editor de mapeamento na tela (spec R17 mod / R22)."""
import json

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from ..conftest_extracao import (
    fonte_por_nome,
    garantir_conector_fake,
    garantir_sistema_origem,
)

scenarios("../extracao-configuravel/editor_mapeamento.feature")

MAPA = {
    "lista_path": "listaFundosInvestimento",
    "campos": [
        {"caminho": "codigoFundoInvestimento", "destino": "cod_fundo"},
        {"caminho": "nomeFundoInvestimento", "destino": "dsc_fundo"},
        {"caminho": "valorSaldoBruto", "destino": "val_saldo"},
    ],
}


@pytest.fixture()
def contexto():
    return {}


def _garantir_conectores(app):
    """API_REST/BANCO_SQL/FTP_ARQUIVO já são registrados no import; garante."""
    from fluxocaixa.extracao import registry
    from fluxocaixa.extracao.conectores import registrar_conectores_disponiveis

    registrar_conectores_disponiveis()
    assert {"FTP_ARQUIVO", "API_REST", "BANCO_SQL"} <= set(registry.tipos_disponiveis())


def _form_sql(nome, layout):
    return {
        "cod_tipo_conector": "BANCO_SQL",
        "nom_fonte": nome,
        "sigla_sistema": "SIS_X",
        "cod_destino": "SALDO_FUNDO",
        "txt_cron": "",
        "url_conexao": "sqlite:///./_naoexiste_mapa.db",
        "query": "SELECT 1 AS x WHERE :data_inicio <= :data_fim",
        "cod_banco": "001",
        "batch_size": "5000",
        "json_layout_raw": json.dumps(layout),
    }


# --------------------------------------------------------------------------
# Dado
# --------------------------------------------------------------------------

@given("que estou autenticado como administrador")
def autenticado_admin(app, _admin_pronto):
    from fluxocaixa.auth.contexto import definir_usuario_corrente

    definir_usuario_corrente(777)
    _garantir_conectores(app)


@given(parsers.parse('um sistema de origem "{sigla}" cadastrado'))
def sistema_cadastrado(app, sigla):
    garantir_sistema_origem(sigla)


@given('o conector de teste "FAKE" registrado')
def conector_fake_registrado(app):
    garantir_conector_fake()


# --------------------------------------------------------------------------
# Quando
# --------------------------------------------------------------------------

@when(parsers.parse('abro o formulário de nova fonte para o tipo "{tipo}"'))
def abro_form_nova(client, contexto, tipo):
    contexto["resp"] = client.get(f"/extracao/fontes/nova?tipo={tipo}")


@when(parsers.parse('cadastro pela tela a fonte SQL "{nome}" com um mapeamento válido'))
def cadastra_mapa_valido(client, contexto, nome):
    contexto["resp"] = client.post(
        "/extracao/fontes", data=_form_sql(nome, MAPA),
        headers={"Accept": "text/html"}, follow_redirects=True,
    )


@when(parsers.parse('cadastro pela tela a fonte SQL "{nome}" com transformação de mapeamento "{transf}"'))
def cadastra_mapa_invalido(client, contexto, nome, transf):
    layout = {"campos": [{"caminho": "x", "destino": "val_saldo", "transformacao": transf}]}
    contexto["resp"] = client.post(
        "/extracao/fontes", data=_form_sql(nome, layout),
        headers={"Accept": "text/html"}, follow_redirects=True,
    )


@when("faço o preview de mapeamento de uma amostra com 2 itens")
def preview_dois(app, client, contexto):
    from fluxocaixa.models import ExecucaoExtracao

    contexto["exec_antes"] = ExecucaoExtracao.query.count()
    amostra = {
        "listaFundosInvestimento": [
            {"codigoFundoInvestimento": 9101, "nomeFundoInvestimento": "ALFA", "valorSaldoBruto": 100.0},
            {"codigoFundoInvestimento": 9102, "nomeFundoInvestimento": "BETA", "valorSaldoBruto": 200.0},
        ]
    }
    contexto["resp"] = client.post("/extracao/fontes/preview-mapeamento", data={
        "amostra_json": json.dumps(amostra), "json_layout_raw": json.dumps(MAPA)})


@when("faço o preview de mapeamento de uma amostra com um item sem o código do fundo")
def preview_erro(client, contexto):
    amostra = {"listaFundosInvestimento": [
        {"nomeFundoInvestimento": "ALFA", "valorSaldoBruto": 100.0}]}
    contexto["resp"] = client.post("/extracao/fontes/preview-mapeamento", data={
        "amostra_json": json.dumps(amostra), "json_layout_raw": json.dumps(MAPA)})


# --------------------------------------------------------------------------
# Então
# --------------------------------------------------------------------------

@then("a tela mostra a seção de layout de arquivo")
def mostra_arquivo(contexto):
    assert 'data-testid="secao-layout"' in contexto["resp"].text


@then("a tela não mostra a seção de layout de arquivo")
def nao_mostra_arquivo(contexto):
    assert 'data-testid="secao-layout"' not in contexto["resp"].text


@then("a tela mostra a seção de mapeamento")
def mostra_mapeamento(contexto):
    assert 'data-testid="secao-mapeamento"' in contexto["resp"].text


@then("a tela não mostra a seção de mapeamento")
def nao_mostra_mapeamento(contexto):
    assert 'data-testid="secao-mapeamento"' not in contexto["resp"].text


@then(parsers.parse('a fonte "{nome}" tem o mapeamento salvo'))
def fonte_tem_mapa(nome):
    fonte = fonte_por_nome(nome)
    assert fonte is not None, "fonte não criada"
    assert fonte.json_layout and fonte.json_layout.get("campos")


@then("o cadastro de mapeamento é rejeitado")
def cadastro_rejeitado(contexto):
    # RegraNegocioError → flash renderizado após o redirect (200 seguido)
    assert "layout inválido" in contexto["resp"].text.lower() or \
           "transforma" in contexto["resp"].text.lower()


@then(parsers.parse('a fonte "{nome}" não existe'))
def fonte_nao_existe(nome):
    assert fonte_por_nome(nome) is None


@then(parsers.parse('o preview de mapeamento retorna {n_linhas:d} linhas e {n_erros:d} erros'))
def preview_contadores(contexto, n_linhas, n_erros):
    resp = contexto["resp"]
    assert resp.status_code == 200, resp.text
    dados = resp.json()
    assert len(dados["linhas"]) == n_linhas
    assert len(dados["erros"]) == n_erros


@then("o preview de mapeamento não registra execução")
def preview_sem_execucao(app, contexto):
    from fluxocaixa.models import ExecucaoExtracao
    from fluxocaixa.models.base import db

    db.session.expire_all()
    assert ExecucaoExtracao.query.count() == contexto["exec_antes"]
