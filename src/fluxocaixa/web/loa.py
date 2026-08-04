"""Rotas web para gestão da LOA (Lei Orçamentária Anual).

A regra de negócio (upsert por ano+qualificador, resolução de qualificador,
inativação) vive em `services/loa_service.py` — spec cadastros-nucleo R24.
O parse de arquivo antigo (`_importar_csv`/`_importar_excel`) morreu com a
F2.5: a importação passa pelo adapter com preview.
"""
from decimal import Decimal

from fastapi import File, Form, Request, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse

from ..auth.permissoes import requer
from ..models import Loa, Qualificador
from ..services import loa_service
from . import handle_exceptions, router, templates

try:
    import openpyxl  # noqa: F401 - só sinaliza suporte a .xlsx na tela
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False


# ==================== Listagem ====================

@router.get('/loa', dependencies=[requer('FC_CONS_LOA')])
@handle_exceptions
async def loa_list(request: Request):
    """Página principal da LOA com listagem e formulários."""
    ano_filtro = request.query_params.get('ano', None)

    query = Loa.query.filter_by(ind_status='A').order_by(Loa.num_ano.desc(), Loa.seq_qualificador)
    if ano_filtro:
        query = query.filter(Loa.num_ano == int(ano_filtro))

    registros = query.all()

    # Anos disponíveis para filtro
    anos_disponiveis = sorted(
        set(r.num_ano for r in Loa.query.filter_by(ind_status='A').all()),
        reverse=True,
    )

    # Qualificadores folha (sem filhos ativos) para o form manual
    todos_qualificadores = Qualificador.query.filter_by(ind_status='A').order_by(Qualificador.num_qualificador).all()
    qualificadores_folha = [q for q in todos_qualificadores if q.is_folha()]

    # Totais por ano
    totais = {}
    for r in registros:
        totais[r.num_ano] = totais.get(r.num_ano, Decimal(0)) + r.val_loa

    return templates.TemplateResponse(
        'loa.html',
        {
            'request': request,
            'registros': registros,
            'anos_disponiveis': anos_disponiveis,
            'ano_filtro': int(ano_filtro) if ano_filtro else None,
            'qualificadores': qualificadores_folha,
            'totais': totais,
            'has_openpyxl': HAS_OPENPYXL,
        },
    )


# ==================== Adicionar Manual ====================

@router.post('/loa/add', dependencies=[requer('FC_INS_LOA')])
@handle_exceptions
async def loa_add(request: Request):
    """Adiciona um registro LOA manualmente (upsert no serviço)."""
    form = await request.form()
    num_ano = int(form.get('num_ano'))
    seq_qualificador = int(form.get('seq_qualificador'))
    val_loa = Decimal(form.get('val_loa', '0').replace('.', '').replace(',', '.'))

    loa_service.salvar_manual(num_ano, seq_qualificador, val_loa)
    # str() explícito: `url_for` devolve URL (não str) — concatenar direto
    # era TypeError 500 latente, pego pelo BDD deste change
    return RedirectResponse(
        str(request.url_for('loa_list')) + f'?ano={num_ano}', status_code=303)


# ==================== Excluir ====================

@router.post('/loa/delete/{seq_loa}', dependencies=[requer('FC_DEL_LOA')])
@handle_exceptions
async def loa_delete(request: Request, seq_loa: int):
    """Exclui (inativa) um registro LOA."""
    loa_service.inativar(seq_loa)
    return RedirectResponse(request.url_for('loa_list'), status_code=303)


# ==================== Importar CSV / Excel ====================

@router.post('/loa/importar', dependencies=[requer('FC_IMP_LOA')])
@handle_exceptions
async def loa_importar(request: Request, arquivo: UploadFile = File(...), ano_import: int = Form(...)):
    """Importa registros LOA de um arquivo CSV ou Excel (.xlsx).

    Formato esperado (CSV):
    qualificador,valor
    ICMS,850000000.00
    IPVA,120000000.00

    Ou com código numérico:
    num_qualificador,valor
    1.0.0,850000000.00
    """
    if not arquivo.filename:
        return JSONResponse({'error': 'Nenhum arquivo enviado'}, status_code=400)

    # Pré-processamento (F2.5): upload → preview → confirmar. O ano é fixado no
    # adapter antes da validação (o preview e a gravação usam o mesmo ano).
    from ..services.preprocessamento import criar_preview
    from .importacao import render_preview

    token, preview = criar_preview('loa', await _ler(arquivo), arquivo.filename,
                                   request.session, contexto={"ano": ano_import})
    return render_preview(request, 'loa', token, preview)


async def _ler(arquivo):
    """Upload com teto de bytes e extensão validada (importacao-arquivos R6)."""
    from ..services.preprocessamento import ler_upload_limitado, validar_extensao

    validar_extensao(arquivo.filename)
    return await ler_upload_limitado(arquivo)
