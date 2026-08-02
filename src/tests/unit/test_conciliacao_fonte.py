"""Unitários da conciliação por fonte (spec fonte-recurso R12) — situação.

⚠️ Imports de `fluxocaixa` TARDIOS (dentro dos testes) — import no topo roda
na coleta, antes de o conftest forçar o DATABASE_URL de teste, e derruba o
isolamento de banco da suíte inteira.
"""
from decimal import Decimal


def _classificar():
    from fluxocaixa.services.conciliacao_fonte_service import classificar_situacao

    return classificar_situacao


class TestClassificarSituacao:
    def test_sem_contabil_e_neutro(self):
        assert _classificar()(Decimal("800.00"), None) == "SEM_CONTABIL"

    def test_bate_e_conciliada(self):
        assert _classificar()(Decimal("800.00"), Decimal("800.00")) == "CONCILIADA"

    def test_difere_e_a_explicar(self):
        assert _classificar()(Decimal("800.00"), Decimal("500.00")) == "A_EXPLICAR"

    def test_sem_operacional_com_contabil_zero_concilia(self):
        assert _classificar()(None, Decimal("0.00")) == "CONCILIADA"

    def test_sem_operacional_com_contabil_positiva_e_a_explicar(self):
        assert _classificar()(None, Decimal("100.00")) == "A_EXPLICAR"
