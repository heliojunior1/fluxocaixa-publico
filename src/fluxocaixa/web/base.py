from datetime import date, datetime
import calendar
import csv

from fastapi import Request, UploadFile, File
from fastapi.responses import RedirectResponse, StreamingResponse, HTMLResponse
from io import BytesIO, StringIO
import openpyxl
from sqlalchemy import func

from . import router, templates, handle_exceptions
from ..domain import LancamentoCreate
from ..services import (
    list_lancamentos,
    create_lancamento,
    update_lancamento,
    delete_lancamento,
    import_lancamentos_service,
    list_tipos_lancamento,
    list_origens_lancamento,
    list_contas_bancarias,
    list_active_qualificadores,
    list_alertas_ativos,
)
from ..models import db
from ..services.seed import seed_data
from ..auth.permissoes import requer

@router.get('/', dependencies=[requer('FC_EXI_DASHBOARD')])
@handle_exceptions
async def index(request: Request):
    """Página principal do sistema - menu de navigação e alertas de gestão"""
    alertas = list_alertas_ativos()
    return templates.TemplateResponse('index.html', {
        'request': request,
        'alertas': alertas,
        'now': datetime.now
    })


@router.get('/init-db', dependencies=[requer('FC_ADMIN_BANCO')])
@handle_exceptions
async def init_db():
    """Initialize/reset the database with seed data"""
    try:
        from ..bootstrap_db import preparar_banco
        from ..services.seed_dominio import seed_dominio
        preparar_banco()
        seed_dominio()
        seed_data()
        return "Database initialized successfully!"
    except Exception as e:
        return f"Error initializing database: {str(e)}"


@router.get('/recreate-db', dependencies=[requer('FC_ADMIN_BANCO')])
@handle_exceptions
async def recreate_db():
    """Recreate the database from scratch (somente APP_ENV=dev)"""
    import os
    from fastapi import HTTPException
    if os.getenv('APP_ENV') != 'dev':
        raise HTTPException(
            status_code=403,
            detail="recreate-db é destrutivo e só está disponível com APP_ENV=dev",
        )
    try:
        from ..bootstrap_db import resetar_banco
        from ..services.seed_dominio import seed_dominio
        resetar_banco()
        seed_dominio()
        seed_data()
        return "Database recreated successfully!"
    except Exception as e:
        return f"Error recreating database: {str(e)}"


@router.get('/saldos', dependencies=[requer('FC_CONS_LANCAMENTO')])
@router.post('/saldos', dependencies=[requer('FC_CONS_LANCAMENTO')])
@handle_exceptions
async def saldos(request: Request):
    start_date = None
    end_date = None
    tipo = None
    qualificador_folha = None
    seq_conta = None
    cod_origem = None
    seq_fonte_recurso = None
    page = 1
    per_page = 50
    sort_by = 'dat_lancamento'
    sort_order = 'desc'

    if request.method == 'POST':
        form = await request.form()
        sd_str = form.get('start_date')
        ed_str = form.get('end_date')
        tipo_str = form.get('tipo')
        qual_str = form.get('qualificador_folha')
        conta_str = form.get('seq_conta')
        origem_str = form.get('cod_origem')
        fonte_str = form.get('seq_fonte_recurso')
        page_str = form.get('page')
        sort_by = form.get('sort_by', 'dat_lancamento')
        sort_order = form.get('sort_order', 'desc')

        if sd_str and ed_str:
            start_date = date.fromisoformat(sd_str)
            end_date = date.fromisoformat(ed_str)
        
        if tipo_str:
            tipo = int(tipo_str)
        
        if qual_str:
            qualificador_folha = int(qual_str)
        
        if conta_str:
            seq_conta = int(conta_str)
        
        if origem_str:
            cod_origem = int(origem_str)

        if fonte_str:
            seq_fonte_recurso = int(fonte_str)

        if page_str:
            page = int(page_str)
    else:
        # GET request - check query params
        page_str = request.query_params.get('page')
        sort_by = request.query_params.get('sort_by', 'dat_lancamento')
        sort_order = request.query_params.get('sort_order', 'desc')
        if page_str:
            page = int(page_str)

    lancamentos, total_count = list_lancamentos(
        start_date=start_date,
        end_date=end_date,
        tipo=tipo,
        qualificador_folha=qualificador_folha,
        seq_conta=seq_conta,
        cod_origem=cod_origem,
        seq_fonte_recurso=seq_fonte_recurso,
        page=page,
        per_page=per_page,
        sort_by=sort_by,
        sort_order=sort_order
    )

    total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1

    tipos = list_tipos_lancamento()
    origens = list_origens_lancamento()
    # Buscar apenas qualificadores folha (que não possuem filhos ativos)
    qualificadores = list_active_qualificadores()
    qualificadores_folha = [q for q in qualificadores if q.is_folha()]
    contas = list_contas_bancarias()

    # Obter código da origem "Manual" para inserção automática
    origem_manual = next((o for o in origens if o.dsc_origem_lancamento == 'Manual'), None)
    cod_origem_manual = origem_manual.cod_origem_lancamento if origem_manual else 1

    # Fontes de recurso ativas — campo opcional SEM default (F9.2)
    from ..services.fonte_recurso_service import listar_fontes
    fontes_recurso = [
        {'seq': f.seq_fonte_recurso,
         'rotulo': f"{f.codigo_completo} · {f.dsc_fonte_recurso}"}
        for f in listar_fontes(status='ativo')
    ]

    return templates.TemplateResponse(
        'saldos.html',
        {
            'request': request,
            'lancamentos': lancamentos,
            'tipos': tipos,
            'origens': origens,
            'qualificadores': qualificadores,
            'qualificadores_folha': qualificadores_folha,
            'contas': contas,
            'page': page,
            'per_page': per_page,
            'total_count': total_count,
            'total_pages': total_pages,
            'sort_by': sort_by,
            'sort_order': sort_order,
            'cod_origem_manual': cod_origem_manual,
            'fontes_recurso': fontes_recurso,
            'filtros': {
                'start_date': start_date.isoformat() if start_date else '',
                'end_date': end_date.isoformat() if end_date else '',
                'tipo': tipo or '',
                'qualificador_folha': qualificador_folha or '',
                'seq_conta': seq_conta or '',
                'cod_origem': cod_origem or '',
                'seq_fonte_recurso': seq_fonte_recurso or '',
            },
        },
    )



@router.post('/saldos/add', name='add_lancamento', dependencies=[requer('FC_INS_LANCAMENTO')])
@handle_exceptions
async def add_lancamento(request: Request):
    form = await request.form()
    data = LancamentoCreate(
        dat_lancamento=date.fromisoformat(form['dat_lancamento']),
        seq_qualificador=int(form['seq_qualificador']),
        val_lancamento=form['val_lancamento'],
        cod_tipo_lancamento=form['cod_tipo_lancamento'],
        cod_origem_lancamento=int(form['cod_origem_lancamento']),
        seq_conta=int(form.get('seq_conta')) if form.get('seq_conta') else None,
        seq_fonte_recurso=(int(form.get('seq_fonte_recurso'))
                           if form.get('seq_fonte_recurso') else None),
    )
    create_lancamento(data)
    return RedirectResponse(request.url_for('saldos'), status_code=303)


@router.post('/saldos/import', dependencies=[requer('FC_IMP_LANCAMENTO')])
@handle_exceptions
async def import_lancamentos(request: Request, file: UploadFile = File(...)):
    """Importa lançamentos com pré-processamento (F2.5): upload → preview."""
    from ..services.preprocessamento import criar_preview
    from .importacao import render_preview

    token, preview = criar_preview('lancamentos', await file.read(), file.filename or '', request.session)
    return render_preview(request, 'lancamentos', token, preview)


@router.get('/saldos/template-xlsx', dependencies=[requer('FC_IMP_LANCAMENTO')])
@handle_exceptions
async def download_lancamento_template():
    """Return an XLSX template for bulk Lancamento import."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Data", "Qualificador", "Valor (R$)", "Tipo", "Banco", "Agencia", "Conta"])
    exemplos = [
        (date(2025, 1, 15), "ICMS", 700000.0, "Entrada", "001", "0001", "123456-7"),
        (date(2025, 1, 15), "REPASSE MUNICÍPIOS", 420000.0, "Saída", "001", "0001", "123456-7"),
        (date(2025, 2, 15), "FPE", 710000.0, "Entrada", "341", "3200", "556677-8"),
        (date(2025, 2, 15), "FOLHA", 525000.0, "Saída", "237", "1234", "98765-4"),
    ]
    for e in exemplos:
        ws.append(list(e))
    stream = BytesIO()
    wb.save(stream)
    stream.seek(0)
    headers = {
        'Content-Disposition': 'attachment; filename=lancamentos_template.xlsx'
    }
    return StreamingResponse(
        stream,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers=headers,
    )


@router.post('/saldos/edit/{seq_lancamento}', name='update_lancamento', dependencies=[requer('FC_ALT_LANCAMENTO')])
@handle_exceptions
async def edit_lancamento_route(request: Request, seq_lancamento: int):
    form = await request.form()
    data = LancamentoCreate(
        dat_lancamento=date.fromisoformat(form['dat_lancamento']),
        seq_qualificador=int(form['seq_qualificador']),
        val_lancamento=form['val_lancamento'],
        cod_tipo_lancamento=form['cod_tipo_lancamento'],
        cod_origem_lancamento=int(form['cod_origem_lancamento']),
    seq_conta=int(form.get('seq_conta')) if form.get('seq_conta') else None,
        seq_fonte_recurso=(int(form.get('seq_fonte_recurso'))
                           if form.get('seq_fonte_recurso') else None),
    )
    update_lancamento(seq_lancamento, data)
    return RedirectResponse(request.url_for('saldos'), status_code=303)


@router.post('/saldos/delete/{seq_lancamento}', name='delete_lancamento', dependencies=[requer('FC_DEL_LANCAMENTO')])
@handle_exceptions
async def delete_lancamento_route(request: Request, seq_lancamento: int):
    delete_lancamento(seq_lancamento)
    return RedirectResponse(request.url_for('saldos'), status_code=303)


@router.get('/conferencia', name='conferencia', dependencies=[requer('FC_CONS_CONFERENCIA')])
@handle_exceptions
async def conferencia(request: Request):
    """Conferência do desembolso — três visões DERIVADAS (F7.1c)."""
    from datetime import timedelta

    from ..services.conferencia_desembolso_service import (
        visao_conciliacao, visao_controle, visao_financeira)

    fim_raw = request.query_params.get('fim') or ''
    inicio_raw = request.query_params.get('inicio') or ''
    fim = date.fromisoformat(fim_raw) if fim_raw else date.today()
    inicio = date.fromisoformat(inicio_raw) if inicio_raw else fim - timedelta(days=13)

    return templates.TemplateResponse('conferencia.html', {
        'request': request,
        'inicio': inicio, 'fim': fim,
        'controle': visao_controle(inicio, fim),
        'financeira': visao_financeira(inicio, fim),
        'conciliacao': visao_conciliacao(inicio, fim),
    })


@router.post('/conferencia/apurado', name='informar_apurado_route',
             dependencies=[requer('FC_MANT_CONFERENCIA')])
@handle_exceptions
async def informar_apurado_route(request: Request):
    """Registra o apurado externo do dia (F7.1c R16)."""
    from decimal import Decimal

    from ..services.conferencia_desembolso_service import informar_apurado

    form = await request.form()
    dia = date.fromisoformat(form['dia'])
    informar_apurado(
        dia,
        val_liberacoes=(Decimal(form['val_apurado_liberacoes'])
                        if form.get('val_apurado_liberacoes') else None),
        val_pagamentos=(Decimal(form['val_apurado_pagamentos'])
                        if form.get('val_apurado_pagamentos') else None),
    )
    return RedirectResponse(f"/conferencia?fim={form.get('fim') or dia.isoformat()}", status_code=303)


