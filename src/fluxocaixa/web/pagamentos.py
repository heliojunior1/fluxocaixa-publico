from datetime import date
from decimal import Decimal

from fastapi import Request
from fastapi.responses import RedirectResponse

from ..auth.permissoes import requer
from ..domain import PagamentoCreate
from ..services import create_pagamento, list_pagamentos
from ..services.pagamento_service import (
    alterar_pagamento,
    apropriacoes_do,
    apropriar_pagamento,
    candidatas_para,
    consumo_do_pagamento,
    estornar_apropriacao,
    excluir_pagamento,
)
from . import handle_exceptions, router, templates


@router.get('/pagamentos', name='pagamentos', dependencies=[requer('FC_CONS_PAGAMENTO')])
@handle_exceptions
async def pagamentos(request: Request):
    pagamentos, orgaos, qualificadores = list_pagamentos()
    consumos = {p.seq_pagamento: consumo_do_pagamento(p.seq_pagamento) for p in pagamentos}
    return templates.TemplateResponse(
        'pagamentos.html',
        {'request': request, 'pagamentos': pagamentos, 'orgaos': orgaos,
         'qualificadores': qualificadores, 'consumos': consumos},
    )


@router.post('/pagamentos/add', dependencies=[requer('FC_INS_PAGAMENTO')])
@handle_exceptions
async def add_pagamento(request: Request):
    form = await request.form()
    
    # Handle empty string for seq_qualificador
    seq_qualificador = form.get('seq_qualificador')
    if seq_qualificador == '' or seq_qualificador is None:
        seq_qualificador = None
    else:
        seq_qualificador = int(seq_qualificador)
    
    data = PagamentoCreate(
        dat_pagamento=date.fromisoformat(form.get('dat_pagamento')),
        cod_orgao=int(form.get('cod_orgao')),
        seq_qualificador=seq_qualificador,
        val_pagamento=form.get('val_pagamento'),
        dsc_pagamento=form.get('dsc_pagamento'),
    )
    create_pagamento(data)
    return RedirectResponse(request.url_for('pagamentos'), status_code=303)


@router.post('/pagamentos/{seq}/editar', name='edit_pagamento',
             dependencies=[requer('FC_ALT_PAGAMENTO')])
@handle_exceptions
async def edit_pagamento(request: Request, seq: int):
    form = await request.form()
    alterar_pagamento(
        seq,
        val_pagamento=Decimal(form['val_pagamento']) if form.get('val_pagamento') else None,
        dsc_pagamento=form.get('dsc_pagamento'),
        seq_qualificador=int(form['seq_qualificador']) if form.get('seq_qualificador') else None,
    )
    return RedirectResponse(request.url_for('pagamentos'), status_code=303)


@router.post('/pagamentos/{seq}/excluir', name='del_pagamento',
             dependencies=[requer('FC_DEL_PAGAMENTO')])
@handle_exceptions
async def del_pagamento(request: Request, seq: int):
    form = await request.form()
    excluir_pagamento(seq, confirmado=form.get('confirmado') == 'true')
    return RedirectResponse(request.url_for('pagamentos'), status_code=303)


@router.get('/pagamentos/{seq}/apropriar', name='apropriar_pagamento_tela',
            dependencies=[requer('FC_APROPRIAR_PAGAMENTO')])
@handle_exceptions
async def apropriar_pagamento_tela(request: Request, seq: int):
    from ..models import Pagamento

    pagamento = Pagamento.query.get_or_404(seq)
    return templates.TemplateResponse('pagamento_apropriar.html', {
        'request': request,
        'pagamento': pagamento,
        'candidatas': candidatas_para(seq),
        'apropriacoes': apropriacoes_do(seq),
        'consumo': consumo_do_pagamento(seq),
    })


@router.post('/pagamentos/{seq}/apropriar', name='apropriar_pagamento_route',
             dependencies=[requer('FC_APROPRIAR_PAGAMENTO')])
@handle_exceptions
async def apropriar_pagamento_route(request: Request, seq: int):
    form = await request.form()
    apropriacoes = []
    for chave, valor in form.multi_items():
        if chave.startswith('valor_') and str(valor).strip():
            apropriacoes.append((int(chave.replace('valor_', '')), Decimal(str(valor))))
    apropriar_pagamento(seq, apropriacoes)
    return RedirectResponse(f'/pagamentos/{seq}/apropriar', status_code=303)


@router.post('/pagamentos/apropriacoes/{seq_evento}/estornar', name='estornar_apropriacao_route',
             dependencies=[requer('FC_APROPRIAR_PAGAMENTO')])
@handle_exceptions
async def estornar_apropriacao_route(request: Request, seq_evento: int):
    pagamento = estornar_apropriacao(seq_evento)
    return RedirectResponse(f'/pagamentos/{pagamento.seq_pagamento}/apropriar', status_code=303)
