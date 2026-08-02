"""Web controller das reservas e bloqueios judiciais (spec desembolso R19–R20)."""
from datetime import date
from decimal import Decimal

from fastapi import Request
from fastapi.responses import RedirectResponse

from . import handle_exceptions, router, templates
from ..auth.permissoes import requer
from ..services.fonte_recurso_service import listar_fontes
from ..services.reserva_service import (
    constituir_reserva,
    liberar_reserva,
    listar_reservas,
    reduzir_reserva,
    reforcar_reserva,
)


@router.get('/reservas', name='reservas', dependencies=[requer('FC_CONS_RESERVA')])
@handle_exceptions
async def reservas(request: Request):
    fontes = [
        {'seq': f.seq_fonte_recurso,
         'rotulo': f"{f.codigo_completo} · {f.dsc_fonte_recurso}"}
        for f in listar_fontes(status='ativo')
    ]
    return templates.TemplateResponse('reservas.html', {
        'request': request,
        'reservas': listar_reservas(),
        'fontes': fontes,
    })


@router.post('/reservas/constituir', name='constituir_reserva_route',
             dependencies=[requer('FC_MANT_RESERVA')])
@handle_exceptions
async def constituir_reserva_route(request: Request):
    form = await request.form()
    constituir_reserva(
        cod_tipo_reserva=form.get('cod_tipo_reserva') or 'A',
        seq_fonte_recurso=int(form['seq_fonte_recurso']),
        val_reserva=Decimal(form['val_reserva']),
        dsc_motivo=form.get('dsc_motivo', ''),
        dat_inicio_vigencia=date.fromisoformat(form['dat_inicio_vigencia']),
        dat_fim_vigencia=(date.fromisoformat(form['dat_fim_vigencia'])
                          if form.get('dat_fim_vigencia') else None),
        dsc_referencia_processo=form.get('dsc_referencia_processo'),
        confirmado=form.get('confirmado') == 'true',
    )
    return RedirectResponse('/reservas', status_code=303)


@router.post('/reservas/{seq}/reforcar', name='reforcar_reserva_route',
             dependencies=[requer('FC_MANT_RESERVA')])
@handle_exceptions
async def reforcar_reserva_route(request: Request, seq: int):
    form = await request.form()
    reforcar_reserva(seq, Decimal(form['valor']), referencia=form.get('referencia'))
    return RedirectResponse('/reservas', status_code=303)


@router.post('/reservas/{seq}/reduzir', name='reduzir_reserva_route',
             dependencies=[requer('FC_MANT_RESERVA')])
@handle_exceptions
async def reduzir_reserva_route(request: Request, seq: int):
    form = await request.form()
    reduzir_reserva(seq, Decimal(form['valor']), referencia=form.get('referencia'))
    return RedirectResponse('/reservas', status_code=303)


@router.post('/reservas/{seq}/liberar', name='liberar_reserva_route',
             dependencies=[requer('FC_MANT_RESERVA')])
@handle_exceptions
async def liberar_reserva_route(request: Request, seq: int):
    form = await request.form()
    liberar_reserva(seq, referencia=form.get('referencia'))
    return RedirectResponse('/reservas', status_code=303)
