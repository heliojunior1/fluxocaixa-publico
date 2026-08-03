"""Pré-processamento de importações de arquivo (spec importacao-arquivos).

Fluxo: upload → parse+validação SEM gravar (preview linha a linha) → staging
em disco (token amarrado à sessão, TTL) → confirmação grava exatamente as
linhas válidas. Cada tipo de importação registra um adapter.
"""
import json
import os
import secrets
import time
from dataclasses import asdict, dataclass, field

from ..config import BASE_DIR
from .validacao import RegraNegocioError

STAGING_DIR = os.path.join(BASE_DIR, "instance", "uploads")
TTL_SEGUNDOS = 30 * 60
MAX_LINHAS = 10_000

# Teto de bytes do upload (importacao-arquivos R6). Folgado para as planilhas
# reais do domínio e longe do que derruba o processo — que serve a TODOS os
# usuários, então esgotar sua memória derruba a aplicação inteira, não só a
# requisição (produção roda --workers 1).
MAX_UPLOAD_BYTES = int(os.getenv("IMPORTACAO_MAX_BYTES", 5 * 1024 * 1024))

EXTENSOES_SUPORTADAS = (".csv", ".txt", ".xlsx")


async def ler_upload_limitado(arquivo, *, max_bytes: int | None = None) -> bytes:
    """Lê o upload recusando o que passar do teto, SEM materializá-lo inteiro.

    Ler `limite + 1` responde "estourou?" sem carregar o arquivo: se voltarem
    `limite + 1` bytes, sabe-se que há mais. A validação de `MAX_LINHAS` que já
    existia roda DEPOIS do parse completo — inútil contra este cenário, porque
    o arquivo já foi inteiro para a memória antes de alguém contar linhas.

    O padrão não é novo no projeto: `web/extracao.py` já o usava no preview de
    layout. Este helper o torna compartilhado, para que o próximo endpoint de
    importação não nasça sem teto.
    """
    limite = MAX_UPLOAD_BYTES if max_bytes is None else max_bytes
    conteudo = await arquivo.read(limite + 1)
    if len(conteudo) > limite:
        raise RegraNegocioError(
            f"Arquivo excede o limite de {limite // (1024 * 1024)} MB."
        )
    return conteudo


def validar_extensao(filename: str | None) -> None:
    """Recusa extensão fora da lista suportada (R6).

    Declarativa e forjável — a defesa real contra conteúdo hostil é o parser.
    O ganho aqui é a MENSAGEM: quem manda `.pdf` numa tela de CSV descobre na
    hora, em vez de receber erro de parse obscuro. Validar *magic bytes* seria
    teatro: quem forja a extensão forja o cabeçalho.
    """
    nome = (filename or "").strip().lower()
    if not nome.endswith(EXTENSOES_SUPORTADAS):
        aceitos = ", ".join(EXTENSOES_SUPORTADAS)
        raise RegraNegocioError(
            f"Formato de arquivo não suportado. Envie um destes: {aceitos}."
        )


@dataclass
class LinhaPreview:
    numero: int
    status: str  # 'ok' | 'aviso' | 'erro'
    mensagem: str | None
    dados: dict = field(default_factory=dict)


@dataclass
class Preview:
    tipo: str
    arquivo: str
    colunas: list
    linhas: list  # list[LinhaPreview]

    @property
    def total_ok(self):
        return sum(1 for l in self.linhas if l.status == 'ok')

    @property
    def total_aviso(self):
        return sum(1 for l in self.linhas if l.status == 'aviso')

    @property
    def total_erro(self):
        return sum(1 for l in self.linhas if l.status == 'erro')

    @property
    def graváveis(self):
        return [l for l in self.linhas if l.status in ('ok', 'aviso')]


# Registry de adapters: tipo -> objeto com parse_validar(content, filename)->Preview
# e gravar(linhas_graváveis)->resultado
_ADAPTERS = {}


def registrar_adapter(tipo, adapter):
    _ADAPTERS[tipo] = adapter


def _adapter(tipo):
    if tipo not in _ADAPTERS:
        # importação tardia registra os adapters na primeira utilização
        from . import preprocessamento_adapters  # noqa: F401
    if tipo not in _ADAPTERS:
        raise RegraNegocioError(f"Tipo de importação desconhecido: {tipo}")
    return _ADAPTERS[tipo]


# ---------------------------------------------------------------- staging

def _garantir_dir():
    os.makedirs(STAGING_DIR, exist_ok=True)


def _caminho(token):
    return os.path.join(STAGING_DIR, f"{token}.json")


def _limpeza_oportunista():
    if not os.path.isdir(STAGING_DIR):
        return
    agora = time.time()
    for nome in os.listdir(STAGING_DIR):
        caminho = os.path.join(STAGING_DIR, nome)
        try:
            if agora - os.path.getmtime(caminho) > TTL_SEGUNDOS:
                os.remove(caminho)
        except OSError:
            pass


def _tokens_sessao(sessao):
    return sessao.setdefault("preview_tokens", [])


# ---------------------------------------------------------------- API

def criar_preview(tipo, content, filename, sessao) -> tuple:
    _garantir_dir()
    _limpeza_oportunista()

    preview = _adapter(tipo).parse_validar(content, filename)
    if len(preview.linhas) > MAX_LINHAS:
        raise RegraNegocioError(f"Arquivo excede o limite de {MAX_LINHAS} linhas")

    token = secrets.token_urlsafe(16)
    payload = {
        "tipo": preview.tipo, "arquivo": preview.arquivo,
        "colunas": preview.colunas,
        "linhas": [asdict(l) for l in preview.linhas],
        "criado_em": time.time(),
    }
    with open(_caminho(token), "w", encoding="utf-8") as fh:
        json.dump(payload, fh)
    _tokens_sessao(sessao).append(token)
    return token, preview


def _carregar(token, sessao) -> Preview:
    if token not in _tokens_sessao(sessao):
        raise RegraNegocioError("Pré-visualização inválida ou de outra sessão")
    caminho = _caminho(token)
    if not os.path.exists(caminho):
        raise RegraNegocioError("Pré-visualização expirada — envie o arquivo novamente")
    with open(caminho, encoding="utf-8") as fh:
        payload = json.load(fh)
    if time.time() - payload["criado_em"] > TTL_SEGUNDOS:
        _remover(token, sessao)
        raise RegraNegocioError("Pré-visualização expirada — envie o arquivo novamente")
    linhas = [LinhaPreview(**l) for l in payload["linhas"]]
    return Preview(tipo=payload["tipo"], arquivo=payload["arquivo"],
                   colunas=payload["colunas"], linhas=linhas)


def obter_preview(token, sessao) -> Preview:
    return _carregar(token, sessao)


def confirmar(token, sessao):
    preview = _carregar(token, sessao)
    resultado = _adapter(preview.tipo).gravar(preview.graváveis)
    _remover(token, sessao)
    return resultado


def descartar(token, sessao):
    _remover(token, sessao)


def _remover(token, sessao):
    try:
        os.remove(_caminho(token))
    except OSError:
        pass
    toks = _tokens_sessao(sessao)
    if token in toks:
        toks.remove(token)
