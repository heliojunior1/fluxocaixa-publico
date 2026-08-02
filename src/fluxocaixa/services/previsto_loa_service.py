"""Previsto do desembolso derivado da LOA (spec desembolso R17–R18).

⚠️ SEMPRE derivado, nunca persistido: mensal = LOA de despesa do ano ×
perfil histórico (proporção do realizado de despesa do ano anterior; sem
histórico → 1/12); semanal = rateio do mês pelos dias úteis. **Previsto por
órgão não existe** — a LOA é qualificador+ano (decisão v2.1 item 9: a tela
nunca rateia por órgão silenciosamente).
"""
import calendar
from datetime import date
from decimal import Decimal

from ..models import Lancamento, Liberacao, Loa, Qualificador
from ..models.liberacao import SITUACAO_CONFIRMADA

ZERO = Decimal("0.00")
DOZE = Decimal("12")


def _loa_despesa_total(ano: int) -> Decimal:
    total = ZERO
    for loa in Loa.query.filter_by(num_ano=ano, ind_status='A').all():
        qualificador = Qualificador.query.get(loa.seq_qualificador)
        if qualificador is not None and qualificador.tipo_fluxo == 'despesa':
            total += Decimal(loa.val_loa)
    return total


def _perfil_realizado(ano_base: int) -> dict | None:
    """Proporção mensal do realizado de despesa do ano-base; None sem dado."""
    por_mes = {m: ZERO for m in range(1, 13)}
    total = ZERO
    for lancamento in Lancamento.query.filter(
            Lancamento.ind_status == 'A',
            Lancamento.cod_tipo_lancamento == 'D').all():
        if lancamento.dat_lancamento.year != ano_base:
            continue
        magnitude = abs(Decimal(lancamento.val_lancamento))
        por_mes[lancamento.dat_lancamento.month] += magnitude
        total += magnitude
    if total == 0:
        return None
    return {m: v / total for m, v in por_mes.items()}


def previsto_mensal(ano: int) -> dict:
    """{mes: Decimal} — perfil do ano−1 com fallback 1/12 (R17).

    ⚠️ Precedência da programação (R22, F7.3b): mês com cota ativa usa a Σ
    das cotas — o mais específico vence a derivação da LOA; misturar as duas
    fontes no mesmo mês somaria previsões de naturezas diferentes.
    """
    from .programacao_service import cotas_do_mes, meses_programados

    total = _loa_despesa_total(ano)
    perfil = _perfil_realizado(ano - 1)
    if perfil is None:
        parcela = (total / DOZE).quantize(Decimal("0.01"))
        derivado = {m: parcela for m in range(1, 13)}
    else:
        derivado = {m: (total * perfil[m]).quantize(Decimal("0.01"))
                    for m in range(1, 13)}

    programados = meses_programados(ano)
    return {m: (cotas_do_mes(ano, m) if m in programados else derivado[m])
            for m in range(1, 13)}


def _dias_uteis_do_mes(ano: int, mes: int) -> int:
    _, ultimo = calendar.monthrange(ano, mes)
    return sum(1 for d in range(1, ultimo + 1)
               if date(ano, mes, d).weekday() < 5)


def previsto_da_semana(dias: list[date]) -> Decimal:
    """Rateia o previsto mensal pelos dias úteis da semana dentro do mês."""
    cache_mensal: dict = {}
    total = ZERO
    for dia in dias:
        if dia.weekday() >= 5:
            continue
        chave = (dia.year, dia.month)
        if chave not in cache_mensal:
            cache_mensal[chave] = previsto_mensal(dia.year).get(dia.month, ZERO)
        uteis = _dias_uteis_do_mes(dia.year, dia.month)
        if uteis:
            total += cache_mensal[chave] / Decimal(uteis)
    return total.quantize(Decimal("0.01"))


# ---------------------------------------------------------------------------
# Teto do autorizado (R18)
# ---------------------------------------------------------------------------

def loa_do_qualificador(ano: int, seq_qualificador: int) -> Decimal | None:
    loa = Loa.query.filter_by(num_ano=ano, seq_qualificador=seq_qualificador,
                              ind_status='A').first()
    return Decimal(loa.val_loa) if loa is not None else None


def excedente_do_teto(liberacao: Liberacao) -> Decimal | None:
    """Excedente sobre o autorizado se a liberação for confirmada; None sem
    teto. Alerta, NUNCA bloqueio. ⚠️ O teto é a DOTAÇÃO ATUALIZADA quando
    existir (F8.1 — a LOA envelhece no primeiro crédito adicional); sem
    dotação, a LOA (fallback).
    """
    from .dotacao_service import teto_do_autorizado

    ano = liberacao.dat_liberacao.year
    teto = teto_do_autorizado(ano, liberacao.seq_qualificador)
    if teto is None:
        return None
    confirmadas = ZERO
    for outra in Liberacao.query.filter_by(
            ind_status='A', cod_situacao=SITUACAO_CONFIRMADA,
            seq_qualificador=liberacao.seq_qualificador).all():
        if outra.dat_liberacao.year == ano and outra.seq_liberacao != liberacao.seq_liberacao:
            confirmadas += Decimal(outra.val_liberacao)
    excedente = confirmadas + Decimal(liberacao.val_liberacao) - teto
    return excedente.quantize(Decimal("0.01")) if excedente > 0 else None


# ---------------------------------------------------------------------------
# Relatório de execução (liberado × pago por natureza)
# ---------------------------------------------------------------------------

def relatorio_execucao(ano: int) -> dict:
    """Liberado (confirmadas) × pago (apropriações A−E) por natureza, com o
    previsto TOTAL da LOA — o pago ganha a dimensão pela LIBERAÇÃO consumida
    (vínculo da F7.1b)."""
    from ..models import PagamentoLiberacao
    from .liberacao_service import consumo_da_liberacao

    naturezas: dict = {}
    total_liberado = ZERO
    total_pago = ZERO
    for liberacao in Liberacao.query.filter_by(
            ind_status='A', cod_situacao=SITUACAO_CONFIRMADA).all():
        if liberacao.dat_liberacao.year != ano:
            continue
        natureza = liberacao.cod_natureza_obrigacao
        linha = naturezas.setdefault(natureza, {'liberado': ZERO, 'pago': ZERO})
        linha['liberado'] += Decimal(liberacao.val_liberacao)
        pago = consumo_da_liberacao(liberacao.seq_liberacao)
        linha['pago'] += pago
        total_liberado += Decimal(liberacao.val_liberacao)
        total_pago += pago

    previsto_total = _loa_despesa_total(ano)
    pct_execucao = (total_liberado / previsto_total * 100).quantize(Decimal("0.01")) \
        if previsto_total > 0 else None
    return {
        'ano': ano,
        'naturezas': {k: {'liberado': v['liberado'].quantize(Decimal("0.01")),
                          'pago': v['pago'].quantize(Decimal("0.01"))}
                      for k, v in sorted(naturezas.items())},
        'total_liberado': total_liberado.quantize(Decimal("0.01")),
        'total_pago': total_pago.quantize(Decimal("0.01")),
        'previsto_total': previsto_total.quantize(Decimal("0.01")),
        'pct_execucao': pct_execucao,
    }
