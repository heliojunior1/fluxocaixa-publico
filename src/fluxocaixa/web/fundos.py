"""Web controller da gestão de aplicações/fundos (spec saldo-por-fundo
R7–R13, R22)."""
from fastapi import Request
from fastapi.responses import RedirectResponse

from ..auth.permissoes import requer
from ..models import SistemaOrigem, TipoInstrumento, TipoOrigemSaldo
from ..services.fundo_service import (
    alterar_fundo,
    aprovar_fundo,
    classificar_fundo,
    criar_fundo,
    inativar_fundo,
    listar_fundos,
)
from . import handle_exceptions, router, templates
from .entrada import data_iso, inteiro


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
    seq_tipo_instrumento = inteiro(
        request.query_params.get('tipo'), 'tipo de instrumento')

    lista = listar_fundos(cod=cod, dsc=dsc, status=status, pendente=pendente,
                          seq_tipo_instrumento=seq_tipo_instrumento)
    tipos = {t.seq_tipo_origem_saldo: t.txt_sigla for t in TipoOrigemSaldo.query.all()}
    sistemas = {s.seq_sistema_origem: s.txt_sigla for s in SistemaOrigem.query.all()}
    tipos_instrumento = {t.seq_tipo_instrumento: t
                         for t in TipoInstrumento.query.all()}
    tipos_instrumento_ativos = sorted(
        (t for t in tipos_instrumento.values() if t.ind_status == 'A'),
        key=lambda t: t.txt_sigla)

    from ..models import FonteRecurso
    from ..services.fonte_recurso_service import listar_fontes
    fontes_por_seq = {f.seq_fonte_recurso: f for f in FonteRecurso.query.all()}
    fontes_ativas = [
        {'seq': f.seq_fonte_recurso, 'rotulo': f"{f.codigo_completo} · {f.dsc_fonte_recurso}"}
        for f in listar_fontes(status='ativo')
    ]

    fundos_view = [
        {
            'seq_fundo': f.seq_fundo,
            'cod_fundo': f.cod_fundo,
            'dsc_fundo': f.dsc_fundo,
            'origem': _rotulo_origem(f, tipos, sistemas),
            'ativo': f.ind_status == 'A',
            'pendente': f.ind_pendente_revisao == 'S',
            'seq_fonte_recurso': f.seq_fonte_recurso,
            'fonte': (fontes_por_seq[f.seq_fonte_recurso].codigo_completo
                      if f.seq_fonte_recurso in fontes_por_seq else None),
            'seq_tipo_instrumento': f.seq_tipo_instrumento,
            'tipo_instrumento': (
                tipos_instrumento[f.seq_tipo_instrumento].txt_sigla
                if f.seq_tipo_instrumento in tipos_instrumento else ''),
            'liquidez_imediata': f.ind_liquidez_imediata == 'S',
            'dat_vencimento': (f.dat_vencimento.isoformat()
                               if f.dat_vencimento else ''),
        }
        for f in lista
    ]
    return templates.TemplateResponse(
        'fundos.html',
        {
            'request': request,
            'fundos': fundos_view,
            'fontes_ativas': fontes_ativas,
            'tipos_instrumento': [
                {'seq': t.seq_tipo_instrumento, 'sigla': t.txt_sigla,
                 'dsc': t.dsc_tipo_instrumento or t.txt_sigla}
                for t in tipos_instrumento_ativos
            ],
            'filtros': {'cod': cod or '', 'dsc': dsc or '', 'status': status or '',
                        'pendente': pendente or False,
                        'tipo': seq_tipo_instrumento or ''},
        },
    )


@router.post('/fundos/adicionar', name='add_fundo', dependencies=[requer('FC_INS_FUNDO')])
@handle_exceptions
async def add_fundo(request: Request):
    form = await request.form()
    criar_fundo(
        form.get('cod_fundo', ''), form.get('dsc_fundo', ''),
        seq_tipo_instrumento=inteiro(
            form.get('seq_tipo_instrumento'), 'tipo de instrumento'),
        ind_liquidez_imediata=form.get('ind_liquidez_imediata', 'S'),
        dat_vencimento=data_iso(form.get('dat_vencimento'), 'vencimento'),
    )
    return RedirectResponse('/fundos', status_code=303)


@router.post('/fundos/{seq_fundo}/editar', name='edit_fundo', dependencies=[requer('FC_ALT_FUNDO')])
@handle_exceptions
async def edit_fundo(request: Request, seq_fundo: int):
    form = await request.form()
    alterar_fundo(
        seq_fundo, form.get('dsc_fundo', ''),
        seq_tipo_instrumento=inteiro(
            form.get('seq_tipo_instrumento'), 'tipo de instrumento'),
        ind_liquidez_imediata=form.get('ind_liquidez_imediata') or None,
        # None explícito limpa o vencimento (campo esvaziado no form)
        dat_vencimento=data_iso(form.get('dat_vencimento'), 'vencimento'),
    )
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


@router.post('/fundos/{seq_fundo}/classificar-fonte', name='classificar_fonte_fundo',
             dependencies=[requer('FC_MANT_FONTE_RECURSO')])
@handle_exceptions
async def classificar_fonte_fundo(request: Request, seq_fundo: int):
    """Classifica o fundo numa fonte de recursos (spec saldo-por-fundo R21)."""
    form = await request.form()
    raw = (form.get('seq_fonte_recurso') or '').strip()
    classificar_fundo(seq_fundo, int(raw) if raw else None)
    return RedirectResponse('/fundos', status_code=303)
