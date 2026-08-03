"""Steps BDD — cabeçalhos de segurança (spec controle-acesso R11).

Change: headers-seguranca-http.
"""
import re
from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../controle-acesso/headers_seguranca.feature")

BASE_HTML = Path(__file__).resolve().parents[4] / "templates" / "base.html"


@pytest.fixture()
def contexto():
    return {}


@given("que estou autenticado como administrador")
def autenticado_admin(app, _admin_pronto):
    from fluxocaixa.auth.contexto import definir_usuario_corrente

    definir_usuario_corrente(777)


@given("que o ambiente é de produção")
def ambiente_prod(monkeypatch):
    monkeypatch.setenv("APP_ENV", "prod")


@given("que o ambiente não é de produção")
def ambiente_nao_prod(monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev")


@when("abro uma tela do sistema")
def abre_tela(client, contexto):
    contexto["resp"] = client.get("/saldos")


@when("inspeciono o template base")
def inspeciona_base(contexto):
    contexto["base_html"] = BASE_HTML.read_text(encoding="utf-8")


@then(parsers.parse('a resposta tem o cabeçalho "{nome}"'))
def tem_cabecalho(contexto, nome):
    assert nome in contexto["resp"].headers, (
        f"cabeçalho {nome} ausente: {dict(contexto['resp'].headers)}")


@then(parsers.parse('a resposta não tem o cabeçalho "{nome}"'))
def nao_tem_cabecalho(contexto, nome):
    assert nome not in contexto["resp"].headers, (
        f"{nome} não deveria ser emitido fora de produção — em dev fixaria "
        "HTTPS no navegador do desenvolvedor")


@then(parsers.parse('a resposta tem o cabeçalho "{nome}" com "{valor}"'))
def cabecalho_com_valor(contexto, nome, valor):
    assert contexto["resp"].headers.get(nome) == valor


@then("a política de conteúdo nega enquadramento por outra origem")
def nega_enquadramento(contexto):
    csp = contexto["resp"].headers.get("Content-Security-Policy", "")
    assert "frame-ancestors 'none'" in csp, csp


@then("nenhum recurso é carregado de origem externa")
def sem_origem_externa(contexto):
    externos = re.findall(
        r'(?:src|href)\s*=\s*["\'](https?://[^"\']+)', contexto["base_html"])
    importados = re.findall(r"@import\s+url\(['\"]?(https?://[^)'\"]+)",
                            contexto["base_html"])
    assert not externos and not importados, (
        f"assets externos no base.html: {externos + importados}")
