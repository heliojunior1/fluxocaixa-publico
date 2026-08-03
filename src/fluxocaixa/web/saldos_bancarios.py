"""Web controller da tela de Saldos Bancários (modelo por fundo — F2.4).

Visão Agregado (default, soma por conta) ou Por fundo. CRUD no modelo novo:
criar/editar via gravação idempotente (chaves imutáveis), excluir = inativar.
Import CSV de transição grava no fundo GERAL (tipo IMPORTADO).
"""
from datetime import date

from fastapi import File, Request, UploadFile
from fastapi.responses import RedirectResponse

from . import handle_exceptions, router, templates
from ..auth.permissoes import requer
from ..models import Fundo
from ..services import list_contas_bancarias
from ..services.saldo_conta_service import (

    criar_saldo_tela,
    editar_saldo_tela,
    inativar_saldo_tela,
    listar_saldos_tela,
)


def _data(valor):
    return date.fromisoformat(valor) if valor else None


@router.get('/saldos-bancarios', dependencies=[requer('FC_CONS_SALDO_BANCARIO')])
@handle_exceptions
async def saldos_bancarios(request: Request):
    visao = request.query_params.get('visao', 'agregado')
    seq_conta = request.query_params.get('seq_conta')
    seq_fundo = request.query_params.get('seq_fundo')
    data_inicio = _data(request.query_params.get('data_inicio'))
    data_fim = _data(request.query_params.get('data_fim'))

    linhas = listar_saldos_tela(
        visao=visao,
        seq_conta=int(seq_conta) if seq_conta else None,
        seq_fundo=int(seq_fundo) if seq_fundo else None,
        data_inicio=data_inicio, data_fim=data_fim,
    )
    return templates.TemplateResponse('saldos_bancarios.html', {
        'request': request,
        'visao': visao,
        'linhas': linhas,
        'contas': list_contas_bancarias(),
        'fundos': Fundo.query.filter_by(ind_status='A').order_by(Fundo.cod_fundo).all(),
        'filtros': {
            'seq_conta': seq_conta or '', 'seq_fundo': seq_fundo or '',
            'data_inicio': request.query_params.get('data_inicio', ''),
            'data_fim': request.query_params.get('data_fim', ''),
        },
    })


@router.post('/saldos-bancarios/adicionar', name='add_saldo_bancario',
             dependencies=[requer('FC_INS_SALDO_BANCARIO')])
@handle_exceptions
async def add_saldo_bancario(request: Request):
    form = await request.form()
    criar_saldo_tela(
        seq_conta=int(form['seq_conta']),
        seq_fundo=int(form['seq_fundo']),
        dat_saldo=date.fromisoformat(form['dat_saldo']),
        val_saldo=form['val_saldo'],
        val_aplicacoes=form.get('val_aplicacoes') or '0',
        val_resgates=form.get('val_resgates') or '0',
    )
    return RedirectResponse('/saldos-bancarios?visao=fundo', status_code=303)


@router.post('/saldos-bancarios/editar', name='edit_saldo_bancario',
             dependencies=[requer('FC_ALT_SALDO_BANCARIO')])
@handle_exceptions
async def edit_saldo_bancario(request: Request):
    form = await request.form()
    editar_saldo_tela(
        seq_conta=int(form['seq_conta']),
        seq_fundo=int(form['seq_fundo']),
        dat_saldo=date.fromisoformat(form['dat_saldo']),
        val_saldo=form['val_saldo'],
        val_aplicacoes=form.get('val_aplicacoes') or '0',
        val_resgates=form.get('val_resgates') or '0',
    )
    return RedirectResponse('/saldos-bancarios?visao=fundo', status_code=303)


@router.post('/saldos-bancarios/inativar', name='delete_saldo_bancario',
             dependencies=[requer('FC_DEL_SALDO_BANCARIO')])
@handle_exceptions
async def inativar_saldo_bancario(request: Request):
    form = await request.form()
    inativar_saldo_tela(int(form['seq_conta']), int(form['seq_fundo']),
                        date.fromisoformat(form['dat_saldo']))
    return RedirectResponse('/saldos-bancarios?visao=fundo', status_code=303)


@router.post('/saldos-bancarios/importar', name='import_saldos_bancarios',
             dependencies=[requer('FC_IMP_SALDO_BANCARIO')])
@handle_exceptions
async def import_saldos_bancarios(request: Request, file: UploadFile = File(...)):
    # Fluxo com pré-processamento (F2.5): upload → preview → confirmar
    from ..services.preprocessamento import criar_preview
    from .importacao import render_preview

    token, preview = criar_preview('saldos', await _ler(file), file.filename or '', request.session)
    return render_preview(request, 'saldos', token, preview)


@router.get('/saldos-bancarios/modelo-csv', name='modelo_csv_saldos',
            dependencies=[requer('FC_IMP_SALDO_BANCARIO')])
@handle_exceptions
async def modelo_csv_saldos():
    from fastapi.responses import Response

    conteudo = (
        "Data;Banco;Agencia;Conta;CodFundo;Aplicacoes;Resgates;Saldo\n"
        "2026-07-11;104;0001;12345-6;GERAL;0;0;1000000.00\n"
    )
    return Response(conteudo, media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=modelo_saldos.csv"})


async def _ler(arquivo):
    """Upload com teto de bytes e extensão validada (importacao-arquivos R6)."""
    from ..services.preprocessamento import ler_upload_limitado, validar_extensao

    validar_extensao(arquivo.filename)
    return await ler_upload_limitado(arquivo)
