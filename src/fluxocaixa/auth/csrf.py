"""Proteção CSRF por token de sessão (spec controle-acesso R12).

Change: protecao-csrf-global.

Duas barreiras, deliberadamente:

1. **Token sincronizador** — forte e independente de cabeçalho, mas depende de
   o formulário carregá-lo (resolvido por injeção automática em `seguranca.js`,
   não por campo escrito à mão em 70 formulários).
2. **Verificação de origem** — cobre o ponto cego da primeira (formulário
   submetido antes de o script carregar, ou sem JS) e não depende de template
   algum. Origem divergente é recusada MESMO com token válido: token vaza por
   log, histórico e extensão; origem não é forjável por página de terceiro.
"""
import secrets
from urllib.parse import urlsplit

from fastapi import Request

CHAVE_SESSAO = "csrf_token"
CAMPO_FORM = "csrf_token"
CABECALHO = "X-CSRF-Token"

METODOS_SEGUROS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})

# `POST /login` não tem sessão estabelecida — a proteção ali é a limpeza de
# sessão contra fixação, que já existe em `efetuar_login`.
CAMINHOS_ISENTOS = frozenset({"/login"})


class CsrfInvalidoError(Exception):
    """Falha de verificação CSRF — o handler traduz para 403."""

    def __init__(self, mensagem: str):
        super().__init__(mensagem)
        self.mensagem = mensagem


def obter_token(sessao) -> str:
    """Token da sessão, criado na primeira necessidade.

    Por SESSÃO, e não por requisição: o sistema é usado com várias abas abertas
    (relatórios lado a lado) e a rotação faria a aba antiga falhar ao submeter —
    o que ensina o usuário a recarregar tudo antes de agir, comportamento que
    leva gente a desligar proteção.
    """
    token = sessao.get(CHAVE_SESSAO)
    if not token:
        token = secrets.token_urlsafe(32)
        sessao[CHAVE_SESSAO] = token
    return token


def _token_da_requisicao(request, corpo_form) -> str | None:
    do_cabecalho = request.headers.get(CABECALHO)
    if do_cabecalho:
        return do_cabecalho
    if corpo_form is not None:
        valor = corpo_form.get(CAMPO_FORM)
        if isinstance(valor, str):
            return valor
    return None


def _origem_confere(request) -> bool:
    """`Origin` (ou `Referer`) deve bater com o host da aplicação.

    Ausência dos dois não reprova: cliente não-navegador legítimo (e o próprio
    TestClient) não os envia, e o token já é exigido de qualquer forma.
    """
    bruto = request.headers.get("origin") or request.headers.get("referer")
    if not bruto:
        return True
    host_informado = urlsplit(bruto).netloc
    if not host_informado:
        return False
    return host_informado == request.headers.get("host")


async def verificar_csrf(request: Request) -> None:
    """Dependency global de verificação (spec controle-acesso R12).

    ⚠️ Dependency, e NÃO middleware `BaseHTTPMiddleware`. O middleware precisaria
    ler o corpo para achar o campo do formulário, e `BaseHTTPMiddleware` entrega
    ao endpoint um `Request` DIFERENTE: o corpo já consumido não é replayado e a
    rota recebe form vazio (`422 Field required`). Como dependency, o `Request` é
    o mesmo, então `await request.form()` fica cacheado e a rota lê normalmente.
    """
    if request.method in METODOS_SEGUROS or request.url.path in CAMINHOS_ISENTOS:
        return

    sessao = request.session if "session" in request.scope else {}
    if not sessao.get("seq_usuario"):
        # Anônimo: não há sessão a proteger, e a rota exigirá login — o
        # `exigir_login` responde o 401/redirect apropriado.
        return

    # Sessão AUTENTICADA sem token falha FECHADO. Deixar passar seria a brecha
    # exata que o token deveria cobrir: bastaria a sessão nunca ter renderizado
    # uma página para a validação ser pulada.
    esperado = sessao.get(CHAVE_SESSAO)
    if not esperado:
        raise CsrfInvalidoError("Sessão sem token de verificação.")

    if not _origem_confere(request):
        raise CsrfInvalidoError("Origem da requisição não confere.")

    corpo_form = None
    tipo = request.headers.get("content-type", "")
    if tipo.startswith(("application/x-www-form-urlencoded", "multipart/form-data")):
        corpo_form = await request.form()

    informado = _token_da_requisicao(request, corpo_form)
    if not informado or not secrets.compare_digest(informado, esperado):
        raise CsrfInvalidoError("Token de verificação ausente ou inválido.")


__all__ = [
    "verificar_csrf",
    "CsrfInvalidoError",
    "obter_token",
    "CAMPO_FORM",
    "CABECALHO",
    "CHAVE_SESSAO",
    "METODOS_SEGUROS",
]
