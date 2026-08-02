"""Unitários da execução orçamentária (spec execucao-orcamentaria R4) —
`validar_cadeia`, função pura.

⚠️ Imports de `fluxocaixa` TARDIOS (dentro dos testes) — import no topo roda
na coleta, antes de o conftest forçar o DATABASE_URL de teste, e derruba o
isolamento de banco da suíte inteira.
"""
import pytest


def _validar():
    from fluxocaixa.services.execucao_orcamentaria_service import validar_cadeia

    return validar_cadeia


def _erro():
    from fluxocaixa.services.validacao import RegraNegocioError

    return RegraNegocioError


class TestValidarCadeia:
    def test_empenho_sem_pai_ok(self):
        _validar()('E', None)

    def test_empenho_com_pai_recusado(self):
        with pytest.raises(_erro()):
            _validar()('E', 'E')

    def test_liquidacao_sobre_empenho_ok(self):
        _validar()('L', 'E')

    def test_pagamento_sobre_liquidacao_ok(self):
        _validar()('P', 'L')

    def test_pagamento_sobre_empenho_recusado(self):
        with pytest.raises(_erro()):
            _validar()('P', 'E')

    def test_liquidacao_sem_pai_recusada(self):
        with pytest.raises(_erro()):
            _validar()('L', None)

    def test_estagio_invalido(self):
        with pytest.raises(_erro()):
            _validar()('X', None)
