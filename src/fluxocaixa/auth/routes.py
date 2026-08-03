"""Rotas de autenticação: login/logout (públicas) e troca de senha (logado)."""
import time
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from ..config import modo_demo
from ..models.usuario import Usuario
from .csrf import obter_token
from .dependencies import (
    CHAVE_ULTIMO_ACESSO,
    CHAVE_VERSAO_CREDENCIAL,
    sessao_atual,
)
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


def _destino_seguro(destino: str | None) -> str:
    """Evita open redirect: só caminhos internos.

    Normaliza a URL em vez de listar prefixos proibidos. A guarda anterior
    recusava `//host` mas aceitava `/\\host` — navegadores normalizam `\\` para
    `/` em esquemas especiais, então `/\\host` vira `//host` vira `https://host`,
    e o phishing pós-login ganha o domínio confiável como trampolim.

    Lista de proibições sempre fica uma variação atrás (barra invertida, espaço
    à esquerda, caractere de controle, `JaVaScRiPt:`). `urlsplit` responde a
    pergunta certa — "esta URL tem host?" — e a resposta não envelhece.
    """
    if not destino:
        return "/"
    # o \ é normalizado para / pelo navegador ANTES de resolver o host; fazer o
    # mesmo aqui garante que se analise a URL que o navegador vai ver
    candidato = destino.replace("\\", "/").strip()
    partes = urlsplit(candidato)
    if partes.scheme or partes.netloc or not candidato.startswith("/"):
        return "/"
    # `//host` é protocol-relative; `///host` tem autoridade vazia e navegadores
    # divergem ao colapsar as barras (parte resolve para o host). Qualquer
    # sequência de barras no início é recusada — caminho interno legítimo nunca
    # precisa de duas.
    if candidato.startswith("//"):
        return "/"
    return destino


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
    # Token CSRF nasce COM a sessão (controle-acesso R12): assim toda sessão
    # autenticada tem token, e o middleware pode falhar fechado na ausência
    # dele em vez de deixar passar.
    obter_token(request.session)
    # Versão de credencial e carimbo de acesso (R13): a sessão passa a poder ser
    # revogada por troca de senha e a expirar por inatividade.
    request.session[CHAVE_VERSAO_CREDENCIAL] = autenticado.num_versao_credencial
    request.session[CHAVE_ULTIMO_ACESSO] = time.time()
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
    # A troca revogou TODAS as sessões (a versão subiu); esta continua válida
    # porque acompanha a versão nova — as outras caem na próxima requisição.
    request.session[CHAVE_VERSAO_CREDENCIAL] = usuario.num_versao_credencial
    return RedirectResponse("/", status_code=303)
