"""Web controller do catálogo de fontes de recurso (spec fonte-recurso R1–R6).

A tela reúne o catálogo (CRUD, aprovação de auto-cadastradas, importação da
tabela STN) e a decomposição da disponibilidade por grupo — sempre com o
rótulo "operacional": o número daqui NÃO é a disponibilidade fiscal do RGF.
"""
from datetime import date

from fastapi import File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse

from . import handle_exceptions, router, templates
from ..auth.permissoes import requer
from ..repositories.saldo_fundo_repository import saldo_bruto_por_grupo
from ..services.fonte_recurso_service import (

    alterar_fonte,
    aprovar_fonte,
    criar_fonte,
    inativar_fonte,
    listar_fontes,
)


@router.get('/fontes-recurso', name='fontes_recurso',
            dependencies=[requer('FC_CONS_FONTE_RECURSO')])
@handle_exceptions
async def fontes_recurso(request: Request):
    exercicio_raw = request.query_params.get('exercicio') or ''
    exercicio = int(exercicio_raw) if exercicio_raw.isdigit() else None
    pendente = True if request.query_params.get('pendente') == 'true' else None

    fontes = listar_fontes(exercicio=exercicio, pendente=pendente)
    exercicios = sorted({f.num_exercicio_vigencia for f in listar_fontes()}, reverse=True)

    fontes_view = [
        {
            'seq': f.seq_fonte_recurso,
            'codigo': f.codigo_completo,
            'dsc': f.dsc_fonte_recurso,
            'vinculada': f.ind_vinculada == 'V',
            'grupo_destinacao': f.dsc_grupo_destinacao or '',
            'origem': f.cod_origem_classificacao,
            'vigencia': f.num_exercicio_vigencia,
            'ativo': f.ind_status == 'A',
            'pendente': f.ind_pendente_revisao == 'S',
        }
        for f in fontes
    ]
    return templates.TemplateResponse(
        'fontes_recurso.html',
        {
            'request': request,
            'fontes': fontes_view,
            'exercicios': exercicios,
            'grupos': saldo_bruto_por_grupo(),
            'exercicio_corrente': date.today().year,
            'filtros': {'exercicio': exercicio_raw, 'pendente': pendente or False},
        },
    )


@router.post('/fontes-recurso/adicionar', name='add_fonte_recurso',
             dependencies=[requer('FC_MANT_FONTE_RECURSO')])
@handle_exceptions
async def add_fonte_recurso(request: Request):
    form = await request.form()
    criar_fonte(
        form.get('identificador', '1'),
        form.get('fonte_stn', ''),
        form.get('dsc', ''),
        int(form.get('exercicio') or date.today().year),
        vinculada=form.get('vinculada', 'V'),
        detalhamento=form.get('detalhamento') or None,
        grupo_destinacao=form.get('grupo_destinacao') or None,
    )
    return RedirectResponse('/fontes-recurso', status_code=303)


@router.post('/fontes-recurso/{seq}/editar', name='edit_fonte_recurso',
             dependencies=[requer('FC_MANT_FONTE_RECURSO')])
@handle_exceptions
async def edit_fonte_recurso(request: Request, seq: int):
    form = await request.form()
    alterar_fonte(
        seq,
        dsc=form.get('dsc'),
        vinculada=form.get('vinculada'),
        grupo_destinacao=form.get('grupo_destinacao'),
    )
    return RedirectResponse('/fontes-recurso', status_code=303)


@router.post('/fontes-recurso/{seq}/aprovar', name='aprovar_fonte_recurso',
             dependencies=[requer('FC_MANT_FONTE_RECURSO')])
@handle_exceptions
async def aprovar_fonte_recurso(request: Request, seq: int):
    form = await request.form()
    aprovar_fonte(seq, vinculada=form.get('vinculada') or None)
    return RedirectResponse('/fontes-recurso', status_code=303)


@router.post('/fontes-recurso/{seq}/inativar', name='inativar_fonte_recurso',
             dependencies=[requer('FC_MANT_FONTE_RECURSO')])
@handle_exceptions
async def inativar_fonte_recurso(request: Request, seq: int):
    inativar_fonte(seq)
    return RedirectResponse('/fontes-recurso', status_code=303)


@router.post('/fontes-recurso/importar', name='importar_fontes_recurso',
             dependencies=[requer('FC_IMP_FONTE_RECURSO')])
@handle_exceptions
async def importar_fontes_recurso(request: Request, arquivo: UploadFile = File(...),
                                  exercicio_import: int = Form(...)):
    """Importa a tabela oficial STN da vigência (upload → preview → confirmar)."""
    from ..services.preprocessamento import criar_preview
    from ..services.preprocessamento_adapters import _AdapterFontesRecurso
    from .importacao import render_preview

    _AdapterFontesRecurso._exercicio = exercicio_import
    token, preview = criar_preview(
        'fontes_recurso', await _ler(arquivo), arquivo.filename, request.session)
    return render_preview(request, 'fontes_recurso', token, preview)


@router.get('/fontes-recurso/conciliacao', name='conciliacao_fonte',
            dependencies=[requer('FC_REL_CONCILIACAO_FONTE')])
@handle_exceptions
async def conciliacao_fonte(request: Request):
    """Operacional × contábil por fonte (spec fonte-recurso R10–R12)."""
    from ..services.conciliacao_fonte_service import conciliar

    data_raw = request.query_params.get('data') or ''
    try:
        data_referencia = date.fromisoformat(data_raw)
    except ValueError:
        data_referencia = date.today()
    return templates.TemplateResponse('conciliacao_fonte.html', {
        'request': request,
        'data_referencia': data_referencia,
        'linhas': conciliar(data_referencia),
    })


@router.post('/fontes-recurso/conciliacao/importar', name='importar_disponibilidade_contabil',
             dependencies=[requer('FC_IMP_DISPONIBILIDADE_CONTABIL')])
@handle_exceptions
async def importar_disponibilidade_contabil(request: Request,
                                            arquivo: UploadFile = File(...),
                                            data_import: str = Form(...)):
    """Importa o balancete/MSC por fonte (upload → preview → confirmar)."""
    from ..services.preprocessamento import criar_preview
    from ..services.preprocessamento_adapters import _AdapterDisponibilidadeContabil
    from .importacao import render_preview

    _AdapterDisponibilidadeContabil._data = date.fromisoformat(data_import)
    token, preview = criar_preview(
        'disponibilidade_contabil', await _ler(arquivo), arquivo.filename,
        request.session)
    return render_preview(request, 'disponibilidade_contabil', token, preview)


async def _ler(arquivo):
    """Upload com teto de bytes e extensão validada (importacao-arquivos R6)."""
    from ..services.preprocessamento import ler_upload_limitado, validar_extensao

    validar_extensao(arquivo.filename)
    return await ler_upload_limitado(arquivo)
