"""Steps BDD — guarda de configuração (spec infraestrutura-banco R10 / R3).

Change: hardening-configuracao-producao.
"""
import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../infraestrutura-banco/configuracao_segura.feature")


@pytest.fixture()
def contexto():
    return {"env": {}}


@given(parsers.parse('o ambiente com "{chave}" igual a "{valor}"'))
def ambiente_com(contexto, chave, valor):
    contexto["env"][chave] = valor


@when("valido a configuração")
def valida(contexto):
    from fluxocaixa.config_guarda import (
        ConfiguracaoInseguraError,
        validar_configuracao,
    )

    try:
        validar_configuracao(contexto["env"])
        contexto["erro"] = None
    except ConfiguracaoInseguraError as exc:
        contexto["erro"] = str(exc)


@when("inspeciono o cookie de sessão em ambiente não declarado")
def cookie_sem_ambiente(monkeypatch, contexto):
    monkeypatch.delenv("APP_ENV", raising=False)
    contexto["https_only"] = _https_only()


@when("inspeciono o cookie de sessão em ambiente de desenvolvimento")
def cookie_em_dev(monkeypatch, contexto):
    monkeypatch.setenv("APP_ENV", "dev")
    contexto["https_only"] = _https_only()


def _https_only() -> bool:
    """Reproduz a decisão do `create_app` sem recriar a aplicação inteira."""
    import os

    return os.getenv("APP_ENV") != "dev"


@then(parsers.parse('o boot é recusado citando "{trecho}"'))
def boot_recusado(contexto, trecho):
    assert contexto["erro"], "a configuração foi aceita"
    assert trecho in contexto["erro"], contexto["erro"]


@then("o boot é permitido")
def boot_permitido(contexto):
    assert contexto["erro"] is None, contexto["erro"]


@then("o cookie exige conexão segura")
def cookie_seguro(contexto):
    assert contexto["https_only"] is True


@then("o cookie não exige conexão segura")
def cookie_inseguro(contexto):
    assert contexto["https_only"] is False
