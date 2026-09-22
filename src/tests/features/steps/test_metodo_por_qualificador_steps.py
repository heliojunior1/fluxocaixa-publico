"""Steps BDD — previsão por qualificador (docs/previsao-metodo-por-qualificador.md).

Ilha: plano do exercício 2097 (receita "1.88", despesa "2.88"), realizado em
2096. Import tardio de `fluxocaixa` (isolamento de banco da suíte).
"""
import json
from datetime import date
from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../previsao/metodo_por_qualificador.feature")

ANO = 2097
EXERCICIO = 2097
DATA_REALIZADO = date(2096, 6, 15)


@pytest.fixture()
def contexto():
    return {}


def _db():
    from fluxocaixa.models.base import db

    return db


def _limpar():
    from sqlalchemy import or_

    from fluxocaixa.models import (
        Lancamento,
        ProjecaoVersao,
        Qualificador,
        RubricaFormula,
        SetorPrevisao,
        SimuladorCenario,
    )

    db = _db()
    db.session.rollback()
    cenarios = (SimuladorCenario.query
                .filter(SimuladorCenario.nom_cenario.like("CEN_MQ%"))
                .order_by(SimuladorCenario.seq_simulador_cenario.desc()).all())
    for c in cenarios:
        for v in ProjecaoVersao.query.filter_by(
                seq_simulador_cenario=c.seq_simulador_cenario).all():
            db.session.delete(v)
        db.session.flush()
        db.session.delete(c)
        db.session.flush()
    quals = Qualificador.query.filter(
        Qualificador.num_ano_exercicio == EXERCICIO,
        or_(Qualificador.num_qualificador.like("1.88%"),
            Qualificador.num_qualificador.like("2.88%"))).all()
    seqs = [q.seq_qualificador for q in quals]
    if seqs:
        for lanc in Lancamento.query.filter(Lancamento.seq_qualificador.in_(seqs)).all():
            db.session.delete(lanc)
        for f in RubricaFormula.query.filter(RubricaFormula.seq_qualificador.in_(seqs)).all():
            db.session.delete(f)
        for q in quals:
            q.seq_setor_previsao = None
        db.session.flush()
        for q in sorted(quals, key=lambda q: -len(q.num_qualificador)):
            db.session.delete(q)
            db.session.flush()
    for s in SetorPrevisao.query.filter(SetorPrevisao.sgl_setor.like("BDDMQ%")).all():
        db.session.delete(s)
    db.session.commit()


@pytest.fixture(autouse=True)
def _ilha(app):
    _limpar()
    yield
    _limpar()


def _q(codigo):
    from fluxocaixa.models import Qualificador

    return Qualificador.query.filter_by(num_qualificador=codigo,
                                        num_ano_exercicio=EXERCICIO).one()


def _cenario(nome):
    from fluxocaixa.models import SimuladorCenario

    return SimuladorCenario.query.filter_by(nom_cenario=nome, ind_status='A').one()


def _erro(contexto, funcao, *args, **kwargs):
    from fluxocaixa.services.validacao import RegraNegocioError

    try:
        contexto["retorno"] = funcao(*args, **kwargs)
        contexto["erro"] = None
    except RegraNegocioError as exc:
        _db().session.rollback()
        contexto["erro"] = exc


# ---------------------------------------------------------------------------
# Massa
# ---------------------------------------------------------------------------

@given("o plano da ilha com realizado de 2096")
def plano_da_ilha(app, datatable):
    from fluxocaixa.models import Lancamento, Qualificador
    from fluxocaixa.models.lancamento import TIPO_CREDITO, TIPO_DEBITO
    from fluxocaixa.services.dominio_lancamento import resolver_origem

    db = _db()
    cabecalho, *linhas = datatable
    origem = resolver_origem("Manual").cod_origem_lancamento
    for codigo, pai, realizado in linhas:
        q = Qualificador(num_qualificador=codigo, dsc_qualificador=f"Ilha MQ {codigo}",
                         num_ano_exercicio=EXERCICIO, ind_status='A',
                         cod_qualificador_pai=_q(pai).seq_qualificador if pai else None)
        db.session.add(q)
        db.session.flush()
        if realizado:
            db.session.add(Lancamento(
                dat_lancamento=DATA_REALIZADO, seq_qualificador=q.seq_qualificador,
                val_lancamento=Decimal(realizado),
                cod_tipo_lancamento=TIPO_CREDITO if codigo.startswith("1") else TIPO_DEBITO,
                cod_origem_lancamento=origem, cod_pessoa_inclusao=1, ind_status='A'))
    db.session.commit()


def _criar_cenario(nome, receita='', cfg_receita=None, despesa='MEDIA_HISTORICA',
                   cfg_despesa=None):
    from fluxocaixa.services.simulador_cenario_service import criar_simulador_cenario

    if despesa == 'MEDIA_HISTORICA' and cfg_despesa is None:
        cfg_despesa = {"seq_qualificadores": [_q("2.88.1").seq_qualificador]}
    return criar_simulador_cenario(
        nom_cenario=nome, dsc_cenario="bdd", ano_base=ANO, num_periodos=12,
        tipo_cenario_receita=receita, config_receita=cfg_receita or {},
        tipo_cenario_despesa=despesa, config_despesa=cfg_despesa or {},
        user_id=1, json_config_base=json.dumps({"anos": [2096]}))


@given(parsers.parse('um cenário "{nome}" sem padrão de receita'), target_fixture="cenario")
def cenario_sem_padrao(app, nome):
    return _criar_cenario(nome)


@given(parsers.parse('um cenário "{nome}" com média de crescimento na receita para '
                     '"{a}" e "{b}"'), target_fixture="cenario")
def cenario_agregado(app, nome, a, b):
    return _criar_cenario(
        nome, receita='CRESCIMENTO_ANO',
        cfg_receita={"seq_qualificadores": [_q(a).seq_qualificador, _q(b).seq_qualificador],
                     "mes_referencia": 3})


@given(parsers.parse('o setor "{sigla}" com recorte "{codigo}"'))
def setor_com_recorte(app, sigla, codigo):
    from fluxocaixa.services.setor_previsao_service import criar_setor, marcar_recorte

    setor = criar_setor(f"Setor {sigla}", sigla)
    marcar_recorte(_q(codigo).seq_qualificador, setor.seq_setor_previsao)


@given(parsers.parse('um cenário "{nome}" do setor "{sigla}"'), target_fixture="cenario")
def cenario_setorial(app, nome, sigla):
    from fluxocaixa.models import SetorPrevisao
    from fluxocaixa.services.setor_previsao_service import definir_setor_do_cenario

    cenario = _criar_cenario(nome, despesa='')
    setor = SetorPrevisao.query.filter_by(sgl_setor=sigla, ind_status='A').one()
    definir_setor_do_cenario(cenario.seq_simulador_cenario, setor.seq_setor_previsao)
    return cenario


@given(parsers.parse('a marcação "{codigo}" com valor fixo anual "{valor}"'))
def marca_valor_fixo(cenario, codigo, valor):
    from fluxocaixa.services.metodo_qualificador_service import definir_marcacao

    definir_marcacao(cenario.seq_simulador_cenario, _q(codigo).seq_qualificador,
                     'VALOR_FIXO', {'valor_anual': valor}, user_id=1)


@given(parsers.parse('a marcação "{codigo}" com percentual "{pct}"'))
def marca_percentual(cenario, codigo, pct):
    from fluxocaixa.services.metodo_qualificador_service import definir_marcacao

    definir_marcacao(cenario.seq_simulador_cenario, _q(codigo).seq_qualificador,
                     'PERCENTUAL', {'percentual': pct}, user_id=1)


@given(parsers.parse('a marcação "{codigo}" sem projeção pelo motivo "{motivo}"'))
def marca_sem_projecao(cenario, codigo, motivo):
    from fluxocaixa.services.metodo_qualificador_service import definir_marcacao

    definir_marcacao(cenario.seq_simulador_cenario, _q(codigo).seq_qualificador,
                     'SEM_PROJECAO', {'motivo': motivo}, user_id=1)


@given(parsers.parse('a marcação "{codigo}" com fórmula'))
def marca_formula(cenario, codigo):
    from fluxocaixa.services.metodo_qualificador_service import definir_marcacao

    definir_marcacao(cenario.seq_simulador_cenario, _q(codigo).seq_qualificador,
                     'FORMULA', {}, user_id=1)


@given(parsers.parse('a fórmula de biblioteca "{expressao}" para a folha "{codigo}"'))
def formula_biblioteca(app, expressao, codigo):
    from fluxocaixa.models import RubricaFormula

    db = _db()
    db.session.add(RubricaFormula(seq_qualificador=_q(codigo).seq_qualificador,
                                  nom_formula="Biblioteca MQ",
                                  dsc_formula_expressao=expressao, ind_status='A'))
    db.session.commit()


@given(parsers.parse('a fórmula própria "{expressao}" para a folha "{codigo}"'))
def formula_propria(cenario, expressao, codigo):
    from fluxocaixa.services.formula_cenario_service import definir_formula_propria

    definir_formula_propria(cenario.seq_simulador_cenario, _q(codigo).seq_qualificador,
                            expressao, user_id=1)


@given("o cenário tem uma versão publicada")
def versao_publicada(cenario):
    from fluxocaixa.services.projecao_versao_service import salvar_projecao_como_versao

    salvar_projecao_como_versao(cenario.seq_simulador_cenario, "v publicada",
                                publicar=True, confirmado=True)


def _publicar_proposta(nome_cenario, nome_versao):
    from fluxocaixa.services.projecao_versao_service import salvar_projecao_como_versao

    return salvar_projecao_como_versao(_cenario(nome_cenario).seq_simulador_cenario,
                                       nome_versao, publicar=True, confirmado=True)


@given(parsers.parse('o cenário setorial publica a proposta "{nome_versao}"'))
def setorial_publica(cenario, contexto, nome_versao):
    contexto.setdefault("versoes", {})[nome_versao] = _publicar_proposta(
        cenario.nom_cenario, nome_versao).seq_projecao_versao
    contexto["setorial"] = cenario.nom_cenario


def _versao(nome_cenario, nome_versao):
    from fluxocaixa.models import ProjecaoVersao

    return ProjecaoVersao.query.filter_by(
        seq_simulador_cenario=_cenario(nome_cenario).seq_simulador_cenario,
        nom_versao=nome_versao).one()


@given(parsers.parse('a marcação "{codigo}" com a proposta "{nome_versao}" do cenário "{origem}"'))
def marca_proposta(cenario, codigo, nome_versao, origem):
    from fluxocaixa.services.metodo_qualificador_service import definir_marcacao

    definir_marcacao(cenario.seq_simulador_cenario, _q(codigo).seq_qualificador,
                     'PROPOSTA_SETORIAL',
                     {'seq_projecao_versao': _versao(origem, nome_versao).seq_projecao_versao},
                     user_id=1)


@given(parsers.parse('altero a marcação "{codigo}" para valor fixo anual "{valor}"'))
def altera_marcacao(cenario, codigo, valor):
    marca_valor_fixo(cenario, codigo, valor)


# ---------------------------------------------------------------------------
# Ações
# ---------------------------------------------------------------------------

@when("executo o cenário")
def executa(cenario, contexto):
    from fluxocaixa.services.simulador_cenario_service import executar_simulacao

    contexto["resultado"] = executar_simulacao(cenario.seq_simulador_cenario)


@when(parsers.parse('executo o cenário "{nome}"'))
def executa_nomeado(contexto, nome):
    from fluxocaixa.services.simulador_cenario_service import executar_simulacao

    contexto["resultado"] = executar_simulacao(_cenario(nome).seq_simulador_cenario)


@when("calculo a cobertura")
def calcula_cobertura(cenario, contexto):
    from fluxocaixa.services.metodo_qualificador_service import cobertura
    from fluxocaixa.services.simulador_cenario_service import executar_simulacao

    resultado = executar_simulacao(cenario.seq_simulador_cenario)
    contexto["cobertura"] = cobertura(cenario, resultado)


@when("tento publicar uma versão sem confirmar")
def publica_sem_confirmar(cenario, contexto):
    from fluxocaixa.services.projecao_versao_service import salvar_projecao_como_versao

    _erro(contexto, salvar_projecao_como_versao, cenario.seq_simulador_cenario,
          "sem confirmar", publicar=True)


@when(parsers.parse('tento marcar "{codigo}" com o método LOA'))
def marca_loa(cenario, contexto, codigo):
    from fluxocaixa.services.metodo_qualificador_service import definir_marcacao

    _erro(contexto, definir_marcacao, cenario.seq_simulador_cenario,
          _q(codigo).seq_qualificador, 'LOA', {}, 1)


@when(parsers.parse('tento marcar "{codigo}" com valor fixo anual "{valor}"'))
def tenta_valor_fixo(cenario, contexto, codigo, valor):
    from fluxocaixa.services.metodo_qualificador_service import definir_marcacao

    _erro(contexto, definir_marcacao, cenario.seq_simulador_cenario,
          _q(codigo).seq_qualificador, 'VALOR_FIXO', {'valor_anual': valor}, 1)


@when(parsers.parse('tento marcar "{codigo}" com a proposta "{nome_versao}" do cenário "{origem}"'))
def tenta_proposta(cenario, contexto, codigo, nome_versao, origem):
    from fluxocaixa.services.metodo_qualificador_service import definir_marcacao

    _erro(contexto, definir_marcacao, cenario.seq_simulador_cenario,
          _q(codigo).seq_qualificador, 'PROPOSTA_SETORIAL',
          {'seq_projecao_versao': _versao(origem, nome_versao).seq_projecao_versao}, 1)


@when(parsers.parse('duplico o cenário como "{nome}"'))
def duplica(cenario, contexto, nome):
    from fluxocaixa.services.simulador_cenario_service import duplicar_cenario

    contexto["copia"] = duplicar_cenario(cenario.seq_simulador_cenario, nome, user_id=1)


@when(parsers.parse('altero na cópia a marcação "{codigo}" para valor fixo anual "{valor}"'))
def altera_copia(contexto, codigo, valor):
    marca_valor_fixo(contexto["copia"], codigo, valor)


@when(parsers.parse('altero na cópia a fórmula própria da folha "{codigo}" para "{expressao}"'))
def altera_formula_copia(contexto, codigo, expressao):
    formula_propria(contexto["copia"], expressao, codigo)


@when(parsers.parse('o setor publica a proposta "{nome_versao}" com valor fixo anual "{valor}"'))
def setor_publica_nova(contexto, nome_versao, valor):
    setorial = _cenario(contexto["setorial"])
    marca_valor_fixo(setorial, "1.88.2", valor)
    _publicar_proposta(setorial.nom_cenario, nome_versao)


@when(parsers.parse('consulto a previsão de receita de {ano:d} para "{codigo}"'))
def consulta_previsao(cenario, contexto, ano, codigo):
    from fluxocaixa.services.relatorio.previsao_receita_service import (
        get_previsao_receita_data,
    )

    contexto["relatorio"] = get_previsao_receita_data(
        ano, cenario.seq_simulador_cenario, [_q(codigo).seq_qualificador])


# ---------------------------------------------------------------------------
# Verificações
# ---------------------------------------------------------------------------

def _total_folha(contexto, codigo):
    resultado = contexto["resultado"]
    seq = _q(codigo).seq_qualificador
    total = Decimal(0)
    for chave in ("projecao_receita_detalhada", "projecao_despesa_detalhada"):
        df = resultado.get(chave)
        if df is None or not len(df):
            continue
        linhas = df[df["seq_qualificador"] == seq]
        total += Decimal(str(round(float(linhas["valor_projetado"].sum()), 2)))
    return total.quantize(Decimal("0.01"))


@then(parsers.parse('a folha "{codigo}" resolve "{metodo}" herdado de "{origem}"'))
def resolve_herdado(cenario, codigo, metodo, origem):
    from fluxocaixa.services.metodo_qualificador_service import (
        carregar_marcacoes,
        marcacao_resolvida,
    )

    marcacao, propria = marcacao_resolvida(
        _q(codigo), carregar_marcacoes(cenario.seq_simulador_cenario))
    assert marcacao.cod_metodo == metodo
    assert not propria
    assert marcacao.seq_qualificador == _q(origem).seq_qualificador


@then(parsers.parse('a folha "{codigo}" resolve "{metodo}" próprio'))
def resolve_proprio(cenario, codigo, metodo):
    from fluxocaixa.services.metodo_qualificador_service import (
        carregar_marcacoes,
        marcacao_resolvida,
    )

    marcacao, propria = marcacao_resolvida(
        _q(codigo), carregar_marcacoes(cenario.seq_simulador_cenario))
    assert marcacao.cod_metodo == metodo
    assert propria


@then(parsers.parse('a folha "{codigo}" projeta "{valor}" no ano'))
def folha_projeta(contexto, codigo, valor):
    assert _total_folha(contexto, codigo) == Decimal(valor)


@then(parsers.parse('as projeções da folha "{codigo}" registram o método "{metodo}" '
                    'calculado em "{no}"'))
def rastro(contexto, codigo, metodo, no):
    df = contexto["resultado"]["projecao_receita_detalhada"]
    linhas = df[df["seq_qualificador"] == _q(codigo).seq_qualificador]
    assert set(linhas["cod_metodo"]) == {metodo}
    assert set(linhas["seq_qualificador_calculo"]) == {_q(no).seq_qualificador}


def _status(contexto, codigo):
    seq = _q(codigo).seq_qualificador
    for perna in ("C", "D"):
        for item in contexto["cobertura"][perna]:
            if item["seq_qualificador"] == seq:
                return item["status"]
    return None


@then(parsers.parse('a folha "{codigo}" é lacuna na cobertura'))
def e_lacuna(contexto, codigo):
    assert _status(contexto, codigo) == "LACUNA"


@then(parsers.parse('a folha "{codigo}" aparece como sem projeção declarada'))
def e_declarada(contexto, codigo):
    assert _status(contexto, codigo) == "DECLARADA"


@then(parsers.parse("a cobertura aponta {n:d} lacuna"))
def total_lacunas(contexto, n):
    assert contexto["cobertura"]["lacunas"] == n


@then(parsers.parse('recebo o erro de previsão "{trecho}"'))
def erro_previsao(contexto, trecho):
    assert contexto["erro"] is not None, "esperava RegraNegocioError"
    assert trecho in contexto["erro"].mensagem, contexto["erro"].mensagem


@then("consigo publicar confirmando e a versão registra as lacunas")
def publica_confirmando(cenario):
    from fluxocaixa.services.projecao_versao_service import salvar_projecao_como_versao

    versao = salvar_projecao_como_versao(cenario.seq_simulador_cenario, "confirmada",
                                         publicar=True, confirmado=True)
    resumo = json.loads(versao.json_resumo)
    assert versao.ind_publicado == 'S'
    assert resumo["lacunas"] == 2  # 1.88.2 e 1.88.3 (só 1.88.1 marcado)
    assert set(resumo["rubricas_sem_projecao"]) == {"1.88.2", "1.88.3"}


def _config(cenario, codigo):
    from fluxocaixa.services.metodo_qualificador_service import (
        carregar_marcacoes,
        config_da_marcacao,
    )

    return config_da_marcacao(
        carregar_marcacoes(cenario.seq_simulador_cenario)[_q(codigo).seq_qualificador])


@then(parsers.parse('a origem mantém "{codigo}" com valor fixo anual "{valor}"'))
def origem_mantem(cenario, codigo, valor):
    _db().session.expire_all()
    assert _config(cenario, codigo)["valor_anual"] == float(valor)


@then(parsers.parse('a origem mantém a fórmula própria "{expressao}" para "{codigo}"'))
def origem_formula(cenario, expressao, codigo):
    from fluxocaixa.services.metodo_qualificador_service import formula_da_folha

    assert formula_da_folha(cenario.seq_simulador_cenario,
                            _q(codigo).seq_qualificador) == (expressao, 'CENARIO')


@then("a cópia não tem versões e aponta a origem")
def copia_sem_versoes(cenario, contexto):
    from fluxocaixa.models import ProjecaoVersao

    copia = contexto["copia"]
    assert copia.seq_cenario_origem == cenario.seq_simulador_cenario
    assert ProjecaoVersao.query.filter_by(
        seq_simulador_cenario=copia.seq_simulador_cenario).count() == 0
    assert _config(copia, "1.88.1")["valor_anual"] == 600.0


@then(parsers.parse('a proposta "{nome_versao}" está enviada'))
def proposta_enviada(contexto, nome_versao):
    assert _versao(contexto["setorial"], nome_versao).cod_situacao_proposta == 'E'


@then(parsers.parse('devolver a proposta "{nome_versao}" é recusado porque está fixada'))
def devolver_recusado(contexto, nome_versao):
    from fluxocaixa.services.setor_previsao_service import avaliar_proposta

    _erro(contexto, avaliar_proposta, _versao(contexto["setorial"], nome_versao).seq_projecao_versao,
          False, "revisar", 1)
    assert contexto["erro"] is not None
    assert "fixada" in contexto["erro"].mensagem


@then(parsers.parse('a projeção detalhada traz as folhas "{a}" e "{b}" somando o total da perna'))
def detalhada_por_folha(contexto, a, b):
    resultado = contexto["resultado"]
    df = resultado["projecao_receita_detalhada"]
    seqs = {_q(a).seq_qualificador, _q(b).seq_qualificador}
    assert set(df["seq_qualificador"].dropna().astype(int)) == seqs
    total = round(float(resultado["projecao_receita"]["valor_projetado"].sum()), 2)
    assert total > 0
    assert round(float(df["valor_projetado"].sum()), 2) == total
    assert _total_folha(contexto, a) == Decimal("300.00")
    assert _total_folha(contexto, b) == Decimal("100.00")


@then(parsers.parse('a previsão anual é "{valor}" vinda da versão publicada'))
def previsao_da_versao(contexto, valor):
    relatorio = contexto["relatorio"]
    assert relatorio["projecao_origem"]["ao_vivo"] is False
    assert Decimal(str(relatorio["composicao_anual"][0]["previsao_total"])).quantize(
        Decimal("0.01")) == Decimal(valor)


@then(parsers.parse('os cenários afetados pela fórmula da biblioteca de "{codigo}" são "{nomes}"'))
def afetados_pela_biblioteca(codigo, nomes):
    from fluxocaixa.services.formula_cenario_service import cenarios_afetados_pela_biblioteca

    afetados = {c.nom_cenario for c in cenarios_afetados_pela_biblioteca(_q(codigo).seq_qualificador)
                if c.nom_cenario.startswith("CEN_MQ")}
    assert afetados == set(nomes.split(", "))
