from fastapi import Request
from ..auth.permissoes import requer
from fastapi.responses import RedirectResponse

from . import router, templates, handle_exceptions
from ..services import (
    list_root_qualificadores,
    list_active_qualificadores,
    create_qualificador,
    update_qualificador,
    delete_qualificador_service,
    get_qualificador,
)

@router.get('/qualificadores', dependencies=[requer('FC_CONS_QUALIFICADOR')])
@handle_exceptions
async def qualificadores(request: Request):
    qualificadores_raiz = list_root_qualificadores()
    todos_qualificadores = list_active_qualificadores()
    # Fluxo de confirmação em duas etapas (spec cadastros-nucleo R4)
    confirmar_exclusao = None
    seq_confirmar = request.query_params.get('confirmar_exclusao')
    if seq_confirmar and seq_confirmar.isdigit():
        from ..models import Qualificador
        confirmar_exclusao = Qualificador.query.get(int(seq_confirmar))

    # Banner de "folha vira pai" (R13) — mesmo padrão de duas etapas, com o
    # cadastro pendente carregado para reenvio.
    confirmar_pai = None
    seq_pai = request.query_params.get('confirmar_pai')
    if seq_pai and seq_pai.isdigit():
        from ..models import Qualificador
        pai = Qualificador.query.get(int(seq_pai))
        if pai is not None:
            pend_seq = request.query_params.get('pend_seq')
            confirmar_pai = {
                'pai': pai,
                'num': request.query_params.get('pend_num', ''),
                'dsc': request.query_params.get('pend_dsc', ''),
                'seq_editar': int(pend_seq) if pend_seq and pend_seq.isdigit() else None,
            }

    # F6.5: a tela precisa mostrar a categoria E DE ONDE ela veio. Herança sem
    # visibilidade é armadilha — "por que esta rubrica entrou no piso da
    # saúde?" não pode ser pergunta que só o código responde, que é justamente
    # a situação da heurística que estamos removendo.
    from ..services.categoria_fiscal_service import (
        categoria_resolvida, criar_memo, siglas_ativas,
    )

    memo = criar_memo()
    origem_categoria = {}
    for q in todos_qualificadores:
        resolvida = categoria_resolvida(q, memo)
        if resolvida is None:
            continue
        origem_categoria[q.seq_qualificador] = {
            'sigla': resolvida.txt_sigla,
            'propria': q.cod_categoria_fiscal is not None,
        }

    return templates.TemplateResponse(
        'qualificadores.html',
        {
            'request': request,
            'qualificadores': qualificadores_raiz,
            'todos_qualificadores': todos_qualificadores,
            'confirmar_exclusao': confirmar_exclusao,
            'confirmar_pai': confirmar_pai,
            'categorias_fiscais': siglas_ativas(),
            'origem_categoria': origem_categoria,
        },
    )


def _categoria_do_form(form):
    """Categoria fiscal do form — vazio significa "sem marcação própria"."""
    valor = form.get('cod_categoria_fiscal')
    return int(valor) if valor not in (None, '') else None


def _confirmado(form) -> bool:
    return str(form.get('confirmado', '')).lower() == 'true'


def _reerguer_com_confirmacao(exc, seq_pai, num, desc, seq_editar=None):
    """Erro de "confirme" vira banner de duas etapas, no padrão do R4.

    ⚠️ O payload viaja na query porque o banner precisa REENVIAR o mesmo POST
    depois do "sim" — só o `seq` (como na exclusão) não bastaria: aqui o que
    está pendente é um cadastro inteiro (código, descrição, pai), e perdê-lo
    obrigaria o usuário a redigitar tudo depois de confirmar.
    """
    from urllib.parse import urlencode

    from ..services.validacao import RegraNegocioError

    params = {'confirmar_pai': seq_pai, 'pend_num': num or '',
              'pend_dsc': desc or ''}
    if seq_editar is not None:
        params['pend_seq'] = seq_editar
    raise RegraNegocioError(
        exc.mensagem, destino=f"/qualificadores?{urlencode(params)}")


@router.post('/qualificadores/add', name='add_qualificador', dependencies=[requer('FC_INS_QUALIFICADOR')])
@handle_exceptions
async def add_qualificador_route(request: Request):
    from ..services.validacao import RegraNegocioError

    form = await request.form()
    num_qualif = form.get('num_qualificador')
    desc = form.get('dsc_qualificador')
    pai_id = form.get('cod_qualificador_pai')

    cod_qualificador_pai = int(pai_id) if pai_id and pai_id != '' else None
    cod_categoria_fiscal = _categoria_do_form(form)

    try:
        create_qualificador(num_qualif, desc, cod_qualificador_pai,
                            confirmado=_confirmado(form),
                            cod_categoria_fiscal=cod_categoria_fiscal)
    except RegraNegocioError as exc:
        if 'confirme' in exc.mensagem.lower():
            _reerguer_com_confirmacao(exc, cod_qualificador_pai, num_qualif, desc)
        raise

    return RedirectResponse(request.url_for('qualificadores'), status_code=303)


@router.post('/qualificadores/edit/{seq_qualificador}', dependencies=[requer('FC_ALT_QUALIFICADOR')])
@handle_exceptions
async def edit_qualificador_route(request: Request, seq_qualificador: int):
    from ..services.validacao import RegraNegocioError

    form = await request.form()
    num_qualif = form['num_qualificador']
    desc = form['dsc_qualificador']
    pai_id = form.get('cod_qualificador_pai')
    
    cod_qualificador_pai = int(pai_id) if pai_id and pai_id != '' else None
    cod_categoria_fiscal = _categoria_do_form(form)

    try:
        update_qualificador(seq_qualificador, num_qualif, desc,
                            cod_qualificador_pai, confirmado=_confirmado(form),
                            cod_categoria_fiscal=cod_categoria_fiscal)
    except RegraNegocioError as exc:
        # "confirme" cobre tanto o aviso de folha→pai (R13) quanto o da
        # cascata de renomeação (R17): mesmo fluxo de duas etapas, mesmo botão
        # que reenvia o POST com `confirmado=true`. Um segundo mecanismo de
        # confirmação para a mesma classe de risco só confundiria.
        if 'confirme' in exc.mensagem.lower():
            _reerguer_com_confirmacao(exc, cod_qualificador_pai, num_qualif,
                                      desc, seq_editar=seq_qualificador)
        raise

    return RedirectResponse(request.url_for('qualificadores'), status_code=303)


@router.post('/qualificadores/delete/{seq_qualificador}', name='delete_qualificador', dependencies=[requer('FC_DEL_QUALIFICADOR')])
@handle_exceptions
async def delete_qualificador_route(request: Request, seq_qualificador: int):
    from ..services.validacao import RegraNegocioError

    form = await request.form()
    confirmado = str(form.get('confirmado', '')).lower() == 'true'
    try:
        delete_qualificador_service(seq_qualificador, confirmado=confirmado)
    except RegraNegocioError as exc:
        if 'confirme a exclusão' in exc.mensagem:
            # Leva o usuário ao banner de confirmação (duas etapas — R4)
            raise RegraNegocioError(
                exc.mensagem,
                destino=f"/qualificadores?confirmar_exclusao={seq_qualificador}",
            )
        raise
    return RedirectResponse(request.url_for('qualificadores'), status_code=303)
