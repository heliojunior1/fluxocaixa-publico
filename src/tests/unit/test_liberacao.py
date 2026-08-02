"""Unitários da liberação (spec desembolso R4) — funções puras.

⚠️ Imports de `fluxocaixa` TARDIOS (dentro dos testes) — import no topo roda
na coleta, antes de o conftest forçar o DATABASE_URL de teste, e derruba o
isolamento de banco da suíte inteira.
"""
from datetime import date


def _semana():
    from fluxocaixa.services.liberacao_service import semana_util_de

    return semana_util_de


class TestSemanaUtil:
    def test_meio_da_semana(self):
        # 2038-06-16 é uma quarta-feira
        dias = _semana()(date(2038, 6, 16))
        assert dias[0] == date(2038, 6, 14)   # segunda
        assert dias[-1] == date(2038, 6, 18)  # sexta
        assert len(dias) == 5

    def test_segunda_e_a_propria(self):
        dias = _semana()(date(2038, 6, 14))
        assert dias[0] == date(2038, 6, 14)

    def test_domingo_cai_na_semana_que_comeca_no_dia_seguinte_nao(self):
        # domingo pertence à semana que COMEÇOU na segunda anterior (ISO)
        dias = _semana()(date(2038, 6, 20))
        assert dias[0] == date(2038, 6, 14)

    def test_virada_de_mes(self):
        # 2038-07-01 é quinta — a segunda da semana é 28/06
        dias = _semana()(date(2038, 7, 1))
        assert dias[0] == date(2038, 6, 28)
        assert dias[-1] == date(2038, 7, 2)


class TestNaoGerenciavel:
    def test_discricionaria_nao_e(self):
        from fluxocaixa.models.liberacao import NATUREZA_DISCRICIONARIA, Liberacao

        liberacao = Liberacao(cod_natureza_obrigacao=NATUREZA_DISCRICIONARIA)
        assert liberacao.nao_gerenciavel is False

    def test_constitucional_e(self):
        from fluxocaixa.models.liberacao import NATUREZA_CONSTITUCIONAL, Liberacao

        liberacao = Liberacao(cod_natureza_obrigacao=NATUREZA_CONSTITUCIONAL)
        assert liberacao.nao_gerenciavel is True
