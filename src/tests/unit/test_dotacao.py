"""Unitários da dotação (spec execucao-orcamentaria R2) — aritmética pura.

⚠️ Imports de `fluxocaixa` TARDIOS (dentro dos testes) — import no topo roda
na coleta, antes de o conftest forçar o DATABASE_URL de teste, e derruba o
isolamento de banco da suíte inteira.
"""
from decimal import Decimal


def _somar():
    from fluxocaixa.services.dotacao_service import somar_eventos

    return somar_eventos


class TestSomarEventos:
    def test_sem_eventos_e_a_inicial(self):
        assert _somar()(Decimal("12000.00"), []) == Decimal("12000.00")

    def test_suplementar_especial_extraordinario_somam(self):
        eventos = [('S', Decimal("100.00")), ('E', Decimal("50.00")),
                   ('X', Decimal("25.00"))]
        assert _somar()(Decimal("1000.00"), eventos) == Decimal("1175.00")

    def test_reducao_subtrai(self):
        eventos = [('S', Decimal("3000.00")), ('R', Decimal("1000.00"))]
        assert _somar()(Decimal("12000.00"), eventos) == Decimal("14000.00")

    def test_quantizacao_em_duas_casas(self):
        assert _somar()(Decimal("0.005"), []) == Decimal("0.00")
        assert _somar()(Decimal("10"), [('S', Decimal("0.1"))]) == Decimal("10.10")
