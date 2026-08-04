import logging
from datetime import date, datetime
from io import BytesIO

import openpyxl
from fastapi import File, Request, UploadFile
from fastapi.responses import RedirectResponse, StreamingResponse

from ..auth.permissoes import requer
from ..domain import LancamentoCreate
from .entrada import data_iso, inteiro, texto_obrigatorio
from ..services.validacao import RegraNegocioError
from . import handle_exceptions, router, templates
from ..services import (
    create_lancamento,
    delete_lancamento,
    list_active_qualificadores,
    list_alertas_ativos,
    list_contas_bancarias,
    list_lancamentos,
    list_origens_lancamento,
    list_tipos_lancamento,
    update_lancamento,
)
from ..services.seed import seed_data


def _exercicio_combo():
    """F10.4 (R28): combos de tela oferecem o plano do exercício corrente
    RESOLVIDO — nunca a união de todos os planos."""
    from ..services.qualificador_service import exercicio_corrente

    return exercicio_corrente()

logger = logging.getLogger(__name__)


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


async def _exigir_seed_destrutivo_autorizado(request: Request, rota: str):
    """Guarda das rotas que acionam `seed_data()` (controle-acesso R6, infra R8).

    As duas rotas removem FISICAMENTE lançamento, qualificador, pagamento e
    órgão. Antes, só `recreate-db` exigia `APP_ENV=dev` — assimetria que vinha
    da spec e deixava desprotegida a rota que ninguém achava perigosa.

    Vive num helper, e não repetido em cada endpoint, porque duplicar guarda de
    segurança é como a primeira ficou para trás.
    """
    import os

    from fastapi import HTTPException

    if os.getenv('APP_ENV') != 'dev':
        raise HTTPException(
            status_code=403,
            detail=f"{rota} é destrutivo e só está disponível com APP_ENV=dev",
        )
    form = await request.form()
    if form.get('confirmado') != 'true':
        raise RegraNegocioError(
            f"{rota} apaga lançamentos, qualificadores, pagamentos e órgãos. "
            "Reenvie com confirmado=true para prosseguir."
        )


@router.post('/init-db', dependencies=[requer('FC_ADMIN_BANCO')])
@handle_exceptions
async def init_db(request: Request):
    """Migra e repopula o banco com os dados de demonstração (só em dev).

    POST, e não GET: `SameSite=lax` envia o cookie de sessão em navegação
    top-level GET, então uma rota destrutiva em GET é acionável por link de
    terceiro. A confirmação protege do acionamento acidental; contra terceiro,
    quem protege é o token CSRF (change protecao-csrf-global).
    """
    await _exigir_seed_destrutivo_autorizado(request, 'init-db')
    try:
        from ..bootstrap_db import preparar_banco
        from ..services.seed_dominio import seed_dominio
        preparar_banco()
        seed_dominio()
        seed_data()
        return "Database initialized successfully!"
    except Exception:
        # nunca devolver str(e): com SQLAlchemy vaza SQL, tabela, coluna e às
        # vezes a string de conexão (o SafeAPIRouter já faz o certo em toda
        # outra rota — estas duas o contornavam)
        logger.exception("Falha ao inicializar o banco")
        return "Erro ao inicializar o banco. Consulte o log do servidor."


@router.post('/recreate-db', dependencies=[requer('FC_ADMIN_BANCO')])
@handle_exceptions
async def recreate_db(request: Request):
    """Recria o banco do zero (somente APP_ENV=dev)."""
    await _exigir_seed_destrutivo_autorizado(request, 'recreate-db')
    try:
        from ..bootstrap_db import resetar_banco
        from ..services.seed_dominio import seed_dominio
        resetar_banco()
        seed_dominio()
        seed_data()
        return "Database recreated successfully!"
    except Exception:
        logger.exception("Falha ao recriar o banco")
        return "Erro ao recriar o banco. Consulte o log do servidor."


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

        # conversão VALIDADA (R15): valor inválido é erro de negócio, não 500
        if sd_str and ed_str:
            start_date = data_iso(sd_str, 'data inicial')
            end_date = data_iso(ed_str, 'data final')

        tipo = tipo_str or None
        qualificador_folha = inteiro(qual_str, 'qualificador')
        seq_conta = inteiro(conta_str, 'conta')
        cod_origem = inteiro(origem_str, 'origem')
        seq_fonte_recurso = inteiro(fonte_str, 'fonte de recursos')
        page = inteiro(page_str, 'página', default=1)
    else:
        # GET request - check query params
        page_str = request.query_params.get('page')
        sort_by = request.query_params.get('sort_by', 'dat_lancamento')
        sort_order = request.query_params.get('sort_order', 'desc')
        page = inteiro(page_str, 'página', default=1)

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
    qualificadores = list_active_qualificadores(_exercicio_combo())
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

    token, preview = criar_preview('lancamentos', await _ler(file), file.filename or '', request.session)
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
        dat_lancamento=data_iso(form.get('dat_lancamento'), 'data', obrigatorio=True),
        seq_qualificador=inteiro(form.get('seq_qualificador'), 'qualificador', obrigatorio=True),
        val_lancamento=texto_obrigatorio(form, 'val_lancamento'),
        cod_tipo_lancamento=texto_obrigatorio(form, 'cod_tipo_lancamento'),
        cod_origem_lancamento=inteiro(form.get('cod_origem_lancamento'), 'origem', obrigatorio=True),
        seq_conta=inteiro(form.get('seq_conta'), 'conta'),
        seq_fonte_recurso=inteiro(form.get('seq_fonte_recurso'), 'fonte de recursos'),
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
        visao_conciliacao,
        visao_controle,
        visao_financeira,
    )

    fim = data_iso(request.query_params.get('fim'), 'fim', default=date.today())
    inicio = data_iso(request.query_params.get('inicio'), 'início',
                      default=fim - timedelta(days=13))

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




async def _ler(arquivo):
    """Upload com teto de bytes e extensão validada (importacao-arquivos R6)."""
    from ..services.preprocessamento import ler_upload_limitado, validar_extensao

    validar_extensao(arquivo.filename)
    return await ler_upload_limitado(arquivo)
