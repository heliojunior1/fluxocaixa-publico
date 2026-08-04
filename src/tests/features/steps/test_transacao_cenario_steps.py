"""Steps BDD — transação única de cenário e backtest (spec previsao R13).

Ilha 2069. Import tardio de `fluxocaixa`.
"""
from decimal import Decimal

import pytest
from sqlalchemy import text
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../previsao/transacao_cenario.feature")

ANO = 2069
QUAL = "1.70.1"


@pytest.fixture()
def contexto():
    return {}


def _db():
    from fluxocaixa.models.base import db

    return db


def _limpar():
    from fluxocaixa.models import SimuladorCenario

    db = _db()
    db.session.rollback()
    for c in SimuladorCenario.query.filter(
            SimuladorCenario.nom_cenario.like("CEN_Q09%")).all():
        db.session.delete(c)
    db.session.execute(text(
        "DELETE FROM flc_backtest_recomendacao WHERE cod_modelo = 'Q09_TESTE'"))
    db.session.commit()


@pytest.fixture(autouse=True)
def _ilha(app):
    _limpar()
    yield
    _limpar()


def _qualificador():
    from fluxocaixa.models import Qualificador

    db = _db()
    q = Qualificador.query.filter_by(num_qualificador=QUAL).first()
    if q is None:
        q = Qualificador(num_qualificador=QUAL,
                         dsc_qualificador="Rubrica Transação Q09",
                         ind_status='A')
        db.session.add(q)
        db.session.commit()
    return q


@when(parsers.parse('tento criar o cenário "{nome}" com modelo LOA na perna '
                    'de receita'))
def cria_com_modelo_errado(app, contexto, nome):
    from fluxocaixa.services.simulador_cenario_service import criar_simulador_cenario
    from fluxocaixa.services.validacao import RegraNegocioError

    try:
        criar_simulador_cenario(
            nom_cenario=nome, dsc_cenario="órfão?", ano_base=ANO,
            num_periodos=12,
            tipo_cenario_receita="LOA", config_receita={},
            tipo_cenario_despesa="MANUAL", config_despesa={},
            user_id=1)
        contexto["erro"] = None
    except RegraNegocioError as exc:
        contexto["erro"] = exc


@given(parsers.parse('um cenário MANUAL "{nome}" com um ajuste gravado'),
       target_fixture="cenario")
def cenario_com_ajuste(app, nome):
    from fluxocaixa.services.simulador_cenario_service import criar_simulador_cenario

    q = _qualificador()
    ajustes = {f"val_ajuste_1_{q.seq_qualificador}": "100.00",
               f"cod_tipo_ajuste_1_{q.seq_qualificador}": "V"}
    return criar_simulador_cenario(
        nom_cenario=nome, dsc_cenario="ajustes", ano_base=ANO, num_periodos=12,
        tipo_cenario_receita="MANUAL", config_receita={},
        tipo_cenario_despesa="MANUAL", config_despesa={},
        ajustes_receita=ajustes, user_id=1)


@when("atualizo o cenário com um ajuste de qualificador inexistente")
def atualiza_com_ajuste_invalido(app, contexto, cenario):
    from fluxocaixa.services.simulador_cenario_service import (
        atualizar_simulador_cenario,
    )
    from fluxocaixa.services.validacao import RegraNegocioError

    ajustes = {"val_ajuste_1_99999999": "50.00",
               "cod_tipo_ajuste_1_99999999": "V"}
    try:
        atualizar_simulador_cenario(
            cenario.seq_simulador_cenario,
            nom_cenario=cenario.nom_cenario, dsc_cenario="upd", ano_base=ANO,
            num_periodos=12,
            tipo_cenario_receita="MANUAL", config_receita={},
            tipo_cenario_despesa="MANUAL", config_despesa={},
            ajustes_receita=ajustes, user_id=1)
        contexto["erro"] = None
    except RegraNegocioError as exc:
        contexto["erro"] = exc


@given("uma recomendação de backtest gravada para o qualificador da ilha")
def recomendacao_gravada(app):
    db = _db()
    q = _qualificador()
    db.session.execute(text(
        """INSERT INTO flc_backtest_recomendacao
           (seq_qualificador, cod_modelo, val_mape, val_wmape, val_bias,
            anos_teste, dat_execucao)
           VALUES (:q, 'Q09_TESTE', 1.0, 1.0, 0.0, '[]', '2069-01-01')"""),
        {"q": q.seq_qualificador})
    db.session.commit()


@when("a regravação das recomendações falha no meio")
def regravacao_falha(app, contexto):
    from fluxocaixa.services.backtest_service import salvar_recomendacoes

    # filho malformado: estoura DEPOIS do DELETE, no meio dos INSERTs
    malformado = {
        "anos_teste": [ANO],
        "resultados_filho": [
            {"melhor_modelo": "X", "modelos": {"X": {"mape": 1.0}}},  # sem seq
        ],
    }
    try:
        salvar_recomendacoes(malformado)
        contexto["falhou"] = False
    except Exception:
        contexto["falhou"] = True
    assert contexto["falhou"], "a massa malformada deveria falhar"


def _recomendacao_existe():
    db = _db()
    return db.session.execute(text(
        "SELECT COUNT(*) FROM flc_backtest_recomendacao "
        "WHERE cod_modelo = 'Q09_TESTE'")).scalar() > 0


@then("recebo erro de negócio de cenário")
def erro_de_negocio(contexto):
    assert contexto["erro"] is not None, "a operação deveria ter falhado"


@then(parsers.parse('nenhum cenário "{nome}" foi persistido'))
def nenhum_cenario(app, nome):
    from fluxocaixa.models import SimuladorCenario

    _db().session.expire_all()
    orfao = SimuladorCenario.query.filter_by(nom_cenario=nome).first()
    assert orfao is None, (
        "o cabeçalho do cenário sobreviveu à falha da config — órfão "
        "commitado que nada desfaz")


@then("o ajuste anterior permanece intacto")
def ajuste_intacto(app, cenario):
    from fluxocaixa.repositories import simulador_cenario_repository as repo

    _db().session.expire_all()
    configs = repo.get_configs_by_simulador(cenario.seq_simulador_cenario)
    ajustes = []
    for config in configs:
        ajustes.extend(repo.get_ajustes_by_config(config.seq_cenario_config))
    assert len(ajustes) == 1, (
        f"{len(ajustes)} ajustes — a exclusão dos antigos foi commitada "
        "antes de os novos falharem")
    assert ajustes[0].val_ajuste == Decimal("100.00")


@then("a recomendação anterior permanece após a falha")
def recomendacao_permanece(app):
    assert _recomendacao_existe(), (
        "a recomendação sumiu — o DELETE global foi efetivado sem os INSERTs")


@then("um commit posterior de outra operação não a apaga")
def commit_posterior_nao_apaga(app):
    # simula outra operação qualquer commitando na MESMA sessão global
    _db().session.commit()
    assert _recomendacao_existe(), (
        "o commit posterior efetivou o DELETE pendente da sessão suja — "
        "todas as recomendações apagadas sem gravar as novas")
