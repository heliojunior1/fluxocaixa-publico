"""Steps BDD — despacho de modelos no serviço (spec previsao R14).

Ilha 2069 (compartilhada com o Q09 — qualificador próprio). Import tardio.
"""
from datetime import date
from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../previsao/despacho_modelos.feature")

ANO = 2069
QUAL = "1.73.1"
QUAL_VAZIO = "1.73.2"


@pytest.fixture()
def contexto():
    return {}


def _db():
    from fluxocaixa.models.base import db

    return db


def _limpar():
    from fluxocaixa.models import Lancamento, Qualificador, SimuladorCenario

    db = _db()
    db.session.rollback()
    for num in (QUAL, QUAL_VAZIO):
        q = Qualificador.query.filter_by(num_qualificador=num).first()
        if q is not None:
            Lancamento.query.filter_by(seq_qualificador=q.seq_qualificador).delete()
    for c in SimuladorCenario.query.filter(
            SimuladorCenario.nom_cenario.like("CEN_Q14%")).all():
        db.session.delete(c)
    db.session.commit()


@pytest.fixture(autouse=True)
def _ilha(app):
    _limpar()
    yield
    _limpar()


def _qualificador(num):
    from fluxocaixa.models import Qualificador

    db = _db()
    q = Qualificador.query.filter_by(num_qualificador=num).first()
    if q is None:
        q = Qualificador(num_qualificador=num,
                         dsc_qualificador=f"Rubrica Despacho {num}",
                         ind_status='A')
        db.session.add(q)
        db.session.commit()
    return q


@given("um qualificador de despacho com 24 meses de histórico",
       target_fixture="qualificador")
def qual_com_historico(app):
    from fluxocaixa.models import Lancamento
    from fluxocaixa.services.dominio_lancamento import resolver_origem, resolver_tipo

    q = _qualificador(QUAL)
    db = _db()
    ano, mes = ANO - 3, 1
    for _ in range(24):
        db.session.add(Lancamento(
            dat_lancamento=date(ano, mes, 15),
            seq_qualificador=q.seq_qualificador,
            val_lancamento=Decimal("100.00"),
            cod_tipo_lancamento=resolver_tipo("Entrada").cod_tipo_lancamento,
            cod_origem_lancamento=resolver_origem("Manual").cod_origem_lancamento,
            cod_pessoa_inclusao=1, ind_status='A'))
        mes += 1
        if mes > 12:
            mes, ano = 1, ano + 1
    db.session.commit()
    return q


@given("um qualificador de despacho sem histórico", target_fixture="qualificador")
def qual_sem_historico(app):
    return _qualificador(QUAL_VAZIO)


@given(parsers.parse('um cenário MANUAL de despacho com versão publicada'),
       target_fixture="cenario")
def cenario_com_versao(app):
    from fluxocaixa.services.projecao_versao_service import (
        publicar_versao,
        salvar_projecao_como_versao,
    )
    from fluxocaixa.services.simulador_cenario_service import criar_simulador_cenario

    q = _qualificador(QUAL)
    ajustes = {f"val_ajuste_1_{q.seq_qualificador}": "100.00",
               f"cod_tipo_ajuste_1_{q.seq_qualificador}": "V"}
    cenario = criar_simulador_cenario(
        nom_cenario="CEN_Q14_VERSAO", dsc_cenario="q14", ano_base=ANO,
        num_periodos=12,
        tipo_cenario_receita="MANUAL", config_receita={},
        tipo_cenario_despesa="MANUAL", config_despesa={},
        ajustes_receita=ajustes, user_id=1)
    versao = salvar_projecao_como_versao(
        cenario.seq_simulador_cenario, nom_versao="Q14", publicar=True)
    publicar_versao(versao.seq_projecao_versao)
    return cenario


@given("que executar a simulação passará a falhar")
def executar_falha(app, monkeypatch):
    from fluxocaixa.web import simulador_cenarios

    def _explode(*args, **kwargs):
        raise RuntimeError("executar_simulacao rodou num page view — A7")

    monkeypatch.setattr(simulador_cenarios, "executar_simulacao", _explode)


@when(parsers.parse('chamo calcular_projecao com "{modelo}" e {n:d} períodos'))
def chama_calcular(app, contexto, modelo, n):
    from fluxocaixa.services import modelos_economicos_service as modelos
    from fluxocaixa.services.validacao import RegraNegocioError

    from fluxocaixa.models import Qualificador

    q = (Qualificador.query.filter_by(num_qualificador=QUAL).first()
         or Qualificador.query.filter_by(num_qualificador=QUAL_VAZIO).first())
    seqs = [q.seq_qualificador] if q else [999999]
    try:
        contexto["resultado"] = modelos.calcular_projecao(
            modelo, seqs, num_periodos=n, ano_base=ANO, config={})
        contexto["erro"] = None
    except RegraNegocioError as exc:
        contexto["erro"] = exc


@when("abro a página do cenário")
def abre_pagina(client, contexto, cenario):
    contexto["resp"] = client.get(f"/simulador/{cenario.seq_simulador_cenario}")


@then(parsers.parse("recebo uma projeção com {n:d} períodos"))
def projecao_ok(contexto, n):
    assert contexto["erro"] is None, contexto["erro"]
    assert len(contexto["resultado"]) == n


@then(parsers.parse('recebo erro de negócio de despacho citando "{trecho}"'))
def erro_citando(contexto, trecho):
    assert contexto["erro"] is not None, (
        "o despacho aceitou — deveria recusar com erro de negócio")
    assert trecho.lower() in str(contexto["erro"]).lower(), str(contexto["erro"])


@then("a página responde com sucesso")
def pagina_ok(contexto):
    assert contexto["resp"].status_code == 200, (
        f"{contexto['resp'].status_code} — a página executou a simulação no "
        "page view (A7)")


@then(parsers.parse('exibe a origem "{texto}"'))
def exibe_origem(contexto, texto):
    assert 'data-testid="origem-versao"' in contexto["resp"].text, (
        "sem o aviso de origem — o usuário não sabe que vê a versão publicada")
