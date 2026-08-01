"""Rotas de autenticação: login/logout (públicas) e troca de senha (logado)."""
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from ..config import modo_demo
from ..models.usuario import Usuario
from .dependencies import sessao_atual
from .service import autenticar, definir_senha, validar_nova_senha

MENSAGEM_CREDENCIAIS_INVALIDAS = "Usuário ou senha inválidos"
MENSAGEM_SENHA_IMUTAVEL_DEMO = (
    "Ambiente de demonstração: a senha não pode ser alterada, "
    "para que o acesso continue disponível a todos os visitantes."
)

# Público: sem dependency de sessão
router_publico = APIRouter()

# Exige sessão, mas permite troca de senha pendente
router_sessao = APIRouter(dependencies=[Depends(sessao_atual)])


def _destino_seguro(destino: str) -> str:
    """Evita open redirect: só caminhos internos."""
    if destino and destino.startswith("/") and not destino.startswith("//"):
        return destino
    return "/"


def _templates():
    from ..web import templates

    return templates


@router_publico.get("/login", include_in_schema=False)
async def tela_login(request: Request, next: str = "/"):
    return _templates().TemplateResponse(
        "login.html", {"request": request, "next": _destino_seguro(next), "erro": None}
    )


@router_publico.post("/login", include_in_schema=False)
async def efetuar_login(
    request: Request,
    usuario: str = Form(...),
    senha: str = Form(...),
    next: str = "/",
):
    destino = _destino_seguro(request.query_params.get("next", next))
    autenticado = autenticar(usuario, senha)
    if autenticado is None:
        return _templates().TemplateResponse(
            "login.html",
            {"request": request, "next": destino, "erro": MENSAGEM_CREDENCIAIS_INVALIDAS},
            status_code=200,
        )

    request.session.clear()
    request.session["seq_usuario"] = autenticado.seq_usuario
    request.session["nom_usuario"] = autenticado.nom_usuario
    if autenticado.ind_troca_senha == 'S':
        request.session["troca_pendente"] = True
        return RedirectResponse("/trocar-senha", status_code=303)
    return RedirectResponse(destino, status_code=303)


@router_sessao.post("/logout", include_in_schema=False)
async def efetuar_logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@router_sessao.get("/trocar-senha", include_in_schema=False)
async def tela_trocar_senha(request: Request):
    return _templates().TemplateResponse(
        "trocar_senha.html",
        {"request": request, "erro": MENSAGEM_SENHA_IMUTAVEL_DEMO if modo_demo() else None},
    )


@router_sessao.post("/trocar-senha", include_in_schema=False)
async def efetuar_troca_senha(
    request: Request,
    senha_atual: str = Form(...),
    nova_senha: str = Form(...),
    confirmacao: str = Form(...),
):
    def _erro(mensagem: str):
        return _templates().TemplateResponse(
            "trocar_senha.html", {"request": request, "erro": mensagem}, status_code=200
        )

    if modo_demo():
        return _erro(MENSAGEM_SENHA_IMUTAVEL_DEMO)

    usuario = Usuario.query.get(request.session["seq_usuario"])
    if usuario is None or usuario.ind_status != 'A':
        request.session.clear()
        return RedirectResponse("/login", status_code=303)

    if not autenticar(usuario.nom_usuario, senha_atual):
        return _erro("Senha atual incorreta")
    if nova_senha != confirmacao:
        return _erro("A confirmação não confere com a nova senha")
    mensagem = validar_nova_senha(nova_senha, usuario.txt_hash_senha)
    if mensagem:
        return _erro(mensagem)

    definir_senha(usuario, nova_senha, troca_pendente=False)
    request.session["troca_pendente"] = False
    return RedirectResponse("/", status_code=303)
