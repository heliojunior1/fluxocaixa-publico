"""LDO & Orçamento service - Monitoramento de Metas Fiscais.

Refatorado para usar dados reais da LOA (flc_loa) e suportar
receitas + despesas + comparativo LOA × Realizado.
"""

from ...models import Qualificador
from ...models.categoria_fiscal import BASE_RCL
from ...repositories.lancamento_repository import LancamentoRepository
from ...repositories.loa_repository import LoaRepository
from ..categoria_fiscal_service import (
    categoria_resolvida,
    criar_memo,
    siglas_ativas,
)
from ..meta_fiscal_service import obter_meta_superavit
from .base import get_tipo_lancamento_ids


def get_ldo_orcamento_data(ano: int, tipo_fluxo: str = 'ambos') -> dict:
    """
    Retorna dados para o relatório de LDO & Orçamento.

    Mostra:
    - KPIs totalizadores (Total LOA, Realizado, % Execução, Saldo)
    - Comparativo LOA × Realizado por categoria (gráfico de barras)
    - Distribuição do Orçamento (LOA) por categoria (gráfico pizza)
    - Metas Fiscais (LDO) com status de cumprimento

    Args:
        ano: Ano para análise
        tipo_fluxo: 'receita', 'despesa' ou 'ambos'

    Returns:
        dict com kpis, comparativo, distribuicao_orcamento, metas_fiscais
    """
    # IDs dos tipos
    tipo_ids = get_tipo_lancamento_ids()
    id_entrada = tipo_ids['entrada']
    id_saida = tipo_ids['saida']

    # Inicializar repositories
    lancamento_repo = LancamentoRepository()
    loa_repo = LoaRepository()

    # --- Buscar qualificadores folha ativos ---
    qualificadores_ativos = [
        q for q in Qualificador.query.filter_by(ind_status='A').all()
        if q.is_folha()
    ]

    # Filtrar por tipo_fluxo
    if tipo_fluxo == 'receita':
        qualificadores_filtrados = [q for q in qualificadores_ativos if q.tipo_fluxo == 'receita']
    elif tipo_fluxo == 'despesa':
        qualificadores_filtrados = [q for q in qualificadores_ativos if q.tipo_fluxo == 'despesa']
    else:
        qualificadores_filtrados = qualificadores_ativos

    # --- Buscar dados LOA reais ---
    loa_dict = loa_repo.get_dict_by_year(ano)

    # --- 1. COMPARATIVO LOA × REALIZADO ---
    comparativo = []
    total_loa = 0.0
    total_realizado = 0.0

    for qual in qualificadores_filtrados:
        # Valor LOA cadastrado
        valor_loa = loa_dict.get(qual.seq_qualificador, 0.0)

        # Valor Realizado (soma dos lançamentos)
        cod_tipo = id_entrada if qual.tipo_fluxo == 'receita' else id_saida
        valor_realizado = float(lancamento_repo.get_sum_by_qualificadores_and_year(
            qualificadores_ids=[qual.seq_qualificador],
            cod_tipo=cod_tipo,
            ano=ano
        ))
        valor_realizado = abs(valor_realizado)

        # Percentual de execução
        perc_execucao = (valor_realizado / valor_loa * 100) if valor_loa > 0 else 0.0

        if valor_loa > 0 or valor_realizado > 0:
            comparativo.append({
                'categoria': qual.dsc_qualificador,
                'qualificador_id': qual.seq_qualificador,
                'valor_loa': round(valor_loa, 2),
                'valor_realizado': round(valor_realizado, 2),
                'percentual_execucao': round(perc_execucao, 2),
                'tipo': qual.tipo_fluxo
            })
            total_loa += valor_loa
            total_realizado += valor_realizado

    # Ordenar por valor LOA decrescente
    comparativo.sort(key=lambda x: x['valor_loa'], reverse=True)

    # --- 2. KPIs ---
    perc_execucao_total = (total_realizado / total_loa * 100) if total_loa > 0 else 0.0
    saldo_loa = total_loa - total_realizado

    kpis = {
        'total_loa': round(total_loa, 2),
        'total_realizado': round(total_realizado, 2),
        'percentual_execucao': round(perc_execucao_total, 2),
        'saldo_loa': round(saldo_loa, 2),
    }

    # --- 3. DISTRIBUIÇÃO DO ORÇAMENTO (LOA) - gráfico pizza ---
    distribuicao = []
    total_loa_dist = 0.0

    for qual in qualificadores_filtrados:
        valor_loa = loa_dict.get(qual.seq_qualificador, 0.0)
        if valor_loa > 0:
            distribuicao.append({
                'categoria': qual.dsc_qualificador,
                'valor': valor_loa,
                'tipo': qual.tipo_fluxo
            })
            total_loa_dist += valor_loa

    # Calcular percentuais
    for item in distribuicao:
        item['percentual'] = round((item['valor'] / total_loa_dist * 100) if total_loa_dist > 0 else 0, 2)
        item['valor'] = round(item['valor'], 2)

    # Ordenar por valor decrescente
    distribuicao.sort(key=lambda x: x['valor'], reverse=True)

    # --- 4. METAS FISCAIS (LDO) ---
    metas_fiscais = _calcular_metas_fiscais(
        ano, lancamento_repo, loa_repo, loa_dict,
        qualificadores_ativos, id_entrada, id_saida
    )

    return {
        'kpis': kpis,
        'comparativo': comparativo,
        'distribuicao_orcamento': distribuicao,
        'metas_fiscais': metas_fiscais,
    }


def _calcular_metas_fiscais(
    ano: int,
    lancamento_repo: LancamentoRepository,
    loa_repo: LoaRepository,
    loa_dict: dict[int, float],
    qualificadores_ativos: list,
    id_entrada: int,
    id_saida: int
) -> list[dict]:
    """Calcula metas fiscais usando dados reais de LOA e lançamentos."""

    quals_receita = [q for q in qualificadores_ativos if q.tipo_fluxo == 'receita']
    quals_despesa = [q for q in qualificadores_ativos if q.tipo_fluxo == 'despesa']

    # Receita Corrente Líquida (RCL) = Total receitas realizadas
    rcl = float(lancamento_repo.get_sum_by_qualificadores_and_year(
        qualificadores_ids=[q.seq_qualificador for q in quals_receita],
        cod_tipo=id_entrada,
        ano=ano
    ))

    # Total Despesas Realizadas
    total_despesas_ano = float(lancamento_repo.get_sum_by_qualificadores_and_year(
        qualificadores_ids=[q.seq_qualificador for q in quals_despesa],
        cod_tipo=id_saida,
        ano=ano
    ))
    total_despesas_ano = abs(total_despesas_ano)

    # Superávit Primário
    superavit_primario = rcl - total_despesas_ano

    # --- Metas por CATEGORIA FISCAL (F6.5 — R17/R18) ---
    # ⚠️ Aqui morava o casamento por substring na descrição:
    #     if 'pessoal' in qual.dsc_qualificador.lower() ...
    # Ele não enxergava a hierarquia: um bloco "EDUCAÇÃO" casaria a palavra mas
    # não é folha (a lista só tem folhas), e as folhas sob ele não casam — a
    # meta dava R$ 0,00 e exibia "ATENÇÃO", indistinguível de descumprimento
    # real. Agora a pertinência vem da categoria RESOLVIDA (própria ou herdada
    # do ancestral mais próximo).
    memo = criar_memo()
    por_categoria: dict[int, float] = {}
    for qual in quals_despesa:
        categoria = categoria_resolvida(qual, memo)
        if categoria is None:
            continue  # sem marcação não entra em meta alguma
        valor = float(lancamento_repo.get_sum_by_qualificadores_and_year(
            qualificadores_ids=[qual.seq_qualificador],
            cod_tipo=id_saida,
            ano=ano
        ))
        chave = categoria.seq_categoria_fiscal
        por_categoria[chave] = por_categoria.get(chave, 0.0) + abs(valor)

    metas_fiscais = []

    # Meta: Superávit Primário — a meta vem do que a entidade INFORMOU para o
    # ano (R19). Sem meta informada não se inventa uma: mostra-se o apurado sem
    # veredito, em vez do antigo `loa_receita_total * 0.02`.
    meta_superavit = obter_meta_superavit(ano)
    entrada_superavit = {
        'nome': 'Superávit Primário',
        'realizado': format_currency_short(superavit_primario),
        'val_realizado': superavit_primario,
        'val_meta': float(meta_superavit) if meta_superavit is not None else None,
    }
    if meta_superavit is None:
        entrada_superavit.update({
            'meta': 'não informada',
            'percentual': 0,
            'status': 'SEM META',
        })
    else:
        alvo = float(meta_superavit)
        entrada_superavit.update({
            'meta': f'≥ {format_currency_short(alvo)}',
            'percentual': round((superavit_primario / alvo * 100) if alvo > 0 else 0, 1),
            'status': 'ATINGIDO' if superavit_primario >= alvo else 'CRÍTICO',
        })
    metas_fiscais.append(entrada_superavit)

    # ⚠️ A meta "Dívida Consolidada / RCL" saiu daqui (R19). Era
    # `divida_consolidada_rcl = 45.0` fixo, exibido como "45.0% — DENTRO DA
    # META": uma afirmação falsa sobre finanças públicas. Não há fonte no
    # sistema para o estoque da dívida, e parametrizar um número que ninguém
    # consegue apurar só moveria a invenção para uma tela de configuração.

    # Demais metas: uma por categoria ativa, com o denominador e os limiares da
    # PRÓPRIA categoria (R18) — pessoal mede sobre a RCL, saúde e educação
    # sobre a despesa total. Sem isso, essa diferença voltaria como um `if`
    # pela sigla, que é a heurística de novo.
    for categoria in siglas_ativas():
        base = rcl if categoria.cod_base_calculo == BASE_RCL else total_despesas_ano
        realizado = por_categoria.get(categoria.seq_categoria_fiscal, 0.0)
        percentual = (realizado / base * 100) if base > 0 else 0
        metas_fiscais.append({
            'nome': categoria.dsc_categoria,
            # A base ia embutida no rótulo antigo ("Despesa com Pessoal / RCL").
            # Agora ela é a coluna `cod_base_calculo`, e vai como campo próprio
            # para a tela não perder de vista o denominador da meta.
            'base': 'RCL' if categoria.cod_base_calculo == BASE_RCL
                    else 'Despesa total',
            'meta': categoria.rotulo_meta(),
            'realizado': f'{round(percentual, 1)}%',
            'percentual': round(percentual, 1),
            'val_realizado': realizado,
            'status': categoria.status_para(percentual),
        })

    return metas_fiscais


def format_currency_short(value: float) -> str:
    """Formata valor em formato abreviado (M para milhões)."""
    abs_value = abs(value)
    if abs_value >= 1_000_000_000:
        return f'R$ {abs_value / 1_000_000_000:.2f} B'
    elif abs_value >= 1_000_000:
        return f'R$ {abs_value / 1_000_000:.1f} M'
    elif abs_value >= 1_000:
        return f'R$ {abs_value / 1_000:.1f} K'
    else:
        return f'R$ {abs_value:.2f}'
