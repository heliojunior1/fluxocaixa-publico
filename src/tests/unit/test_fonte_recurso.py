"""Unitários do catálogo de fontes de recurso (spec fonte-recurso R1).

Funções puras: decomposição/derivação do código e grupo da disponibilidade.

⚠️ Imports de `fluxocaixa` são TARDIOS (dentro dos testes): import no topo
roda na COLETA, antes de a fixture `client` forçar DATABASE_URL de teste —
e derruba o isolamento de banco da suíte inteira (aviso do conftest).
"""
import pytest


def _mod():
    from fluxocaixa.models import fonte_recurso

    return fonte_recurso


def _parsear():
    from fluxocaixa.services.fonte_recurso_service import parsear_codigo

    return parsear_codigo


def _erro():
    from fluxocaixa.services.validacao import RegraNegocioError

    return RegraNegocioError


class TestParsearCodigo:
    def test_codigo_completo_sem_detalhamento(self):
        assert _parsear()("1.500") == ("1", "500", None)

    def test_codigo_completo_com_detalhamento(self):
        assert _parsear()("1.500.0001") == ("1", "500", "0001")

    def test_forma_curta_assume_exercicio_corrente(self):
        # é como a fonte chega nas cargas do sistema de origem (3 dígitos)
        assert _parsear()("761") == ("1", "761", None)

    def test_exercicios_anteriores_e_condicionados(self):
        assert _parsear()("2.500") == ("2", "500", None)
        assert _parsear()("9.700") == ("9", "700", None)

    def test_identificador_invalido_rejeitado(self):
        with pytest.raises(_erro()):
            _parsear()("5.500")

    def test_vazio_rejeitado(self):
        with pytest.raises(_erro()):
            _parsear()("")

    def test_lixo_rejeitado(self):
        with pytest.raises(_erro()):
            _parsear()("abcd")


class TestResolverFonteDeAtributos:
    """Caminhos que retornam None sem tocar o banco (F9.2 D2)."""

    def _resolver(self):
        from fluxocaixa.services.fonte_recurso_service import (
            resolver_fonte_de_atributos,
        )

        return resolver_fonte_de_atributos

    def test_atributos_nulos(self):
        assert self._resolver()(None, 2026) is None

    def test_atributos_vazios(self):
        assert self._resolver()({}, 2026) is None

    def test_sem_chave_de_fonte(self):
        assert self._resolver()({"natureza": "11120000"}, 2026) is None

    def test_valor_nao_parseavel_vira_none(self):
        # lixo não vira fonte nova — e não bloqueia a classificação
        assert self._resolver()({"fonte_recurso": "XYZ"}, 2026) is None

    def test_valor_em_branco_ignorado(self):
        assert self._resolver()({"fonte_recurso": "  "}, 2026) is None


class TestCodigoCompleto:
    def test_derivado_sem_detalhamento(self):
        m = _mod()
        fonte = m.FonteRecurso(cod_identificador_exercicio="1", cod_fonte_stn="500")
        assert fonte.codigo_completo == "1.500"

    def test_derivado_com_detalhamento(self):
        m = _mod()
        fonte = m.FonteRecurso(
            cod_identificador_exercicio="1", cod_fonte_stn="500",
            cod_detalhamento="0001")
        assert fonte.codigo_completo == "1.500.0001"


class TestGrupo:
    def test_livre(self):
        m = _mod()
        fonte = m.FonteRecurso(cod_identificador_exercicio="1", cod_fonte_stn="500",
                               ind_vinculada=m.IND_LIVRE)
        assert fonte.grupo == m.GRUPO_LIVRE

    def test_vinculada(self):
        m = _mod()
        fonte = m.FonteRecurso(cod_identificador_exercicio="1", cod_fonte_stn="761",
                               ind_vinculada=m.IND_VINCULADA)
        assert fonte.grupo == m.GRUPO_VINCULADO

    def test_vinculacao_nao_segue_prefixo(self):
        # fonte de faixa "livre" marcada como vinculada conta como vinculada —
        # ind_vinculada é explícita, nunca derivada do código
        m = _mod()
        fonte = m.FonteRecurso(cod_identificador_exercicio="1", cod_fonte_stn="509",
                               ind_vinculada=m.IND_VINCULADA)
        assert fonte.grupo == m.GRUPO_VINCULADO
