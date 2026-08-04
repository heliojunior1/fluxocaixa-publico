"""Unitários do painel analítico (spec desembolso R26) — evolução mensal.

⚠️ Imports de `fluxocaixa` TARDIOS (dentro dos testes) — import no topo roda
na coleta, antes de o conftest forçar o DATABASE_URL de teste, e derruba o
isolamento de banco da suíte inteira.
"""
from datetime import date
from decimal import Decimal


def _evolucao():
    from fluxocaixa.services.relatorio.analitico_desembolso_service import (
        evolucao_mensal,
    )

    return evolucao_mensal


class TestEvolucaoMensal:
    def test_sem_eventos_e_zero_o_ano_inteiro(self):
        resultado = _evolucao()([], [], 2059)
        assert all(resultado[m] == Decimal("0.00") for m in range(1, 13))

    def test_confirmacao_entra_no_mes_e_persiste(self):
        resultado = _evolucao()([(date(2059, 3, 10), Decimal("1000.00"))], [], 2059)
        assert resultado[2] == Decimal("0.00")
        assert resultado[3] == Decimal("1000.00")
        assert resultado[12] == Decimal("1000.00")

    def test_apropriacao_abate_e_estorno_devolve(self):
        confirmacoes = [(date(2059, 3, 10), Decimal("1000.00"))]
        eventos = [(date(2059, 4, 15), 'A', Decimal("300.00")),
                   (date(2059, 6, 15), 'E', Decimal("100.00"))]
        resultado = _evolucao()(confirmacoes, eventos, 2059)
        assert resultado[3] == Decimal("1000.00")
        assert resultado[4] == Decimal("700.00")
        assert resultado[5] == Decimal("700.00")
        assert resultado[6] == Decimal("800.00")

    def test_dezembro_inclui_o_ano_inteiro(self):
        resultado = _evolucao()([(date(2059, 12, 31), Decimal("50.00"))], [], 2059)
        assert resultado[11] == Decimal("0.00")
        assert resultado[12] == Decimal("50.00")
