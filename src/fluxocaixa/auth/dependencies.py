"""Proteção de rotas: dependency global e handlers de redirecionamento.

Aplicada via `dependencies=[Depends(exigir_login)]` no `include_router` do
`create_app` — protege todas as rotas de negócio sem alterá-las
(spec controle-acesso R2; design D3).
"""
import logging
import os
import secrets
import time

from fastapi import Request
from fastapi.responses import JSONResponse, PlainTextResponse, RedirectResponse

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


# Inatividade: segundo limite, mais curto que o absoluto de expediente. Os dois
# medem coisas diferentes — o absoluto limita o dano de um cookie roubado que o
# atacante mantém ativo; este cobre a estação destravada, que num setor de
# tesouraria é o cenário mais provável dos dois.
INATIVIDADE_MAX_SEGUNDOS = int(os.getenv("SESSAO_INATIVIDADE_SEGUNDOS", 60 * 60))
CHAVE_ULTIMO_ACESSO = "ultimo_acesso"
CHAVE_VERSAO_CREDENCIAL = "versao_credencial"


def _usuario_da_sessao(request: Request, seq_usuario: int):
    """Carrega e revalida o usuário, memoizando no request (R13).

    Memoização em `request.state` segue o padrão de `permissoes_do_request` —
    na prática as duas leituras vivem juntas no mesmo request.
    """
    memo = getattr(request.state, "usuario_revalidado", None)
    if memo is not None:
        return memo

    from ..models.usuario import Usuario

    usuario = Usuario.query.get(seq_usuario)
    request.state.usuario_revalidado = usuario
    return usuario


async def sessao_atual(request: Request) -> int:
    """Exige sessão autenticada, válida e de usuário ativo.

    Uso: rotas de troca de senha e logout. Async de propósito: dependency
    síncrona roda em threadpool com CÓPIA do contexto, e o contextvar de
    auditoria setado lá não propagaria ao endpoint.
    """
    seq_usuario = request.session.get("seq_usuario")
    if not seq_usuario:
        raise NaoAutenticadoError(_destino_atual(request))

    agora = time.time()
    ultimo = request.session.get(CHAVE_ULTIMO_ACESSO)
    if ultimo is not None and agora - ultimo > INATIVIDADE_MAX_SEGUNDOS:
        request.session.clear()
        raise NaoAutenticadoError(_destino_atual(request))

    usuario = _usuario_da_sessao(request, seq_usuario)
    # Desativar o usuário É o mecanismo de desligamento (não há tela de
    # usuários): ele MUST valer para quem já está dentro, não só no login.
    if usuario is None or usuario.ind_status != 'A':
        request.session.clear()
        raise NaoAutenticadoError(_destino_atual(request))

    versao_sessao = request.session.get(CHAVE_VERSAO_CREDENCIAL)
    if versao_sessao != usuario.num_versao_credencial:
        # Troca de senha incrementa a versão — revoga as demais sessões,
        # inclusive uma roubada. Sessão emitida antes do change não tem a
        # chave e cai aqui: todos reautenticam uma vez (design D5).
        request.session.clear()
        raise NaoAutenticadoError(_destino_atual(request))

    request.session[CHAVE_ULTIMO_ACESSO] = agora
    return seq_usuario


async def exigir_login(request: Request) -> int:
    """Exige sessão autenticada e sem troca de senha pendente (R2, R4)."""
    seq_usuario = await sessao_atual(request)
    if request.session.get("troca_pendente"):
        raise TrocaSenhaPendenteError()
    # Auditoria (R9): registra o usuário corrente para as gravações do request
    from .contexto import definir_usuario_corrente, marcar_em_requisicao

    marcar_em_requisicao()
    definir_usuario_corrente(seq_usuario)
    return seq_usuario


def _aceita_html(request: Request) -> bool:
    return "text/html" in request.headers.get("accept", "")


def registrar_handlers(app) -> None:
    from .csrf import CsrfInvalidoError

    @app.exception_handler(CsrfInvalidoError)
    async def _csrf_invalido(request: Request, exc: CsrfInvalidoError):
        """403 sem executar efeito (controle-acesso R12).

        Não é `RegraNegocioError`: erro de negócio vira flash + redirect e o
        usuário tentaria de novo. Aqui a requisição é ilegítima, e a resposta
        precisa ser terminal.
        """
        if _aceita_html(request):
            return PlainTextResponse(exc.mensagem, status_code=403)
        return JSONResponse({"detail": exc.mensagem}, status_code=403)

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
            from .routes import _destino_seguro

            request.session["flash"] = exc.mensagem
            # o `Referer` PARECE infraestrutura do navegador, mas é cabeçalho
            # enviado pelo cliente e forjável — a mesma guarda do `next` vale
            # aqui (origem única, controle-acesso R2)
            destino = _destino_seguro(
                exc.destino or request.headers.get("referer") or "/")
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
