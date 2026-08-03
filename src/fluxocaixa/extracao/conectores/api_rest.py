"""Conector de API REST configurável (spec R19).

Genérico e parametrizável: para cada conta da lista, resolve o `path_template`
e faz **apenas GET** na API, mapeando a resposta JSON pelo `json_layout`
(mapeamento pontilhado — R20). Autenticação OAUTH2/BEARER/BASIC; retry em 429,
renovação de token 1x em 401; só posição corrente (snapshot único). A API #54
de fundos do Banco do Brasil é apenas a configuração de referência.

Transporte: `httpx` direto (sem proxy corporativo). Nos testes, um
`httpx.MockTransport` é injetado por `_TRANSPORT_TESTE` (seam de teste).
"""
import time
from base64 import b64encode

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..conector import ErroLinha, Janela, ResultadoTeste
from ..mapeamento_json import LayoutApiRest, itens, mapear_item

AUTH_OAUTH2 = "OAUTH2"
AUTH_BEARER = "BEARER"
AUTH_BASIC = "BASIC"

_BACKOFFS = [2, 4, 8]           # 3 tentativas em 429
_PLACEHOLDERS_OK = {"agencia", "conta"}

# Seam de teste: quando definido, o cliente HTTP usa este transport.
_TRANSPORT_TESTE = None


class ContaAlvo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agencia: str
    conta: str


class ConfigApiRest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url_base: str
    path_template: str
    cod_banco: str
    autenticacao: str
    contas: list[ContaAlvo]
    timeout: int = 30
    # OAUTH2
    token_url: str | None = None
    client_id: str | None = None
    client_secret: str | None = Field(default=None, json_schema_extra={"secreto": True})
    scope: str | None = None
    # BEARER
    token: str | None = Field(default=None, json_schema_extra={"secreto": True})
    # BASIC
    usuario: str | None = None
    senha: str | None = Field(default=None, json_schema_extra={"secreto": True})

    @field_validator("autenticacao")
    @classmethod
    def _auth_valida(cls, v: str) -> str:
        if v not in (AUTH_OAUTH2, AUTH_BEARER, AUTH_BASIC):
            raise ValueError("autenticacao deve ser OAUTH2, BEARER ou BASIC")
        return v

    @field_validator("url_base", "token_url")
    @classmethod
    def _destino_confinado(cls, v: str | None) -> str | None:
        """Confina o destino (R23) — inclui a URL do token, não só a base.

        Deixar `token_url` de fora daria SSRF pela porta da autenticação: ela é
        chamada antes de qualquer coisa, e com credenciais.
        """
        if v:
            from ..confinamento import validar_url_externa

            validar_url_externa(v)
        return v

    @field_validator("path_template")
    @classmethod
    def _path_valido(cls, v: str) -> str:
        if ".." in v or "://" in v:
            raise ValueError("path_template não pode conter '..' nem esquema absoluto")
        import re

        for ph in re.findall(r"\{(\w+)\}", v):
            if ph not in _PLACEHOLDERS_OK:
                raise ValueError(
                    f"placeholder '{{{ph}}}' não suportado (use {_PLACEHOLDERS_OK})"
                )
        return v


def _cliente(config: dict) -> httpx.Client:
    kwargs = {"timeout": config.get("timeout", 30)}
    if _TRANSPORT_TESTE is not None:
        kwargs["transport"] = _TRANSPORT_TESTE
    return httpx.Client(**kwargs)


def _autenticar(cliente: httpx.Client, config: dict) -> str | None:
    """Devolve o Bearer token (OAUTH2/BEARER) ou None (BASIC usa header próprio)."""
    modo = config["autenticacao"]
    if modo == AUTH_BEARER:
        return config.get("token")
    if modo == AUTH_OAUTH2:
        cred = f"{config.get('client_id', '')}:{config.get('client_secret', '')}".encode()
        headers = {
            "Authorization": "Basic " + b64encode(cred).decode(),
            "Content-Type": "application/x-www-form-urlencoded",
        }
        body = "grant_type=client_credentials"
        if config.get("scope"):
            body += f"&scope={config['scope']}"
        resp = cliente.post(config["token_url"], content=body, headers=headers)
        if resp.status_code != 200:
            raise RuntimeError(f"OAuth falhou: HTTP {resp.status_code}")
        return resp.json()["access_token"]
    return None  # BASIC


def _headers(config: dict, token: str | None) -> dict:
    if config["autenticacao"] == AUTH_BASIC:
        cred = f"{config.get('usuario', '')}:{config.get('senha', '')}".encode()
        return {"Authorization": "Basic " + b64encode(cred).decode()}
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


def _get_saldo(cliente: httpx.Client, config: dict, url: str, token: str | None) -> dict:
    """GET com renovação de token 1x em 401 e backoff em 429. Só GET."""
    tentativa = 0
    renovou = False
    while True:
        resp = cliente.get(url, headers=_headers(config, token))
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 401 and not renovou and config["autenticacao"] == AUTH_OAUTH2:
            token = _autenticar(cliente, config)
            renovou = True
            continue
        if resp.status_code == 429 and tentativa < len(_BACKOFFS):
            time.sleep(_BACKOFFS[tentativa])
            tentativa += 1
            continue
        raise RuntimeError(f"GET {url} retornou HTTP {resp.status_code}")


class ConectorApiRest:
    tipo = "API_REST"
    layout_kind = "MAPEAMENTO"
    schema_config = ConfigApiRest
    schema_layout = LayoutApiRest

    def testar_conexao(self, config: dict) -> ResultadoTeste:
        try:
            with _cliente(config) as cliente:
                token = _autenticar(cliente, config)
            if config["autenticacao"] == AUTH_OAUTH2 and not token:
                return ResultadoTeste(ok=False, mensagem="Não foi possível obter token")
            return ResultadoTeste(ok=True, mensagem="Autenticação OK")
        except Exception as exc:  # falha de conexão é resultado, não crash
            return ResultadoTeste(ok=False, mensagem=str(exc))

    def extrair(self, config: dict, layout: dict | None, janela: Janela):
        layout = layout or {}
        lista_path = layout.get("lista_path")
        with _cliente(config) as cliente:
            token = _autenticar(cliente, config)
            for alvo in config["contas"]:
                agencia, conta = alvo["agencia"], alvo["conta"]
                url = config["url_base"] + config["path_template"].format(
                    agencia=agencia, conta=conta
                )
                try:
                    resposta = _get_saldo(cliente, config, url, token)
                except Exception as exc:
                    yield ErroLinha(numero=0, arquivo=f"conta {conta}", mensagem=str(exc))
                    continue
                for item in itens(resposta, lista_path):
                    linha = mapear_item(item, layout, cod_banco=config["cod_banco"],
                                        agencia=agencia, conta=conta)
                    # Snapshot: API não tem histórico → data = fim da janela
                    if hasattr(linha, "val_saldo"):
                        linha.dat_saldo = janela.data_fim
                    yield linha
        # Aviso (não-erro) quando a janela cobre mais de um dia
        if janela.data_fim != janela.data_inicio:
            yield ErroLinha(
                numero=0, arquivo="", aviso=True,
                mensagem="API sem histórico — snapshot único na data final da janela",
            )
