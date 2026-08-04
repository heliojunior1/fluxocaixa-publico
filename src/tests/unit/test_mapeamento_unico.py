"""Unitários do mapeamento sem dimensão receita/despesa (automacao R6).

Cobre o detector de colisão da migração 0037 (função PURA — é ele que decide
entre fundir e abortar) e a unicidade nova no serviço. Import tardio de
`fluxocaixa`; a migração é carregada por caminho (alembic/versions não é
pacote).
"""
import importlib.util
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[3]


def _migracao():
    caminho = RAIZ / "alembic" / "versions" / "0037_mapeamento_sem_tipo.py"
    spec = importlib.util.spec_from_file_location("migracao_0037", caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_colisao_detecta_qualificador_nos_dois_lados():
    m = _migracao()
    assert m.colisoes_da_fusao({10: {1, 2}, 20: {2, 3}}) == [2]


def test_sem_colisao_quando_qualificadores_disjuntos():
    m = _migracao()
    assert m.colisoes_da_fusao({10: {1, 2}, 20: {3, 4}}) == []


def test_colisao_multipla_ordenada():
    m = _migracao()
    assert m.colisoes_da_fusao({10: {5, 1, 3}, 20: {3, 5, 9}}) == [3, 5]


def test_mapeamento_sozinho_nunca_colide():
    m = _migracao()
    assert m.colisoes_da_fusao({10: {1, 2, 3}}) == []


@pytest.fixture()
def massa_unicidade(app):
    from fluxocaixa.models import Mapeamento, Qualificador
    from fluxocaixa.models.base import db

    from tests.features.conftest_extracao import garantir_sistema_origem
    from tests.features.steps.conftest_regra import (
        garantir_termos_padrao,
        sistema_por_sigla,
    )

    db.session.rollback()
    garantir_sistema_origem("SIS_UNIT_Q")
    garantir_termos_padrao()
    sistema = sistema_por_sigla("SIS_UNIT_Q")
    Mapeamento.query.filter_by(
        seq_sistema_origem=sistema.seq_sistema_origem).delete()
    q = Qualificador.query.filter_by(num_qualificador="1.77.1").first()
    if q is None:
        q = Qualificador(num_qualificador="1.77.1",
                         dsc_qualificador="Rubrica Unicidade", ind_status='A')
        db.session.add(q)
    db.session.commit()
    yield sistema, q
    db.session.rollback()
    Mapeamento.query.filter_by(
        seq_sistema_origem=sistema.seq_sistema_origem).delete()
    db.session.commit()


def test_unicidade_por_ano_e_sistema(massa_unicidade):
    from fluxocaixa.services.mapeamento_service import criar_mapeamento
    from fluxocaixa.services.validacao import RegraNegocioError

    sistema, q = massa_unicidade
    item = [{"seq_qualificador": q.seq_qualificador,
             "txt_regra": "Unidade Gestora = '999001'"}]
    criar_mapeamento(2077, sistema.seq_sistema_origem, "Único 2077", item)

    with pytest.raises(RegraNegocioError) as exc:
        criar_mapeamento(2077, sistema.seq_sistema_origem, "Duplicado", item)
    assert "reúna os itens" in str(exc.value)

    # outro ano coexiste
    criar_mapeamento(2078, sistema.seq_sistema_origem, "Outro ano", item)
