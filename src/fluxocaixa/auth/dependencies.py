"""Proteção de rotas: dependency global e handlers de redirecionamento.

Aplicada via `dependencies=[Depends(exigir_login)]` no `include_router` do
`create_app` — protege todas as rotas de negócio sem alterá-las
(spec controle-acesso R2; design D3).
"""
import logging
import os
import secrets

from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse

logger = logging.getLogger(__name__)


class NaoAutenticadoError(Exception):
    def __init__(self, destino: str = "/"):
        self.destino = destino


class TrocaSenhaPendenteError(Exception):
    pass


def _destino_atual(request: Request) -> str:
    caminho = request.url.path
    if request.url.query:
        caminho = f"{caminho}?{request.url.query}"
    return caminho


async def sessao_atual(request: Request) -> int:
    """Exige sessão autenticada; permite navegação com troca de senha pendente.

    Uso: rotas de troca de senha e logout. Async de propósito: dependency
    síncrona roda em threadpool com CÓPIA do contexto, e o contextvar de
    auditoria setado lá não propagaria ao endpoint.
    """
    seq_usuario = request.session.get("seq_usuario")
    if not seq_usuario:
        raise NaoAutenticadoError(_destino_atual(request))
    return seq_usuario


async def exigir_login(request: Request) -> int:
    """Exige sessão autenticada e sem troca de senha pendente (R2, R4)."""
    seq_usuario = await sessao_atual(request)
    if request.session.get("troca_pendente"):
        raise TrocaSenhaPendenteError()
    # Auditoria (R9): registra o usuário corrente para as gravações do request
    from .contexto import definir_usuario_corrente

    definir_usuario_corrente(seq_usuario)
    return seq_usuario


def _aceita_html(request: Request) -> bool:
    return "text/html" in request.headers.get("accept", "")


def registrar_handlers(app) -> None:
    @app.exception_handler(NaoAutenticadoError)
    async def _nao_autenticado(request: Request, exc: NaoAutenticadoError):
        if _aceita_html(request):
            from urllib.parse import quote

            return RedirectResponse(
                f"/login?next={quote(exc.destino, safe='/?=&')}", status_code=302
            )
        return JSONResponse({"detail": "Não autenticado"}, status_code=401)

    @app.exception_handler(TrocaSenhaPendenteError)
    async def _troca_pendente(request: Request, exc: TrocaSenhaPendenteError):
        if _aceita_html(request):
            return RedirectResponse("/trocar-senha", status_code=302)
        return JSONResponse(
            {"detail": "Troca de senha obrigatória pendente"}, status_code=403
        )

    from ..services.validacao import RegraNegocioError

    @app.exception_handler(RegraNegocioError)
    async def _regra_negocio(request: Request, exc: RegraNegocioError):
        if _aceita_html(request):
            request.session["flash"] = exc.mensagem
            destino = exc.destino or request.headers.get("referer") or "/"
            return RedirectResponse(destino, status_code=303)
        return JSONResponse({"detail": exc.mensagem}, status_code=400)

    from .permissoes import PermissaoNegadaError

    @app.exception_handler(PermissaoNegadaError)
    async def _permissao_negada(request: Request, exc: PermissaoNegadaError):
        if _aceita_html(request):
            from ..web import templates

            return templates.TemplateResponse(
                "403.html",
                {"request": request, "permissao": exc.cod_permissao},
                status_code=403,
            )
        return JSONResponse(
            {"detail": f"Permissão necessária: {exc.cod_permissao}"}, status_code=403
        )


def obter_secret_key() -> str:
    """SECRET_KEY da env; sem ela, chave aleatória por processo + warning (R3/D2)."""
    chave = os.getenv("SECRET_KEY")
    if chave:
        return chave
    logger.warning(
        "SECRET_KEY não definida — usando chave aleatória por processo. "
        "Sessões serão invalidadas a cada restart; defina SECRET_KEY em produção."
    )
    return secrets.token_hex(32)
