"""Tela de exercícios: situação, pendências, abrir/fechar/reabrir e histórico
(cadastros-nucleo R31–R32). Rotas finas — regra em `exercicio_service` e
`qualificador_service.abrir_exercicio` (a abertura é a mesma da F10.3)."""
from fastapi import Request
from fastapi.responses import RedirectResponse

from ..auth.permissoes import requer
from ..services import exercicio_service as exercicios
from . import handle_exceptions, router, templates
from .entrada import inteiro

_TELA = '/exercicios'
_SIM = ('S', 'on', 'true', '1')


def _na_tela(funcao, *args, **kwargs):
    """Erro de negócio volta para a tela de exercícios (o handler global usa
    `destino`; sem ele cairia no Referer, que nem sempre vem)."""
    from ..services.validacao import RegraNegocioError

    try:
        return funcao(*args, **kwargs)
    except RegraNegocioError as exc:
        exc.destino = exc.destino or _TELA
        raise


@router.get(_TELA, name='exercicios', dependencies=[requer('FC_CONS_EXERCICIO')])
@handle_exceptions
async def exercicios_tela(request: Request):
    return templates.TemplateResponse('exercicios.html', {
        'request': request,
        'exercicios': exercicios.listar_para_tela(),
    })


@router.post(_TELA + '/abrir', name='exercicio_abrir',
             dependencies=[requer('FC_ABRIR_EXERCICIO')])
@handle_exceptions
async def exercicio_abrir(request: Request):
    from ..services.qualificador_service import abrir_exercicio

    form = await request.form()
    origem = inteiro(form.get('exercicio_origem'), 'exercício de origem', obrigatorio=True)
    novo = inteiro(form.get('exercicio_novo'), 'exercício novo', obrigatorio=True)
    _na_tela(abrir_exercicio, origem, novo, confirmado=form.get('confirmado') in _SIM)
    request.session['flash'] = f"Exercício {novo} aberto a partir de {origem}"
    return RedirectResponse(_TELA, status_code=303)


@router.post(_TELA + '/{ano}/fechar', name='exercicio_fechar',
             dependencies=[requer('FC_FECHAR_EXERCICIO')])
@handle_exceptions
async def exercicio_fechar(request: Request, ano: int):
    form = await request.form()
    _na_tela(exercicios.fechar_exercicio, ano, form.get('motivo'),
             confirmado=form.get('confirmado') in _SIM)
    request.session['flash'] = f"Exercício {ano} fechado"
    return RedirectResponse(_TELA, status_code=303)


@router.post(_TELA + '/{ano}/reabrir', name='exercicio_reabrir',
             dependencies=[requer('FC_REABRIR_EXERCICIO')])
@handle_exceptions
async def exercicio_reabrir(request: Request, ano: int):
    form = await request.form()
    _na_tela(exercicios.reabrir_exercicio, ano, form.get('motivo'))
    request.session['flash'] = f"Exercício {ano} reaberto"
    return RedirectResponse(_TELA, status_code=303)
