"""Steps BDD — preview da regra sobre a staging (spec automacao-lancamentos R8).

O recorte é (sistema de origem, ano) — o mesmo do mapeamento —, não uma fonte.
"""
from datetime import date
from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from ..conftest_extracao import (
    criar_fonte_fake,
    fonte_por_nome,
    garantir_conector_fake,
)
from .conftest_regra import garantir_termos_padrao, sistema_por_sigla

scenarios("../automacao-lancamentos/preview_regra.feature")

# Linhas fictícias: nada de UG/natureza reais (repo público).
LINHAS = [
    {"natureza": "11120000", "ug": "999001", "valor": "100.00"},
    {"natureza": "11120001", "ug": "999002", "valor": "200.00"},
    {"natureza": "22220000", "ug": "999001", "valor": "300.00"},
    {"natureza": "33330000", "ug": "999999", "valor": "50.00"},
]
LINHA_QUE_CASA = {"natureza": "11129999", "ug": "999001", "valor": "10.00"}


@pytest.fixture()
def contexto():
    return {}


@pytest.fixture(autouse=True)
def _staging_limpa(app):
    """Este módulo conta linhas: parte de uma staging vazia."""
    from fluxocaixa.models import EtlStaging
    from fluxocaixa.models.base import db

    db.session.rollback()
    db.session.query(EtlStaging).delete()
    db.session.commit()


def _semear(sigla, nom_fonte, linhas, ano=2026):
    """Cria (se preciso) uma fonte do sistema e deposita linhas na staging."""
    from fluxocaixa.models import EtlStaging, ExecucaoExtracao
    from fluxocaixa.models.base import db

    garantir_conector_fake()
    sistema = sistema_por_sigla(sigla)

    fonte = fonte_por_nome(nom_fonte)
    if fonte is None:
        fonte = criar_fonte_fake(nom_fonte, sigla_sistema=sigla)

    execucao = ExecucaoExtracao(
        seq_fonte_extracao=fonte.seq_fonte_extracao,
        dat_inicio_execucao=date(ano, 7, 10),
        cod_disparo="MANUAL",
        cod_status="SUCESSO",
        dat_janela_inicio=date(ano, 7, 10),
        dat_janela_fim=date(ano, 7, 10),
    )
    db.session.add(execucao)
    db.session.flush()

    for linha in linhas:
        db.session.add(EtlStaging(
            seq_fonte_extracao=fonte.seq_fonte_extracao,
            seq_execucao_extracao=execucao.seq_execucao_extracao,
            num_ano_exercicio=ano,
            dat_referencia=date(ano, 7, 10),
            val_referencia=Decimal(linha["valor"]),
            json_atributos=dict(linha),
            ind_status_processamento='0',
        ))
    db.session.commit()
    return sistema, fonte


# --------------------------------------------------------------------------
# Dado
# --------------------------------------------------------------------------

@given("que estou autenticado como administrador")
def autenticado_admin(app, _admin_pronto):
    from fluxocaixa.auth.contexto import definir_usuario_corrente

    definir_usuario_corrente(777)


@given("os termos de regra padrão cadastrados")
def termos_padrao(app):
    garantir_termos_padrao()


@given(parsers.parse('o sistema de origem "{sigla}" com uma fonte de lançamento '
                     'com linhas na staging'))
def staging_populada(app, contexto, sigla):
    _semear(sigla, "Fonte Preview", LINHAS)


@given(parsers.parse('uma segunda fonte de lançamento de "{sigla}" com 1 linha que casa'))
def segunda_fonte(app, sigla):
    _semear(sigla, "Fonte Preview 2", [LINHA_QUE_CASA])


@given(parsers.parse('uma fonte de lançamento do sistema "{sigla}" com 1 linha que casa'))
def fonte_outro_sistema(app, sigla):
    from ..conftest_extracao import garantir_sistema_origem

    garantir_sistema_origem(sigla)
    _semear(sigla, f"Fonte {sigla}", [LINHA_QUE_CASA])


@given(parsers.parse('uma fonte de lançamento de "{sigla}" com 1 linha que casa '
                     'no ano {ano:d}'))
def fonte_outro_ano(app, sigla, ano):
    _semear(sigla, f"Fonte Preview {ano}", [LINHA_QUE_CASA], ano=ano)


# --------------------------------------------------------------------------
# Quando
# --------------------------------------------------------------------------

@when(parsers.parse('peço o preview da regra "{regra}" para "{sigla}" no ano {ano:d}'))
def pede_preview_ano(app, contexto, regra, sigla, ano):
    _pede(contexto, regra, sigla, ano)


@when(parsers.parse('peço o preview da regra "{regra}" para "{sigla}"'))
def pede_preview(app, contexto, regra, sigla):
    _pede(contexto, regra, sigla, None)


def _pede(contexto, regra, sigla, ano):
    from fluxocaixa.models import Lancamento
    from fluxocaixa.services.regra import preview_regra

    contexto["lancamentos_antes"] = Lancamento.query.count()
    contexto["preview"] = preview_regra(
        regra, sistema_por_sigla(sigla).seq_sistema_origem,
        num_ano_exercicio=ano, limite=10,
    )


# --------------------------------------------------------------------------
# Então
# --------------------------------------------------------------------------

@then(parsers.parse('o preview retorna {n:d} linhas'))
def preview_conta(contexto, n):
    assert contexto["preview"]["total"] == n, contexto["preview"]


@then("a amostra do preview traz valores Decimal com 2 casas")
def preview_decimal(contexto):
    amostra = contexto["preview"]["amostra"]
    assert amostra, "amostra vazia"
    for linha in amostra:
        val = linha["val_referencia"]
        assert isinstance(val, Decimal), type(val)
        assert val == val.quantize(Decimal("0.01"))


@then("nenhuma linha da staging teve o status alterado")
def staging_intacta(app):
    from fluxocaixa.models import EtlStaging
    from fluxocaixa.models.base import db

    db.session.expire_all()
    linhas = EtlStaging.query.all()
    assert linhas
    assert all(ln.ind_status_processamento == '0' for ln in linhas)


@then("nenhum lançamento foi criado")
def sem_lancamento(app, contexto):
    from fluxocaixa.models import Lancamento
    from fluxocaixa.models.base import db

    db.session.expire_all()
    # o seed demo já popula lançamentos: o que importa é que o preview não criou
    assert Lancamento.query.count() == contexto["lancamentos_antes"]
