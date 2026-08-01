"""Steps BDD — conector API REST e resolvedor de mapeamento (spec R19/R20)."""
import json as _json
from datetime import date
from decimal import Decimal

import httpx
import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from ..conftest_extracao import (
    execucoes_da_fonte,
    fonte_por_nome,
    garantir_conta,
    garantir_sistema_origem,
)

scenarios("../extracao-configuravel/conector_api_rest.feature")

URL_BASE = "https://api.mock/bb"
TOKEN_URL = "https://api.mock/bb/oauth/token"
PATH_TEMPLATE = "/v1/saldo/agencia/{agencia}/conta/{conta}"

LAYOUT_API = {
    "lista_path": "listaFundosInvestimento",
    "campos": [
        {"caminho": "codigoFundoInvestimento", "destino": "cod_fundo"},
        {"caminho": "nomeFundoInvestimento", "destino": "dsc_fundo"},
        {"caminho": "valorSaldoBruto", "destino": "val_saldo"},
    ],
}

# Catálogo de referência (fictício, estilo BB) — conta → fundos
CATALOGO = {
    "12345": [
        {"codigoFundoInvestimento": 9101, "nomeFundoInvestimento": "FUNDO ALFA", "valorSaldoBruto": 1850432.10},
        {"codigoFundoInvestimento": 9102, "nomeFundoInvestimento": "FUNDO BETA", "valorSaldoBruto": 925100.55},
    ],
    "37001": [],  # conta sem fundos
}


@pytest.fixture()
def contexto():
    return {}


@pytest.fixture()
def mock_api():
    """Estado programável do mock HTTP e o handler do MockTransport."""
    estado = {
        "tokens": 0,          # nº de emissões de token
        "primeiro_401": False,
        "usou_401": False,
        "primeiro_429": False,
        "usou_429": False,
        "conta_500": None,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path.endswith("/oauth/token"):
            estado["tokens"] += 1
            return httpx.Response(200, json={"access_token": f"tok-{estado['tokens']}"})
        # GET de saldo
        conta = request.url.path.rsplit("/", 1)[-1]
        if estado["primeiro_401"] and not estado["usou_401"]:
            estado["usou_401"] = True
            return httpx.Response(401, json={"erro": "token expirado"})
        if estado["primeiro_429"] and not estado["usou_429"]:
            estado["usou_429"] = True
            return httpx.Response(429, json={"erro": "rate limit"})
        if conta == estado["conta_500"]:
            return httpx.Response(500, json={"erro": "interno"})
        fundos = CATALOGO.get(conta, [])
        return httpx.Response(200, json={
            "quantidadeFundosInvestimento": len(fundos),
            "listaFundosInvestimento": fundos,
        })

    from fluxocaixa.extracao.conectores import api_rest

    api_rest._TRANSPORT_TESTE = httpx.MockTransport(handler)
    # backoff instantâneo nos testes
    _orig_backoffs = api_rest._BACKOFFS
    api_rest._BACKOFFS = [0, 0, 0]
    yield estado
    api_rest._TRANSPORT_TESTE = None
    api_rest._BACKOFFS = _orig_backoffs


def _config(contas):
    return {
        "url_base": URL_BASE,
        "path_template": PATH_TEMPLATE,
        "cod_banco": "001",
        "autenticacao": "OAUTH2",
        "token_url": TOKEN_URL,
        "client_id": "cid",
        "client_secret": "csecret",
        "scope": "fundos.info",
        "contas": [{"agencia": "0001", "conta": c} for c in contas],
    }


def _criar_fonte_api(nome, contas):
    from fluxocaixa.services.extracao_service import criar_fonte

    return criar_fonte(
        nom_fonte=nome, cod_tipo_conector="API_REST", sigla_sistema="SIS_X",
        json_config=_config(contas), json_layout=LAYOUT_API,
    )


# --------------------------------------------------------------------------
# Dado
# --------------------------------------------------------------------------

@given("que estou autenticado como administrador")
def autenticado_admin(app, _admin_pronto):
    from fluxocaixa.auth.contexto import definir_usuario_corrente

    definir_usuario_corrente(777)


@given(parsers.parse('um sistema de origem "{sigla}" cadastrado'))
def sistema_cadastrado(app, sigla):
    garantir_sistema_origem(sigla)


@given('o conector "API_REST" registrado')
def conector_api_registrado(app):
    from fluxocaixa.extracao import registry
    from fluxocaixa.extracao.conectores.api_rest import ConectorApiRest

    if "API_REST" not in registry.tipos_disponiveis():
        registry.registrar(ConectorApiRest())


@given("as contas de API cadastradas")
def contas_api(app):
    # cod_banco 001, agência 0001; contas normalizadas do catálogo
    garantir_conta("001/0001/12345")
    garantir_conta("001/0001/37001")
    garantir_conta("001/0001/9999")


@given(parsers.parse('uma fonte "{nome}" que devolve 2 fundos para a conta "{conta}"'))
def fonte_dois_fundos(app, nome, conta):
    _criar_fonte_api(nome, [conta])


@given(parsers.parse('uma fonte "{nome}" cuja conta "{conta}" não tem fundos'))
def fonte_conta_vazia(app, nome, conta):
    _criar_fonte_api(nome, [conta])


@given(parsers.parse('uma fonte "{nome}" que responde 401 na primeira chamada e 200 após renovar'))
def fonte_401(app, mock_api, nome):
    mock_api["primeiro_401"] = True
    _criar_fonte_api(nome, ["12345"])


@given(parsers.parse('uma fonte "{nome}" que responde 429 e depois 200'))
def fonte_429(app, mock_api, nome):
    mock_api["primeiro_429"] = True
    _criar_fonte_api(nome, ["12345"])


@given(parsers.parse('uma fonte "{nome}" com a conta "12345" ok e a conta "9999" respondendo 500'))
def fonte_parcial(app, mock_api, nome):
    mock_api["conta_500"] = "9999"
    _criar_fonte_api(nome, ["12345", "9999"])


# --------------------------------------------------------------------------
# Quando (mapeamento — R20)
# --------------------------------------------------------------------------

@when(parsers.parse('mapeio o item de fundo "{cod}" com saldo bruto "{valor}"'))
def mapeia_item(contexto, cod, valor):
    from fluxocaixa.extracao.mapeamento_json import mapear_item

    item = {"codigoFundoInvestimento": int(cod), "nomeFundoInvestimento": "X",
            "valorSaldoBruto": float(valor)}
    contexto["mapeado"] = mapear_item(item, LAYOUT_API, cod_banco="001",
                                      agencia="0001", conta="12345")


@when("mapeio uma resposta de saldo único sem lista_path")
def mapeia_sem_lista(contexto):
    from fluxocaixa.extracao.conector import ErroLinha, LinhaExtraida
    from fluxocaixa.extracao.mapeamento_json import itens, mapear_item

    layout = {"campos": LAYOUT_API["campos"]}
    resposta = {"codigoFundoInvestimento": 9101, "nomeFundoInvestimento": "X", "valorSaldoBruto": 10.0}
    emitidos = [mapear_item(it, layout, cod_banco="001", agencia="0001", conta="12345")
                for it in itens(resposta, layout.get("lista_path"))]
    contexto["linhas"] = [e for e in emitidos if isinstance(e, LinhaExtraida)]
    contexto["erros"] = [e for e in emitidos if isinstance(e, ErroLinha)]


@when("mapeio um item sem o campo de código do fundo")
def mapeia_sem_codigo(contexto):
    from fluxocaixa.extracao.conector import ErroLinha, LinhaExtraida
    from fluxocaixa.extracao.mapeamento_json import mapear_item

    item = {"nomeFundoInvestimento": "X", "valorSaldoBruto": 10.0}  # sem codigoFundoInvestimento
    r = mapear_item(item, LAYOUT_API, cod_banco="001", agencia="0001", conta="12345")
    contexto["linhas"] = [r] if isinstance(r, LinhaExtraida) else []
    contexto["erros"] = [r] if isinstance(r, ErroLinha) else []


# --------------------------------------------------------------------------
# Quando (execução — R19)
# --------------------------------------------------------------------------

@when(parsers.parse('executo a fonte "{nome}" para o dia "{dia}"'))
def executa_dia(app, mock_api, contexto, nome, dia):
    from fluxocaixa.extracao.conector import Janela
    from fluxocaixa.services.extracao_service import executar_fonte

    contexto["fonte_nome"] = nome
    contexto["mock"] = mock_api
    d = date.fromisoformat(dia)
    executar_fonte(fonte_por_nome(nome).seq_fonte_extracao, janela=Janela(d, d))


@when(parsers.parse('executo a fonte "{nome}" de "{ini}" a "{fim}"'))
def executa_janela(app, mock_api, contexto, nome, ini, fim):
    from fluxocaixa.extracao.conector import Janela
    from fluxocaixa.services.extracao_service import executar_fonte

    contexto["fonte_nome"] = nome
    contexto["mock"] = mock_api
    executar_fonte(fonte_por_nome(nome).seq_fonte_extracao,
                   janela=Janela(date.fromisoformat(ini), date.fromisoformat(fim)))


# --------------------------------------------------------------------------
# Então
# --------------------------------------------------------------------------

@then(parsers.parse('a linha mapeada tem fundo "{cod}" e saldo "{valor}"'))
def linha_mapeada(contexto, cod, valor):
    from fluxocaixa.extracao.conector import LinhaExtraida

    m = contexto["mapeado"]
    assert isinstance(m, LinhaExtraida), m
    assert m.cod_fundo == cod
    assert m.val_saldo == Decimal(valor).quantize(Decimal("0.01"))


@then(parsers.parse("o mapeamento produz {n_linhas:d} linhas e {n_erros:d} erros"))
def obtenho_map(contexto, n_linhas, n_erros):
    assert len(contexto["linhas"]) == n_linhas
    assert len(contexto["erros"]) == n_erros


@then(parsers.parse('a execução de API registra status "{status}" com {ok:d} inseridas e {erro:d} com erro'))
def execucao_api_status(contexto, status, ok, erro):
    execucoes = execucoes_da_fonte(contexto["fonte_nome"])
    assert execucoes, f"nenhuma execução para {contexto['fonte_nome']!r}"
    e = execucoes[-1]
    assert e.cod_status == status, (
        f"esperava {status}, veio {e.cod_status} (detalhe: {e.txt_detalhe_erros!r})"
    )
    assert (e.qtd_linhas_inseridas, e.qtd_linhas_erro) == (ok, erro)


@then("o token foi renovado uma vez")
def token_renovado(contexto):
    # 1 token inicial + 1 renovação = 2 emissões
    assert contexto["mock"]["tokens"] == 2, contexto["mock"]


@then(parsers.parse('os saldos gravados têm data "{dia}"'))
def saldos_data(contexto, dia):
    from fluxocaixa.models import SaldoContaFundo
    from fluxocaixa.models.base import db

    db.session.expire_all()
    d = date.fromisoformat(dia)
    ativos = SaldoContaFundo.query.filter_by(dat_saldo=d, ind_status="A").all()
    assert ativos, f"nenhum saldo ativo em {dia}"


@then(parsers.parse('o detalhe da execução de API menciona "{trecho}"'))
def detalhe_menciona(contexto, trecho):
    e = execucoes_da_fonte(contexto["fonte_nome"])[-1]
    assert e.txt_detalhe_erros and trecho in e.txt_detalhe_erros
