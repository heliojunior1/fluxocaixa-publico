from fastapi.templating import Jinja2Templates
import os

from ..utils import format_currency

from ..config import BASE_DIR, modo_demo
from .safe_router import SafeAPIRouter, handle_exceptions

# Shared router and templates object used by the route modules
router = SafeAPIRouter()
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, 'templates'))
templates.env.filters['format_currency'] = format_currency

# Global, e não contexto por rota: o aviso de demo aparece no login (rota
# pública) e no layout base (todas as demais) — passar pela mão em cada
# TemplateResponse seria esquecido na primeira rota nova.
templates.env.globals['modo_demo'] = modo_demo


def _tem_permissao(request, cod_permissao: str) -> bool:
    """Helper Jinja: esconde ações sem permissão (conveniência de UI —
    a proteção efetiva é a dependency `requer` na rota)."""
    from ..auth.permissoes import permissoes_do_request

    try:
        return cod_permissao in permissoes_do_request(request)
    except Exception:
        return False


templates.env.globals['tem_permissao'] = _tem_permissao


def _fundos_pendentes(request) -> int:
    """Contador de fundos pendentes de revisão — só para quem aprova.

    Memoizado em request.state; 0 sem FC_APROVAR_FUNDO (não vaza contagem)."""
    cache = getattr(request.state, 'fundos_pendentes', None)
    if cache is not None:
        return cache
    total = 0
    if _tem_permissao(request, 'FC_APROVAR_FUNDO'):
        from ..services.fundo_service import contar_pendentes
        total = contar_pendentes()
    request.state.fundos_pendentes = total
    return total


templates.env.globals['fundos_pendentes'] = _fundos_pendentes

# Import routes so they register themselves with the router
from . import base, pagamentos, mapeamentos, processamento, termos_regra, relatorios, alertas, qualificadores, saldos_bancarios, simulador_cenarios, loa, formulas, fundos, contas_bancarias, importacao_lote, importacao, extracao  # noqa: E402,F401

__all__ = ['router', 'templates', 'handle_exceptions']
