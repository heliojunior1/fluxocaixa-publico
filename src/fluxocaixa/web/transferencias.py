"""Web controller das transferências internas (spec desembolso R13)."""
from datetime import date
from decimal import Decimal

from fastapi import Request
from fastapi.responses import RedirectResponse

from . import handle_exceptions, router, templates
from ..auth.permissoes import requer
from ..services.transferencia_service import (
    criar_transferencia,
    inativar_transferencia,
    listar_transferencias,
)


@router.get('/transferencias', name='transferencias',
            dependencies=[requer('FC_CONS_TRANSFERENCIA')])
@handle_exceptions
async def transferencias(request: Request):
    from ..models import ContaBancaria

    contas = (ContaBancaria.query.filter_by(ind_status='A')
              .order_by(ContaBancaria.cod_banco).all())
    return templates.TemplateResponse('transferencias.html', {
        'request': request,
        'transferencias': listar_transferencias(),
        'contas': contas,
    })


@router.post('/transferencias/adicionar', name='add_transferencia',
             dependencies=[requer('FC_MANT_TRANSFERENCIA')])
@handle_exceptions
async def add_transferencia(request: Request):
    form = await request.form()
    criar_transferencia(
        dat_transferencia=date.fromisoformat(form['dat_transferencia']),
        seq_conta_origem=int(form['seq_conta_origem']),
        seq_conta_destino=int(form['seq_conta_destino']),
        val_transferencia=Decimal(form['val_transferencia']),
        dsc_transferencia=form.get('dsc_transferencia'),
    )
    return RedirectResponse('/transferencias', status_code=303)


@router.post('/transferencias/{seq}/inativar', name='inativar_transferencia_route',
             dependencies=[requer('FC_MANT_TRANSFERENCIA')])
@handle_exceptions
async def inativar_transferencia_route(request: Request, seq: int):
    inativar_transferencia(seq)
    return RedirectResponse('/transferencias', status_code=303)
