"""Relatório do funil LOA→caixa e conciliação (spec execucao-orcamentaria R8–R9).

Só leitura — TUDO derivado dos serviços existentes; nenhuma tabela própria.
"""
from decimal import Decimal

from ..models import ExecucaoOrcamentaria, Pagamento, Qualificador
from ..models.execucao_orcamentaria import (
    ESTAGIO_EMPENHO,
    ESTAGIO_LIQUIDACAO,
    ESTAGIO_PAGAMENTO,
)

ZERO = Decimal("0.00")

DIRECAO_ORCAMENTO = "pago no orçamento sem desembolso registrado"
DIRECAO_CAIXA = "desembolso sem execução importada"
DIRECAO_CONCILIADO = "conciliado"


def classificar_diferenca(diferenca: Decimal) -> str:
    """Direção NOMEADA da diferença (R9) — nunca divergência anônima."""
    if diferenca > 0:
        return DIRECAO_ORCAMENTO
    if diferenca < 0:
        return DIRECAO_CAIXA
    return DIRECAO_CONCILIADO


def _linha_zerada():
    return {'empenhado': ZERO, 'liquidado': ZERO, 'pago': ZERO,
            'liquidado_nao_pago': ZERO}


def relatorio_funil(num_ano: int) -> dict:
    """Autorizado × E × L × P × liquidado não pago por qualificador (R8)."""
    from .dotacao_service import teto_do_autorizado
    from .execucao_orcamentaria_service import (
        consumido_pelos_filhos,
        valor_corrente,
    )

    por_qualificador: dict = {}
    for documento in ExecucaoOrcamentaria.query.filter_by(
            num_ano=num_ano, ind_status='A').all():
        linha = por_qualificador.setdefault(documento.seq_qualificador, _linha_zerada())
        corrente = valor_corrente(documento.seq_execucao)
        if documento.cod_estagio == ESTAGIO_EMPENHO:
            linha['empenhado'] += corrente
        elif documento.cod_estagio == ESTAGIO_LIQUIDACAO:
            linha['liquidado'] += corrente
            linha['liquidado_nao_pago'] += \
                corrente - consumido_pelos_filhos(documento.seq_execucao)
        else:
            linha['pago'] += corrente

    # qualificador autorizado (dotação ou LOA) sem execução entra zerado —
    # ausência de execução é informação
    from ..models import Dotacao, Loa

    for dotacao in Dotacao.query.filter_by(num_ano=num_ano, ind_status='A').all():
        por_qualificador.setdefault(dotacao.seq_qualificador, _linha_zerada())
    for loa in Loa.query.filter_by(num_ano=num_ano, ind_status='A').all():
        qualificador = Qualificador.query.get(loa.seq_qualificador)
        if qualificador is not None and qualificador.tipo_fluxo == 'despesa':
            por_qualificador.setdefault(loa.seq_qualificador, _linha_zerada())

    linhas = []
    totais = {'autorizado': ZERO, **_linha_zerada()}
    for seq, valores in por_qualificador.items():
        qualificador = Qualificador.query.get(seq)
        # dotação atualizada vence; LOA é o fallback (mesma precedência do teto)
        autorizado = teto_do_autorizado(num_ano, seq)
        linha = {
            'qualificador': qualificador,
            'autorizado': autorizado,
            **{k: v.quantize(Decimal("0.01")) for k, v in valores.items()},
        }
        linha['pct_empenhado'] = (
            (linha['empenhado'] / autorizado * 100).quantize(Decimal("0.01"))
            if autorizado else None)
        linhas.append(linha)
        if autorizado is not None:
            totais['autorizado'] += autorizado
        for k in ('empenhado', 'liquidado', 'pago', 'liquidado_nao_pago'):
            totais[k] += valores[k]
    linhas.sort(key=lambda item: item['qualificador'].num_qualificador)
    return {
        'linhas': linhas,
        'totais': {k: v.quantize(Decimal("0.01")) for k, v in totais.items()},
    }


def conciliacao_orcamento_caixa(num_ano: int) -> list[dict]:
    """Σ P (orçamentário) × Σ `flc_pagamento` (financeiro) por órgão (R9)."""
    from .execucao_orcamentaria_service import valor_corrente

    orcamentario: dict = {}
    for documento in ExecucaoOrcamentaria.query.filter_by(
            cod_estagio=ESTAGIO_PAGAMENTO, num_ano=num_ano, ind_status='A').all():
        orcamentario[documento.cod_orgao] = (
            orcamentario.get(documento.cod_orgao, ZERO)
            + valor_corrente(documento.seq_execucao))

    financeiro: dict = {}
    for pagamento in Pagamento.query.filter_by(ind_status='A').all():
        if pagamento.dat_pagamento.year != num_ano:
            continue
        financeiro[pagamento.cod_orgao] = (
            financeiro.get(pagamento.cod_orgao, ZERO)
            + Decimal(pagamento.val_pagamento))

    linhas = []
    for cod_orgao in sorted(set(orcamentario) | set(financeiro)):
        pago = orcamentario.get(cod_orgao, ZERO).quantize(Decimal("0.01"))
        desembolso = financeiro.get(cod_orgao, ZERO).quantize(Decimal("0.01"))
        diferenca = (pago - desembolso).quantize(Decimal("0.01"))
        linhas.append({
            'cod_orgao': cod_orgao,
            'pago_orcamentario': pago,
            'desembolso_financeiro': desembolso,
            'diferenca': diferenca,
            'direcao': classificar_diferenca(diferenca),
        })
    return linhas
