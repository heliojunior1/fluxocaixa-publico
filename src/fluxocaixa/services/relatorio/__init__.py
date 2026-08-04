"""Relatorio services - modular organization.

This package contains modularized services for different types of reports,
replacing the monolithic relatorio_service.py.
"""
from .comparativo_service import get_analise_comparativa_data
from .controle_despesa_service import get_controle_despesa_data
from .dfc_service import get_dfc_data, get_dfc_eventos
from .indicadores_service import get_indicadores_data
from .kpis_service import get_kpis_data
from .ldo_orcamento_service import get_ldo_orcamento_data
from .previsao_receita_service import get_previsao_receita_data
from .resumo_service import get_resumo_data
from .saldos_service import get_saldos_diarios_data
from .years_service import get_available_years

__all__ = [
    'get_analise_comparativa_data',
    'get_available_years',
    'get_controle_despesa_data',
    'get_dfc_data',
    'get_dfc_eventos',
    'get_indicadores_data',
    'get_kpis_data',
    'get_ldo_orcamento_data',
    'get_previsao_receita_data',
    'get_resumo_data',
    'get_saldos_diarios_data',
]
