"""Rotas do fluxo de pré-processamento de importações (spec importacao-arquivos).

Uma tela de preview genérica serve os três tipos. As rotas de confirmar/
descartar exigem a permissão do TIPO do preview.
"""
from fastapi import Form, Request
from fastapi.responses import RedirectResponse

from ..auth.permissoes import permissoes_do_request
from ..services.preprocessamento import confirmar, descartar, obter_preview
from . import handle_exceptions, router, templates

# tipo de importação -> (permissão exigida, rota de retorno)
_TIPOS = {
    "saldos": ("FC_IMP_SALDO_BANCARIO", "/saldos-bancarios"),
    "lancamentos": ("FC_IMP_LANCAMENTO", "/saldos"),
    "loa": ("FC_IMP_LOA", "/loa"),
    "fontes_recurso": ("FC_IMP_FONTE_RECURSO", "/fontes-recurso"),
    "programacao": ("FC_IMP_PROGRAMACAO", "/desembolso/programacao"),
    "dotacao": ("FC_IMP_DOTACAO", "/orcamento/dotacoes"),
    "execucao": ("FC_IMP_EXECUCAO_ORCAMENTARIA", "/orcamento/execucao"),
    "disponibilidade_contabil": ("FC_IMP_DISPONIBILIDADE_CONTABIL", "/fontes-recurso/conciliacao"),
}


def _exigir(request: Request, tipo: str):
    from ..auth.permissoes import PermissaoNegadaError

    perm = _TIPOS.get(tipo, (None, "/"))[0]
    if perm and perm not in permissoes_do_request(request):
        raise PermissaoNegadaError(perm)


def render_preview(request: Request, tipo: str, token, preview):
    return templates.TemplateResponse('importacao_preview.html', {
        'request': request, 'tipo': tipo, 'token': token, 'preview': preview,
        'retorno': _TIPOS.get(tipo, (None, "/"))[1],
    })


@router.post('/importacoes/{token}/confirmar', name='confirmar_importacao')
@handle_exceptions
async def confirmar_importacao(request: Request, token: str):
    preview = obter_preview(token, request.session)  # valida sessão/TTL
    _exigir(request, preview.tipo)
    resultado = confirmar(token, request.session)
    inseridas = getattr(resultado, 'linhas_inseridas', None)
    if inseridas is None and isinstance(resultado, dict):
        inseridas = resultado.get('sucesso', 0)
    request.session['flash'] = f"Importação concluída: {inseridas} registro(s) gravado(s)."
    return RedirectResponse(_TIPOS.get(preview.tipo, (None, "/"))[1], status_code=303)


@router.post('/importacoes/{token}/descartar', name='descartar_importacao')
@handle_exceptions
async def descartar_importacao(request: Request, token: str, tipo: str = Form("saldos")):
    # Exige a permissão do TIPO do preview, como o confirmar (R6). A assimetria
    # anterior tinha impacto direto pequeno (o token é amarrado à sessão), mas
    # ensinava que preview não precisa de permissão — e a próxima rota de
    # preview nasceria sem.
    preview = obter_preview(token, request.session)
    _exigir(request, preview.tipo)
    descartar(token, request.session)
    return RedirectResponse(_TIPOS.get(tipo, (None, "/"))[1], status_code=303)
