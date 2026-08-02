"""Unitários do funil (spec execucao-orcamentaria R9) — direção da diferença.

⚠️ Imports de `fluxocaixa` TARDIOS (dentro dos testes) — import no topo roda
na coleta, antes de o conftest forçar o DATABASE_URL de teste, e derruba o
isolamento de banco da suíte inteira.
"""
from decimal import Decimal


def _classificar():
    from fluxocaixa.services.funil_service import classificar_diferenca

    return classificar_diferenca


class TestClassificarDiferenca:
    def test_positiva_e_orcamento_sem_desembolso(self):
        assert _classificar()(Decimal("100.00")) == \
            "pago no orçamento sem desembolso registrado"

    def test_negativa_e_desembolso_sem_execucao(self):
        assert _classificar()(Decimal("-150.00")) == \
            "desembolso sem execução importada"

    def test_zero_e_conciliado(self):
        assert _classificar()(Decimal("0.00")) == "conciliado"
