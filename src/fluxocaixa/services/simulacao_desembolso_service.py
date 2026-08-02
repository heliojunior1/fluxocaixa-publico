"""Simulação de disponibilidade do desembolso (spec desembolso R9–R12).

O para-brisa: compõe, por mês, a disponibilidade projetada do grupo de fonte
— saldo bruto (F9.1) − reservas (F7.4, hoje 0 — a subtração ÚNICA acontece
aqui, nunca embutida no saldo) + receitas repartidas (F9.3; 'N' fora do modo
prudente) − despesas ajustadas (anti-dupla contagem por qualificador × mês ×
grupo, piso zero) − pendente posicionado − lote (rascunhos posicionados).

Veredicto sobre o mínimo da curva COM lote × colchão do grupo; a
**insuficiência estrutural** (curva-base SEM lote violando o colchão) é
acusada à parte — "não é o lote". A confirmação do lote é transação única
com snapshot imutável (rastro da decisão).
"""
from datetime import date
from decimal import Decimal

from ..auth.contexto import cod_pessoa_atual
from ..models import (
    Liberacao,
    LiberacaoEvento,
    ParametroDesembolso,
    SimulacaoDesembolso,
)
from ..models.base import db
from ..models.fonte_recurso import GRUPO_LIVRE, GRUPO_VINCULADO
from ..models.liberacao import (
    EVENTO_CONFIRMACAO,
    SITUACAO_CONFIRMADA,
    SITUACAO_RASCUNHO,
)
from ..models.simulacao_desembolso import PARAM_COLCHAO_MINIMO
from ..repositories.saldo_fundo_repository import saldo_bruto_por_grupo
from .liberacao_service import consumo_da_liberacao
from .reparticao_fonte_service import GRUPO_NAO_CLASSIFICADO, repartir_valor
from .validacao import RegraNegocioError

MODO_PRUDENTE = 'prudente'
MODO_INFORMATIVO = 'informativo'

VEREDICTO_OK = 'OK'
VEREDICTO_ALERTA = 'ALERTA'
VEREDICTO_BLOQUEIO = 'BLOQUEIO'

ZERO = Decimal("0.00")


# ---------------------------------------------------------------------------
# Colchão por grupo (R11)
# ---------------------------------------------------------------------------

def colchao_do_grupo(grupo: str) -> Decimal:
    """Override do grupo vence o default global (grupo nulo); sem ambos, 0."""
    override = ParametroDesembolso.query.filter_by(
        cod_parametro=PARAM_COLCHAO_MINIMO, cod_grupo=grupo, ind_status='A').first()
    if override is not None:
        return Decimal(override.val_parametro).quantize(Decimal("0.01"))
    global_ = ParametroDesembolso.query.filter_by(
        cod_parametro=PARAM_COLCHAO_MINIMO, cod_grupo=None, ind_status='A').first()
    if global_ is not None:
        return Decimal(global_.val_parametro).quantize(Decimal("0.01"))
    return ZERO


def definir_colchao(valor: Decimal, grupo: str | None = None) -> ParametroDesembolso:
    valor = Decimal(valor)
    if valor < 0:
        raise RegraNegocioError("Colchão mínimo não pode ser negativo")
    anterior = ParametroDesembolso.query.filter_by(
        cod_parametro=PARAM_COLCHAO_MINIMO, cod_grupo=grupo, ind_status='A').first()
    if anterior is not None:
        anterior.ind_status = 'I'
        anterior.dat_alteracao = date.today()
        anterior.cod_pessoa_alteracao = cod_pessoa_atual()
    novo = ParametroDesembolso(
        cod_parametro=PARAM_COLCHAO_MINIMO, cod_grupo=grupo,
        val_parametro=valor.quantize(Decimal("0.01")), ind_status='A',
        cod_pessoa_inclusao=cod_pessoa_atual())
    db.session.add(novo)
    db.session.commit()
    return novo


# ---------------------------------------------------------------------------
# Posicionamento (dat_prevista_desembolso → mês do horizonte)
# ---------------------------------------------------------------------------

def _mes_posicionado(dat_prevista: date, ano: int, meses: list[int]) -> int | None:
    """Anterior ao horizonte → primeiro mês (pendente vencido desconta
    integral); posterior → fora (None)."""
    if (dat_prevista.year, dat_prevista.month) < (ano, meses[0]):
        return meses[0]
    if dat_prevista.year == ano and dat_prevista.month in meses:
        return dat_prevista.month
    return None


def _liberacoes_posicionadas(situacao: str, grupo: str, ano: int,
                             meses: list[int]) -> tuple[dict, dict, list]:
    """({(seq_qualificador, mes): valor}, {mes: total}, [liberações])."""
    por_chave: dict = {}
    por_mes = {m: ZERO for m in meses}
    liberacoes = []
    q = Liberacao.query.filter_by(ind_status='A', cod_situacao=situacao).all()
    for liberacao in q:
        if liberacao.fonte_recurso.grupo != grupo:
            continue
        valor = Decimal(liberacao.val_liberacao)
        if situacao == SITUACAO_CONFIRMADA:
            valor -= consumo_da_liberacao(liberacao.seq_liberacao)
        if valor <= 0:
            continue
        mes = _mes_posicionado(liberacao.dat_prevista_desembolso, ano, meses)
        if mes is None:
            continue
        chave = (liberacao.seq_qualificador, mes)
        por_chave[chave] = por_chave.get(chave, ZERO) + valor
        por_mes[mes] += valor
        liberacoes.append(liberacao)
    return por_chave, por_mes, liberacoes


# ---------------------------------------------------------------------------
# Simulação (R9/R10/R11)
# ---------------------------------------------------------------------------

def simular(cenario_id: int, ano: int, grupo: str = GRUPO_LIVRE,
            modo: str = MODO_PRUDENTE, mes_inicial: int = 1,
            qtd_meses: int = 12) -> dict:
    from .relatorio.dfc_projecao import resolver_projecao

    if grupo not in (GRUPO_LIVRE, GRUPO_VINCULADO):
        raise RegraNegocioError("Grupo de fonte inválido")
    if modo not in (MODO_PRUDENTE, MODO_INFORMATIVO):
        raise RegraNegocioError("Modo de simulação inválido")

    meses = list(range(mes_inicial, min(12, mes_inicial + qtd_meses - 1) + 1))
    mapa, origem = resolver_projecao(cenario_id, ano)

    # Receitas repartidas (F9.3) — 'N' fica fora do prudente (R10)
    receitas = {m: ZERO for m in meses}
    nao_classificado = ZERO
    for (seq, tipo, mes), valor in mapa.items():
        if tipo != 'C' or mes not in meses:
            continue
        if seq is None:  # projeção agregada sem qualificador → não classificado
            grupos_valor = {GRUPO_NAO_CLASSIFICADO: abs(valor)}
        else:
            grupos_valor = repartir_valor(seq, ano, abs(valor))
        receitas[mes] += grupos_valor.get(grupo, ZERO)
        parcela_n = grupos_valor.get(GRUPO_NAO_CLASSIFICADO, ZERO)
        nao_classificado += parcela_n
        if modo == MODO_INFORMATIVO:
            receitas[mes] += parcela_n

    # Pendente e lote posicionados pela data prevista (R9)
    pend_chave, pend_mes, _confirmadas = _liberacoes_posicionadas(
        SITUACAO_CONFIRMADA, grupo, ano, meses)
    _lote_chave, lote_mes, rascunhos = _liberacoes_posicionadas(
        SITUACAO_RASCUNHO, grupo, ano, meses)

    # Despesas ajustadas — anti-dupla contagem (qualificador × mês × grupo),
    # piso zero; despesa entra INTEIRA no grupo simulado (conservador)
    despesas = {m: ZERO for m in meses}
    for (seq, tipo, mes), valor in mapa.items():
        if tipo != 'D' or mes not in meses:
            continue
        magnitude = abs(valor)
        ajustada = max(ZERO, magnitude - pend_chave.get((seq, mes), ZERO))
        despesas[mes] += ajustada

    # F7.4: a subtração ÚNICA das reservas/bloqueios (seção 4.4 do módulo —
    # nunca embutida no saldo bruto)
    from .reserva_service import reservas_vigentes_do_grupo

    reservas = reservas_vigentes_do_grupo(grupo, date.today())
    saldo_inicial = saldo_bruto_por_grupo()[grupo] - reservas
    colchao = colchao_do_grupo(grupo)

    periodos = []
    acumulado_base = saldo_inicial
    acumulado_lote = saldo_inicial
    for mes in meses:
        fluxo = receitas[mes] - despesas[mes] - pend_mes[mes]
        acumulado_base += fluxo
        acumulado_lote += fluxo - lote_mes[mes]
        periodos.append({
            'ano': ano, 'mes': mes,
            'receitas': receitas[mes], 'despesas_ajustadas': despesas[mes],
            'pendente': pend_mes[mes], 'lote': lote_mes[mes],
            'saldo_base': acumulado_base.quantize(Decimal("0.01")),
            'saldo_projetado': acumulado_lote.quantize(Decimal("0.01")),
        })

    minimo_lote = min((p['saldo_projetado'] for p in periodos), default=saldo_inicial)
    minimo_base = min((p['saldo_base'] for p in periodos), default=saldo_inicial)

    if minimo_lote < 0:
        veredicto = VEREDICTO_BLOQUEIO
    elif minimo_lote < colchao:
        veredicto = VEREDICTO_ALERTA
    else:
        veredicto = VEREDICTO_OK

    estrutural = None
    if minimo_base < colchao:
        pior = min(periodos, key=lambda p: p['saldo_base'])
        estrutural = {
            'mes': pior['mes'],
            'saldo_base': minimo_base,
            'faltante': (colchao - minimo_base).quantize(Decimal("0.01")),
        }

    return {
        'grupo': grupo, 'modo': modo, 'ano': ano,
        'saldo_inicial': saldo_inicial, 'reservas': reservas,
        'colchao': colchao, 'periodos': periodos,
        'veredicto': veredicto, 'minimo': minimo_lote,
        'estrutural': estrutural,
        'nao_classificado': nao_classificado.quantize(Decimal("0.01")),
        'total_lote': sum(lote_mes.values(), ZERO),
        'qtd_rascunhos': len(rascunhos),
        'origem_projecao': origem,
    }


# ---------------------------------------------------------------------------
# Confirmação do lote (R12) — transação ÚNICA com snapshot
# ---------------------------------------------------------------------------

def _serializavel(valor):
    if isinstance(valor, Decimal):
        return str(valor)
    if isinstance(valor, dict):
        return {str(k): _serializavel(v) for k, v in valor.items()}
    if isinstance(valor, list):
        return [_serializavel(v) for v in valor]
    return valor


def confirmar_lote(cenario_id: int, ano: int, grupo: str = GRUPO_LIVRE,
                   modo: str = MODO_PRUDENTE, mes_inicial: int = 1,
                   qtd_meses: int = 12,
                   justificativa: str | None = None) -> SimulacaoDesembolso:
    if modo != MODO_PRUDENTE:
        raise RegraNegocioError(
            "Confirmação de lote exige o modo prudente (autorizativo)")

    resultado = simular(cenario_id, ano, grupo=grupo, modo=modo,
                        mes_inicial=mes_inicial, qtd_meses=qtd_meses)

    meses = [p['mes'] for p in resultado['periodos']]
    _chaves, _mes, rascunhos = _liberacoes_posicionadas(
        SITUACAO_RASCUNHO, grupo, ano, meses)
    if not rascunhos:
        raise RegraNegocioError("Nenhuma liberação em rascunho no lote do grupo")

    if resultado['veredicto'] == VEREDICTO_BLOQUEIO:
        raise RegraNegocioError(
            "Caixa insuficiente — a curva fica negativa; confirmação bloqueada")
    justificativa = (justificativa or "").strip() or None
    if resultado['veredicto'] == VEREDICTO_ALERTA and not justificativa:
        raise RegraNegocioError(
            "Abaixo do colchão mínimo — confirmar exige justificativa registrada")

    # Teto da LOA (F7.3a D3): o lote NÃO trava no teto — a decisão já é
    # consciente e auditada; os excedentes entram no snapshot.
    from .previsto_loa_service import excedente_do_teto

    excedentes = []
    for liberacao in rascunhos:
        excedente = excedente_do_teto(liberacao)
        if excedente is not None:
            excedentes.append({'seq_liberacao': liberacao.seq_liberacao,
                               'excedente': excedente})
    resultado['excedentes_teto'] = excedentes

    # snapshot imutável + confirmações num ÚNICO commit (meio lote não existe)
    snapshot = SimulacaoDesembolso(
        dat_simulacao=date.today(), cod_grupo=grupo,
        cod_veredicto=resultado['veredicto'],
        json_snapshot=_serializavel(resultado),
        cod_pessoa_inclusao=cod_pessoa_atual())
    db.session.add(snapshot)
    db.session.flush()

    for liberacao in rascunhos:
        liberacao.cod_situacao = SITUACAO_CONFIRMADA
        liberacao.dat_alteracao = date.today()
        liberacao.cod_pessoa_alteracao = cod_pessoa_atual()
        if justificativa:
            liberacao.dsc_justificativa = justificativa
        db.session.add(LiberacaoEvento(
            seq_liberacao=liberacao.seq_liberacao,
            cod_tipo_evento=EVENTO_CONFIRMACAO,
            dsc_justificativa=justificativa,
            dsc_referencia_snapshot=snapshot.referencia,
            dat_evento=date.today(),
            cod_pessoa_evento=cod_pessoa_atual(),
        ))
    db.session.commit()
    return snapshot
