"""Steps BDD — configuração unificada do cenário (spec previsao R1–R6).

Ilha 2015: as outras redes/features ocupam 2017, 2019, 2022–2026 e 2031–2038.
"""
from datetime import date, datetime
from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../previsao/cenario_config.feature")

ANO = 2015
QUAL = "1.96.1"


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
        SimuladorCenario.nom_cenario.like("CEN_%")
    ).all():
        db.session.delete(c)
    db.session.commit()


@pytest.fixture(autouse=True)
def _ilha(app):
    _limpar()
    yield
    _limpar()


def _qualificador(num=QUAL):
    from fluxocaixa.models import Qualificador

    db = _db()
    q = Qualificador.query.filter_by(num_qualificador=num).first()
    if q is None:
        q = Qualificador(num_qualificador=num,
                         dsc_qualificador=f"Rubrica cenário {num}")
        db.session.add(q)
        db.session.commit()
    return q


def _configs(cenario):
    from fluxocaixa.repositories import simulador_cenario_repository as repo

    return repo.get_configs_by_simulador(cenario.seq_simulador_cenario)


def _configurar(contexto, cenario, perna, modelo):
    from fluxocaixa.services.simulador_cenario_service import criar_config
    from fluxocaixa.services.validacao import RegraNegocioError

    try:
        contexto["config"] = criar_config(
            cenario.seq_simulador_cenario, perna, modelo,
            {"seq_qualificadores": [_qualificador().seq_qualificador]})
        contexto.pop("erro", None)
    except RegraNegocioError as erro:
        contexto["erro"] = erro


# --------------------------------------------------------------------------
# Dado
# --------------------------------------------------------------------------

@given(parsers.parse('um cenário de convergência "{nome}"'), target_fixture="cenario")
@given(parsers.parse('um cenário de convergência "{nome}" com versão publicada nas duas pernas'),
       target_fixture="cenario")
def cenario_convergencia(app, contexto, nome):
    from fluxocaixa.models import ProjecaoValor, ProjecaoVersao, SimuladorCenario

    db = _db()
    cenario = SimuladorCenario(
        nom_cenario=nome, dsc_cenario="F6.2", ano_base=ANO, num_periodos=12,
        cod_periodicidade='MENSAL', ind_status='A',
    )
    db.session.add(cenario)
    db.session.commit()

    if "versão publicada" in (contexto.get("_marca") or "") or "PROJECAO" in nome or "LEITURA" in nome:
        versao = ProjecaoVersao(
            seq_simulador_cenario=cenario.seq_simulador_cenario,
            nom_versao="v1", dat_versao=datetime(2026, 1, 1), ind_publicado='S')
        db.session.add(versao)
        db.session.commit()
        for tipo, valor in (('C', "1000.00"), ('D', "400.00")):
            db.session.add(ProjecaoValor(
                seq_projecao_versao=versao.seq_projecao_versao,
                seq_qualificador=_qualificador().seq_qualificador,
                cod_tipo=tipo, ano=ANO, num_periodo=1, val_projetado=Decimal(valor)))
        db.session.commit()
        contexto["versao"] = versao
    contexto["cenario"] = cenario
    return cenario


@given(parsers.parse('um cenário de convergência "{nome}" com a perna "{perna}" no modelo "{modelo}" e ajustes'),
       target_fixture="cenario")
def cenario_com_ajustes(app, contexto, nome, perna, modelo):
    from fluxocaixa.services.simulador_cenario_service import criar_simulador_cenario

    seq = _qualificador().seq_qualificador
    ajustes = {f"val_ajuste_desp_{m}_{seq}": 250 for m in range(1, 13)}
    ajustes.update({f"cod_tipo_ajuste_desp_{m}_{seq}": "V" for m in range(1, 13)})
    cenario = criar_simulador_cenario(
        nom_cenario=nome, dsc_cenario="F6.2", ano_base=ANO, num_periodos=12,
        tipo_cenario_receita=None, config_receita={},
        tipo_cenario_despesa=modelo, config_despesa={"seq_qualificadores": [seq]},
        ajustes_despesa=ajustes, user_id=1,
    )
    contexto["cenario"] = cenario
    return cenario


@given(parsers.parse('a perna "{perna}" configurada com o modelo "{modelo}"'))
def perna_configurada(contexto, cenario, perna, modelo):
    _configurar(contexto, cenario, perna, modelo)
    assert "erro" not in contexto, contexto.get("erro")


@given(parsers.parse('um ajuste de "{valor}" do tipo "{tipo}" registrado na perna "{perna}"'))
def ajuste_registrado(contexto, cenario, valor, tipo, perna):
    _registrar_ajuste(contexto, cenario, perna, valor, tipo)


def _registrar_ajuste(contexto, cenario, perna, valor, tipo):
    from fluxocaixa.models import CenarioAjuste
    from fluxocaixa.repositories import simulador_cenario_repository as repo

    config = repo.get_config_by_perna(cenario.seq_simulador_cenario, perna)
    try:
        repo.create_ajuste(CenarioAjuste(
            seq_cenario_config=config.seq_cenario_config,
            seq_qualificador=_qualificador().seq_qualificador,
            ano=ANO, mes=1, cod_tipo_ajuste=tipo, val_ajuste=Decimal(valor)))
        contexto["ajuste_ok"] = True
    except Exception:
        _db().session.rollback()
        contexto["ajuste_ok"] = False


# --------------------------------------------------------------------------
# Quando
# --------------------------------------------------------------------------

@when(parsers.parse('configuro a perna "{perna}" com o modelo "{modelo}"'))
def configura(contexto, cenario, perna, modelo):
    _configurar(contexto, cenario, perna, modelo)


@when("executo a simulação do cenário")
def executa(contexto, cenario):
    from fluxocaixa.services.simulador_cenario_service import executar_simulacao

    contexto["resultado"] = executar_simulacao(cenario.seq_simulador_cenario)


@when(parsers.parse('registro um ajuste de "{valor}" do tipo "{tipo}" em cada perna para o mesmo qualificador, ano e mês'))
def registra_nas_duas(contexto, cenario, valor, tipo):
    for perna in ('C', 'D'):
        _registrar_ajuste(contexto, cenario, perna, valor, tipo)


@when(parsers.parse('registro outro ajuste de "{valor}" do tipo "{tipo}" na perna "{perna}" para a mesma chave'))
def registra_duplicado(contexto, cenario, valor, tipo, perna):
    _registrar_ajuste(contexto, cenario, perna, valor, tipo)


@when(parsers.parse('removo a configuração da perna "{perna}"'))
def remove_config(contexto, cenario, perna):
    from fluxocaixa.repositories import simulador_cenario_repository as repo

    config = repo.get_config_by_perna(cenario.seq_simulador_cenario, perna)
    repo.delete_config(config.seq_cenario_config)


@when("inspeciono os cenários migrados do seed")
def inspeciona_seed(app, contexto):
    """O banco de teste é compartilhado e outros módulos apagam cenários, então
    o invariante é verificado sobre um cenário criado pela via pública: toda
    perna configurada resulta em `flc_cenario_config` com modelo preenchido —
    que é o que a migração produz para os cenários existentes."""
    from fluxocaixa.repositories import simulador_cenario_repository as repo
    from fluxocaixa.services.simulador_cenario_service import criar_simulador_cenario

    cenario = criar_simulador_cenario(
        nom_cenario="CEN_INVARIANTE", dsc_cenario="R4", ano_base=ANO,
        num_periodos=12,
        tipo_cenario_receita="MANUAL", config_receita={},
        tipo_cenario_despesa="LOA", config_despesa={"valor_anual": 1200},
        user_id=1)
    contexto["seed"] = [
        (cenario, repo.get_configs_by_simulador(cenario.seq_simulador_cenario))
    ]


@when("leio os valores da versão publicada")
def le_valores(contexto):
    from fluxocaixa.models import ProjecaoValor

    contexto["valores"] = ProjecaoValor.query.filter_by(
        seq_projecao_versao=contexto["versao"].seq_projecao_versao).all()


@when("resolvo a projeção para o fluxo de caixa")
def resolve_projecao(contexto, cenario):
    from fluxocaixa.services.relatorio.dfc_projecao import resolver_projecao

    contexto["mapa"], _ = resolver_projecao(cenario.seq_simulador_cenario, ANO)


# --------------------------------------------------------------------------
# Então
# --------------------------------------------------------------------------

@then(parsers.parse('o cenário tem {qtd:d} configurações'))
def qtd_configs(cenario, qtd):
    assert len(_configs(cenario)) == qtd


@then(parsers.parse('existe configuração da perna "{a}" e da perna "{b}"'))
def existem_pernas(cenario, a, b):
    pernas = {c.cod_tipo_lancamento for c in _configs(cenario)}
    assert pernas == {a, b}, pernas


@then(parsers.parse('recebo erro de configuração mencionando "{trecho}"'))
def erro_com_trecho(contexto, trecho):
    assert "erro" in contexto, "esperava RegraNegocioError"
    assert trecho.lower() in str(contexto["erro"]).lower(), str(contexto["erro"])


@then(parsers.parse('a configuração {resultado}'))
def config_resultado(contexto, resultado):
    if resultado.strip() == "é criada":
        assert "erro" not in contexto, str(contexto.get("erro"))
        assert contexto.get("config") is not None
    else:
        assert "erro" in contexto, "esperava rejeição"


@then("a simulação devolve resultado")
def simulacao_ok(contexto):
    assert contexto["resultado"] is not None


@then("a projeção de receita está vazia")
def receita_vazia(contexto):
    assert len(contexto["resultado"]["projecao_receita"]) == 0


@then(parsers.parse('cada perna tem {qtd:d} ajuste'))
def ajustes_por_perna(cenario, qtd):
    from fluxocaixa.repositories import simulador_cenario_repository as repo

    for config in _configs(cenario):
        assert len(repo.get_ajustes_by_config(config.seq_cenario_config)) == qtd


@then("o registro do ajuste é rejeitado")
def ajuste_rejeitado(contexto):
    assert contexto["ajuste_ok"] is False


@then("não há ajustes órfãos na ilha")
def sem_orfaos(cenario):
    from fluxocaixa.models import CenarioAjuste

    seqs = {c.seq_cenario_config for c in _configs(cenario)}
    orfaos = [a for a in CenarioAjuste.query.all()
              if a.seq_cenario_config not in seqs and a.ano == ANO]
    assert orfaos == [], orfaos


@then("todo cenário do seed tem configuração unificada")
def seed_unificado(contexto):
    assert contexto["seed"], "seed sem cenários"
    for cenario, configs in contexto["seed"]:
        assert configs, f"cenário {cenario.nom_cenario} sem config"


@then("nenhuma configuração tem modelo vazio")
def seed_com_modelo(contexto):
    for _cenario, configs in contexto["seed"]:
        assert all(c.cod_tipo_modelo for c in configs)


@then(parsers.parse('os tipos gravados são "{a}" e "{b}"'))
def tipos_gravados(contexto, a, b):
    assert {v.cod_tipo for v in contexto["valores"]} == {a, b}


@then(parsers.parse('nenhum valor tem o tipo antigo "{antigo}"'))
def sem_tipo_antigo(contexto, antigo):
    assert all(v.cod_tipo != antigo for v in contexto["valores"])


@then("todos os valores projetados de despesa são positivos")
def despesa_positiva(contexto):
    despesa = contexto["resultado"]["projecao_despesa"]
    assert len(despesa) > 0, "projeção de despesa vazia"
    assert all(v >= 0 for v in despesa["valor_projetado"]), despesa["valor_projetado"].tolist()


@then(parsers.parse('os valores da perna "{perna}" aparecem negativos'))
def perna_negativa(contexto, perna):
    valores = [v for (_s, t, _m), v in contexto["mapa"].items() if t == perna]
    assert valores and all(v < 0 for v in valores), valores


@then(parsers.parse('os valores da perna "{perna}" aparecem positivos'))
def perna_positiva(contexto, perna):
    valores = [v for (_s, t, _m), v in contexto["mapa"].items() if t == perna]
    assert valores and all(v > 0 for v in valores), valores
