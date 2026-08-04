"""Rede de caracterização dos relatórios de lançamento (spec cadastros-nucleo R8).

Prova que a F6.1b (valor sempre positivo + tipo 'C'/'D') não muda número
nenhum: a golden versionada tem de bater antes e depois da migração.

Para REGERAR a golden deliberadamente (só quando a mudança de número for
intencional e revisada):

    PYTHONPATH=src REGERAR_GOLDEN=1 pytest src/tests/integration/test_caracterizacao_lancamento.py

O helper (massa, coleta, canonicalização) vive em `src/tests/caracterizacao.py`.
"""
import os

import pytest

from .. import caracterizacao as carac


@pytest.fixture()
def massa(app):
    dados = carac.montar_massa()
    yield dados
    carac.limpar_massa()


def test_golden_dos_relatorios_nao_mudou(massa):
    snapshot = carac.coletar_snapshot()

    if os.getenv("REGERAR_GOLDEN") == "1":
        carac.salvar_golden(snapshot)
        pytest.skip("golden regenerada por REGERAR_GOLDEN=1")

    if not carac.caminho_golden().exists():
        carac.salvar_golden(snapshot)
        pytest.skip("golden inexistente — criada agora; rode de novo para comparar")

    esperado = carac.carregar_golden()
    divergencias = carac.diferencas(esperado, snapshot)
    assert not divergencias, (
        "os números dos relatórios mudaram:\n  "
        + "\n  ".join(divergencias[:40])
        + (f"\n  … e outras {len(divergencias) - 40}" if len(divergencias) > 40 else "")
    )


def test_snapshot_cobre_os_relatorios_e_e_deterministico(massa):
    primeiro = carac.coletar_snapshot()
    segundo = carac.coletar_snapshot()

    for relatorio in carac.RELATORIOS_COBERTOS:
        assert relatorio in primeiro, f"relatório {relatorio} fora do snapshot"
    assert carac.diferencas(primeiro, segundo) == []


def test_massa_e_coerente_e_cobre_as_formas_estruturais(massa):
    """A massa precisa ser COERENTE (sinal e tipo concordam) e ainda assim
    exercitar as formas que os relatórios enxergam.

    A coerência não é detalhe: linha anômala muda de tipo na migração por
    construção, e aí todo relatório que separa receita de despesa POR TIPO
    redistribui entre as colunas. Se a golden carregasse essas linhas, a
    promessa "nada mudou para dado válido" viria com asterisco. A semântica
    das anômalas é fixada pelo BDD `tipo_lancamento_cd.feature`.
    """
    from sqlalchemy import extract

    from fluxocaixa.models import Lancamento
    from fluxocaixa.models.lancamento import TIPO_CREDITO, TIPO_DEBITO
    from fluxocaixa.services.dominio_lancamento import (
        ORIGEM_AUTOMATICO,
        resolver_origem,
    )

    da_ilha = Lancamento.query.filter(
        extract("year", Lancamento.dat_lancamento) == carac.ANO,
        Lancamento.ind_status == 'A',
    ).all()
    cod_automatico = resolver_origem(ORIGEM_AUTOMATICO).cod_origem_lancamento

    assert all(l.val_lancamento > 0 for l in da_ilha), "valor deve ser positivo"
    assert all(l.cod_tipo_lancamento in (TIPO_CREDITO, TIPO_DEBITO)
               for l in da_ilha), "tipo deve ser 'C' ou 'D'"
    assert any(l.cod_tipo_lancamento == TIPO_CREDITO for l in da_ilha), "falta crédito"
    assert any(l.cod_tipo_lancamento == TIPO_DEBITO for l in da_ilha), "falta débito"
    assert any(l.seq_conta is None for l in da_ilha), "falta lançamento sem conta"
    assert any(l.cod_origem_lancamento == cod_automatico
               for l in da_ilha), "falta lançamento de origem Automático"
