"""Resumo (Cash Flow Summary) service."""
from datetime import date, timedelta

from ...repositories.lancamento_repository import LancamentoRepository
from ...repositories.saldo_conta_repository import SaldoContaRepository
from ...utils.constants import MONTH_NAME_PT
from .dfc_projecao import resolver_projecao
from .base import get_tipo_lancamento_ids


def get_resumo_data(
    ano_selecionado: int,
    meses_selecionados: list[int],
    estrategia: str,
    cenario_selecionado_id: int | None
) -> dict:
    """Get cash flow summary data for selected year and months.
    
    Args:
        ano_selecionado: Year to analyze
        meses_selecionados: List of months (1-12)
        estrategia: 'realizado' or 'projetado'
        cenario_selecionado_id: ID of scenario if strategy is 'projetado'
    
    Returns:
        Dictionary with summary data including totals and cash flow chart data
    """
    meses_nomes = MONTH_NAME_PT
    tipo_ids = get_tipo_lancamento_ids()
    id_entrada = tipo_ids['entrada']
    id_saida = tipo_ids['saida']
    
    # Initialize repositories
    lancamento_repo = LancamentoRepository()
    saldo_repo = SaldoContaRepository()

    # Calculate period totals using repository
    total_entradas_periodo = float(lancamento_repo.get_total_by_tipo_and_period(
        cod_tipo=id_entrada,
        ano=ano_selecionado,
        meses=meses_selecionados
    ))
    
    total_saidas_lanc = float(lancamento_repo.get_total_by_tipo_and_period(
        cod_tipo=id_saida,
        ano=ano_selecionado,
        meses=meses_selecionados
    ))
    total_saidas_periodo = abs(total_saidas_lanc)
    disponibilidade_periodo = total_entradas_periodo - total_saidas_periodo
    
    # Get initial bank balance from day before period start
    # Determine first day of period
    primeiro_mes = min(meses_selecionados)
    data_inicio_periodo = date(ano_selecionado, primeiro_mes, 1)
    data_saldo_inicial = data_inicio_periodo - timedelta(days=1)  # Day before period
    
    # `is None` = ausência de registro → carry; zero registrado é respeitado (R22)
    saldo_inicial_conta = saldo_repo.get_saldo_total_by_date(data_saldo_inicial)
    if saldo_inicial_conta is None:
        saldo_inicial_conta = saldo_repo.get_latest_saldo_total_before_date(data_saldo_inicial)
    
    # Calculate final bank balance
    saldo_final_conta = saldo_inicial_conta + total_entradas_periodo - total_saidas_periodo

    # Projeção pela PORTA ÚNICA (previsao RN15): última versão publicada →
    # ao vivo com aviso. Antes executava o cenário ao vivo a cada abertura e
    # ignorava a versão publicada (o número mudava sem ninguém publicar).
    simulacao_resultado = None
    projecao_origem = None
    projetado_por_mes: dict = {}
    if estrategia == "projetado" and cenario_selecionado_id:
        mapa, projecao_origem = resolver_projecao(cenario_selecionado_id, ano_selecionado)
        for (_seq, tipo, mes), valor in mapa.items():
            if mes is None:
                continue
            chave = (tipo, mes)
            projetado_por_mes[chave] = projetado_por_mes.get(chave, 0.0) + abs(float(valor))
        simulacao_resultado = projetado_por_mes

    # Build cash flow data month by month
    cash_flow_data = {
        "labels": [],
        "saldo_inicial_mensal": [],
        "receitas": [],
        "despesas": [],
        "saldos": [],
        "saldo_final": [],
        "meses_projetados": [],
    }
    saldo_acumulado_banco = saldo_inicial_conta  # Start with bank initial balance
    saldo_acumulado = 0
    hoje = date.today()
    total_entradas_recalc = 0
    total_saidas_recalc = 0

    for mes in sorted(meses_selecionados):
        projetar_mes = (
            estrategia == "projetado"
            and simulacao_resultado is not None
            and (
                ano_selecionado > hoje.year
                or (ano_selecionado == hoje.year and mes >= hoje.month)
            )
        )
        receitas_mes = 0
        despesas_mes = 0
        
        if projetar_mes:
            receitas_mes = projetado_por_mes.get(('C', mes), 0.0)
            despesas_mes = projetado_por_mes.get(('D', mes), 0.0)
        else:
            # Use actual data from repository
            receitas_mes = float(lancamento_repo.get_monthly_summary(
                ano=ano_selecionado,
                mes=mes,
                cod_tipo=id_entrada
            ))
            
            despesas_lanc_mes = float(lancamento_repo.get_monthly_summary(
                ano=ano_selecionado,
                mes=mes,
                cod_tipo=id_saida
            ))
            despesas_mes = abs(despesas_lanc_mes or 0)
        
        cash_flow_data["labels"].append(meses_nomes[mes][:3])
        cash_flow_data["saldo_inicial_mensal"].append(saldo_acumulado_banco)
        cash_flow_data["receitas"].append(float(receitas_mes))
        cash_flow_data["despesas"].append(float(despesas_mes))
        cash_flow_data["meses_projetados"].append(projetar_mes)
        total_entradas_recalc += float(receitas_mes)
        total_saidas_recalc += float(despesas_mes)
        saldo_mes = float(receitas_mes) - float(despesas_mes)
        saldo_acumulado += saldo_mes
        saldo_acumulado_banco += saldo_mes  # Update bank balance
        cash_flow_data["saldos"].append(saldo_mes)
        cash_flow_data["saldo_final"].append(saldo_acumulado_banco)

    if estrategia == "projetado" and simulacao_resultado is not None:
        total_entradas_periodo = total_entradas_recalc
        total_saidas_periodo = total_saidas_recalc
        disponibilidade_periodo = total_entradas_periodo - total_saidas_periodo
        saldo_final_conta = saldo_inicial_conta + total_entradas_periodo - total_saidas_periodo
        
    return {
        "saldo_inicial_conta": saldo_inicial_conta,
        "total_entradas_periodo": total_entradas_periodo,
        "total_saidas_periodo": total_saidas_periodo,
        "disponibilidade_periodo": disponibilidade_periodo,
        "saldo_final_conta": saldo_final_conta,
        "cash_flow_data": cash_flow_data,
        "meses_nomes": meses_nomes,
        "projecao_origem": projecao_origem,
    }
