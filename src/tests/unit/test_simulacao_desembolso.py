"""Unitários da simulação de disponibilidade (spec desembolso R9) — puros.

⚠️ Imports de `fluxocaixa` TARDIOS (dentro dos testes) — ver aviso do conftest.
"""
from datetime import date


def _posicionar():
    from fluxocaixa.services.simulacao_desembolso_service import _mes_posicionado

    return _mes_posicionado


class TestMesPosicionado:
    MESES = [3, 4, 5]

    def test_dentro_do_horizonte(self):
        assert _posicionar()(date(2040, 4, 10), 2040, self.MESES) == 4

    def test_anterior_clampa_no_primeiro_mes(self):
        # pendente vencido desconta integral no primeiro período
        assert _posicionar()(date(2040, 1, 10), 2040, self.MESES) == 3

    def test_ano_anterior_clampa_no_primeiro_mes(self):
        assert _posicionar()(date(2038, 12, 1), 2040, self.MESES) == 3

    def test_posterior_fica_fora(self):
        assert _posicionar()(date(2040, 7, 1), 2040, self.MESES) is None

    def test_ano_posterior_fica_fora(self):
        assert _posicionar()(date(2041, 3, 1), 2040, self.MESES) is None
