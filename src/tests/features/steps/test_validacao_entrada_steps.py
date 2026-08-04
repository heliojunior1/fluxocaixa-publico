"""Steps BDD — entrada inválida nunca vira 500 (infraestrutura-banco R15)."""
import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../infraestrutura-banco/validacao_entrada.feature")


@pytest.fixture()
def contexto():
    return {}


@when(parsers.parse('requisito a tela de lançamentos com page "{valor}"'))
def tela_lancamentos(client, contexto, valor):
    contexto["resp"] = client.get(f"/saldos?page={valor}")


@when(parsers.parse('requisito a conferência com fim "{valor}"'))
def conferencia(client, contexto, valor):
    contexto["resp"] = client.get(f"/conferencia?fim={valor}")


@when("requisito os eventos do DFC sem o parâmetro seq")
def dfc_eventos_sem_seq(client, contexto):
    contexto["resp"] = client.get("/relatorios/dfc/eventos?periodo=mes&col=1")


@given(parsers.parse('que a execução do backtest falhará com "{segredo}"'))
def calculo_falha(app, monkeypatch, segredo):
    from fluxocaixa.services import backtest_service

    def _explode(*args, **kwargs):
        raise RuntimeError(f"detalhe interno: {segredo} /caminho/secreto.db")

    monkeypatch.setattr(backtest_service, "executar_backtest", _explode)


@when("executo o backtest pela API")
def executa_backtest(client, contexto):
    contexto["resp"] = client.post(
        "/relatorios/backtest/executar",
        json={"anos_treino": [2020], "anos_teste": [2021],
              "modelos": ["MEDIA_HISTORICA"]})


@then("a resposta não é erro de servidor")
def nao_500(contexto):
    assert contexto["resp"].status_code != 500, (
        "entrada inválida do usuário virou 500 — deveria ser erro de negócio "
        "com mensagem citando o campo")


@then("a resposta é 500 com mensagem genérica")
def resposta_generica(contexto):
    assert contexto["resp"].status_code == 500


@then(parsers.parse('"{segredo}" não aparece no corpo'))
def sem_segredo(contexto, segredo):
    assert segredo not in contexto["resp"].text, (
        "str(e) da exceção interna vazou para o cliente — caminho/SQL/schema "
        "expostos")
