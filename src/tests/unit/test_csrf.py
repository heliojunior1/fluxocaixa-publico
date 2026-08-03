"""Unitários da proteção CSRF (spec controle-acesso R12).

Change: protecao-csrf-global. Import de `fluxocaixa` é TARDIO (convenção).
"""
import pytest


def test_token_e_criado_uma_vez_e_reusado():
    from fluxocaixa.auth.csrf import CHAVE_SESSAO, obter_token

    sessao = {}
    primeiro = obter_token(sessao)
    assert sessao[CHAVE_SESSAO] == primeiro
    assert obter_token(sessao) == primeiro, (
        "o token é POR SESSÃO — rotacionar quebraria abas paralelas")


def test_tokens_de_sessoes_distintas_diferem():
    from fluxocaixa.auth.csrf import obter_token

    assert obter_token({}) != obter_token({})


def test_token_tem_entropia_suficiente():
    from fluxocaixa.auth.csrf import obter_token

    assert len(obter_token({})) >= 40


class _Req:
    def __init__(self, headers):
        self.headers = headers


@pytest.mark.parametrize("origem,host,esperado", [
    (None, "app.test", True),                       # cliente sem cabeçalho
    ("https://app.test", "app.test", True),
    ("https://app.test/pagina", "app.test", True),
    ("https://exemplo-externo.test", "app.test", False),
    ("https://app.test.evil.test", "app.test", False),  # sufixo enganoso
    ("about:blank", "app.test", False),                 # sem netloc
])
def test_origem_confere(origem, host, esperado):
    from fluxocaixa.auth.csrf import _origem_confere

    cabecalhos = {"host": host}
    if origem:
        cabecalhos["origin"] = origem
    assert _origem_confere(_Req(cabecalhos)) is esperado


def test_token_do_cabecalho_tem_precedencia_sobre_o_form():
    from fluxocaixa.auth.csrf import CAMPO_FORM, _token_da_requisicao

    req = _Req({"X-CSRF-Token": "do-cabecalho"})
    assert _token_da_requisicao(req, {CAMPO_FORM: "do-form"}) == "do-cabecalho"


def test_token_do_form_quando_nao_ha_cabecalho():
    from fluxocaixa.auth.csrf import CAMPO_FORM, _token_da_requisicao

    assert _token_da_requisicao(_Req({}), {CAMPO_FORM: "do-form"}) == "do-form"


def test_sem_token_em_lugar_nenhum():
    from fluxocaixa.auth.csrf import _token_da_requisicao

    assert _token_da_requisicao(_Req({}), None) is None
