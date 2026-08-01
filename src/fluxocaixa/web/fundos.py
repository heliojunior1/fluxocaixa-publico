"""Web controller da gestão de fundos (spec saldo-por-fundo R7–R13)."""
from fastapi import Request
from fastapi.responses import RedirectResponse

from . import handle_exceptions, router, templates
from ..auth.permissoes import requer
from ..models import SistemaOrigem, TipoOrigemSaldo
from ..services.fundo_service import (
    alterar_fundo,
    aprovar_fundo,
    criar_fundo,
    inativar_fundo,
    listar_fundos,
)


def _rotulo_origem(fundo, tipos, sistemas) -> str:
    if tipos.get(fundo.seq_tipo_origem) == 'MANUAL':
        return 'Manual'
    sigla = sistemas.get(fundo.seq_sistema_origem, '')
    return f"Auto-cadastrado — {sigla}" if sigla else "Auto-cadastrado"


@router.get('/fundos', dependencies=[requer('FC_CONS_FUNDO')])
@handle_exceptions
async def fundos(request: Request):
    cod = request.query_params.get('cod') or None
    dsc = request.query_params.get('dsc') or None
    status = request.query_params.get('status') or None
    pendente = True if request.query_params.get('pendente') == 'true' else None

    lista = listar_fundos(cod=cod, dsc=dsc, status=status, pendente=pendente)
    tipos = {t.seq_tipo_origem_saldo: t.txt_sigla for t in TipoOrigemSaldo.query.all()}
    sistemas = {s.seq_sistema_origem: s.txt_sigla for s in SistemaOrigem.query.all()}

    fundos_view = [
        {
            'seq_fundo': f.seq_fundo,
            'cod_fundo': f.cod_fundo,
            'dsc_fundo': f.dsc_fundo,
            'origem': _rotulo_origem(f, tipos, sistemas),
            'ativo': f.ind_status == 'A',
            'pendente': f.ind_pendente_revisao == 'S',
        }
        for f in lista
    ]
    return templates.TemplateResponse(
        'fundos.html',
        {
            'request': request,
            'fundos': fundos_view,
            'filtros': {'cod': cod or '', 'dsc': dsc or '', 'status': status or '',
                        'pendente': pendente or False},
        },
    )


@router.post('/fundos/adicionar', name='add_fundo', dependencies=[requer('FC_INS_FUNDO')])
@handle_exceptions
async def add_fundo(request: Request):
    form = await request.form()
    criar_fundo(form.get('cod_fundo', ''), form.get('dsc_fundo', ''))
    return RedirectResponse('/fundos', status_code=303)


@router.post('/fundos/{seq_fundo}/editar', name='edit_fundo', dependencies=[requer('FC_ALT_FUNDO')])
@handle_exceptions
async def edit_fundo(request: Request, seq_fundo: int):
    form = await request.form()
    alterar_fundo(seq_fundo, form.get('dsc_fundo', ''))
    return RedirectResponse('/fundos', status_code=303)


@router.post('/fundos/{seq_fundo}/aprovar', name='aprovar_fundo', dependencies=[requer('FC_APROVAR_FUNDO')])
@handle_exceptions
async def aprovar_fundo_route(request: Request, seq_fundo: int):
    form = await request.form()
    dsc = form.get('dsc_fundo') or None
    aprovar_fundo(seq_fundo, dsc=dsc)
    return RedirectResponse('/fundos', status_code=303)


@router.post('/fundos/{seq_fundo}/inativar', name='inativar_fundo', dependencies=[requer('FC_DEL_FUNDO')])
@handle_exceptions
async def inativar_fundo_route(request: Request, seq_fundo: int):
    inativar_fundo(seq_fundo)
    return RedirectResponse('/fundos', status_code=303)
