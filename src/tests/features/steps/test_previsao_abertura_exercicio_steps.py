"""Steps BDD — despesa pela porta avulsa e previsão através da abertura de
exercício (change corrigir-previsao-despesa-e-abertura-exercicio; spec
previsao R20/R21, cadastros-nucleo R29).

Ilha: exercícios 2111–2114, receita "1.86", despesa "2.86". A abertura copia
TODO o plano ativo do ano de origem — os anos da ilha são exclusivos desta
feature. Import tardio de `fluxocaixa` (isolamento de banco da suíte).
"""
from datetime import date
from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../previsao/previsao_abertura_exercicio.feature")

ANOS_DA_ILHA = (2111, 2112, 2113, 2114)
PREFIXO_CENARIO = "CEN_AB_"
SETOR = "BDDAB"


@pytest.fixture()
def contexto():
    return {}


def _db():
    from fluxocaixa.models.base import db

    return db


def _limpar():
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
                .filter(SimuladorCenario.nom_cenario.like(f"{PREFIXO_CENARIO}%"))
                .order_by(SimuladorCenario.seq_simulador_cenario.desc()).all())
    for c in cenarios:
        for v in ProjecaoVersao.query.filter_by(
                seq_simulador_cenario=c.seq_simulador_cenario).all():
            db.session.delete(v)
        db.session.flush()
        db.session.delete(c)
        db.session.flush()
    quals = Qualificador.query.filter(
        Qualificador.num_ano_exercicio.in_(ANOS_DA_ILHA)).all()
    seqs = [q.seq_qualificador for q in quals]
    if seqs:
        for lanc in Lancamento.query.filter(Lancamento.seq_qualificador.in_(seqs)).all():
            db.session.delete(lanc)
        for f in RubricaFormula.query.filter(RubricaFormula.seq_qualificador.in_(seqs)).all():
            db.session.delete(f)
        for q in quals:
            q.seq_setor_previsao = None
            q.cod_qualificador_pai = None
        db.session.flush()
        for q in quals:
            db.session.delete(q)
        db.session.flush()
    for s in SetorPrevisao.query.filter_by(sgl_setor=SETOR).all():
        db.session.delete(s)
    db.session.commit()


@pytest.fixture(autouse=True)
def _ilha(app):
    _limpar()
    yield
    _limpar()


def _q(codigo, ano):
    from fluxocaixa.models import Qualificador

    return Qualificador.query.filter_by(num_qualificador=codigo,
                                        num_ano_exercicio=ano,
                                        ind_status='A').one()


def _criar_q(codigo, ano, pai=None):
    from fluxocaixa.services.qualificador_service import create_qualificador

    return create_qualificador(
        codigo, f"Ilha AB {codigo}", num_ano_exercicio=ano,
        cod_qualificador_pai=pai.seq_qualificador if pai else None)


# ---------------------------------------------------------------------------
# Massa
# ---------------------------------------------------------------------------

@given(parsers.parse('a rubrica de despesa "{codigo}" com saída de "{valor}" em '
                     'todos os meses de {inicio:d} a {fim:d}'))
def rubrica_de_despesa(app, codigo, valor, inicio, fim):
    from fluxocaixa.models import Lancamento
    from fluxocaixa.models.lancamento import TIPO_DEBITO
    from fluxocaixa.services.dominio_lancamento import resolver_origem

    q = _criar_q(codigo, fim)
    origem = resolver_origem("Manual").cod_origem_lancamento
    db = _db()
    for ano in range(inicio, fim + 1):
        for mes in range(1, 13):
            db.session.add(Lancamento(
                dat_lancamento=date(ano, mes, 10), seq_qualificador=q.seq_qualificador,
                val_lancamento=Decimal(valor), cod_tipo_lancamento=TIPO_DEBITO,
                cod_origem_lancamento=origem, cod_pessoa_inclusao=1, ind_status='A'))
    db.session.commit()


@given(parsers.parse('o plano de {ano:d} com a folha "{folha}" sob o bloco "{bloco}" '
                     'e realizado de "{valor}" no ano'))
def plano_com_folha(app, ano, folha, bloco, valor):
    """O realizado dá à folha participação no bloco (RN05) — sem ele, o valor
    fixo não teria por onde ser distribuído."""
    from fluxocaixa.models import Lancamento
    from fluxocaixa.models.lancamento import TIPO_CREDITO, TIPO_DEBITO
    from fluxocaixa.services.dominio_lancamento import resolver_origem

    pai = _criar_q(bloco, ano)
    q = _criar_q(folha, ano, pai=pai)
    db = _db()
    db.session.add(Lancamento(
        dat_lancamento=date(ano, 6, 15), seq_qualificador=q.seq_qualificador,
        val_lancamento=Decimal(valor),
        cod_tipo_lancamento=TIPO_CREDITO if folha.startswith("1") else TIPO_DEBITO,
        cod_origem_lancamento=resolver_origem("Manual").cod_origem_lancamento,
        cod_pessoa_inclusao=1, ind_status='A'))
    db.session.commit()


@given(parsers.parse('um cenário "{nome}" de {ano:d}'), target_fixture="cenario")
def cenario_sem_padrao(app, nome, ano):
    from fluxocaixa.services.simulador_cenario_service import criar_simulador_cenario

    return criar_simulador_cenario(
        nom_cenario=nome, dsc_cenario="bdd", ano_base=ano, num_periodos=12,
        tipo_cenario_receita='', config_receita={},
        tipo_cenario_despesa='', config_despesa={}, user_id=1)


@given(parsers.parse('um cenário "{nome}" de {ano:d} com despesa manual e ajuste de '
                     '"{valor}" em janeiro para "{folha}"'), target_fixture="cenario")
def cenario_manual_com_ajuste(app, nome, ano, valor, folha):
    from fluxocaixa.models import CenarioAjuste, CenarioConfig
    from fluxocaixa.services.simulador_cenario_service import criar_simulador_cenario

    cenario = criar_simulador_cenario(
        nom_cenario=nome, dsc_cenario="bdd", ano_base=ano, num_periodos=12,
        tipo_cenario_receita='', config_receita={},
        tipo_cenario_despesa='MANUAL', config_despesa={}, user_id=1)
    config = CenarioConfig.query.filter_by(
        seq_simulador_cenario=cenario.seq_simulador_cenario).one()
    db = _db()
    db.session.add(CenarioAjuste(
        seq_cenario_config=config.seq_cenario_config,
        seq_qualificador=_q(folha, ano - 1).seq_qualificador,
        ano=ano, mes=1, cod_tipo_ajuste='V', val_ajuste=Decimal(valor)))
    db.session.commit()
    return cenario


@given(parsers.parse('a marcação "{codigo}" com valor fixo anual "{valor}"'))
def marca_valor_fixo(cenario, codigo, valor):
    from fluxocaixa.services.metodo_qualificador_service import (
        definir_marcacao,
        exercicio_do_cenario,
    )

    ano = exercicio_do_cenario(cenario)
    definir_marcacao(cenario.seq_simulador_cenario, _q(codigo, ano).seq_qualificador,
                     'VALOR_FIXO', {'valor_anual': valor}, user_id=1)


@given("o cenário tem uma versão publicada")
def versao_publicada(cenario, contexto):
    from fluxocaixa.services.projecao_versao_service import salvar_projecao_como_versao

    contexto["versao"] = salvar_projecao_como_versao(
        cenario.seq_simulador_cenario, "v antes da abertura",
        publicar=True, confirmado=True)


@given(parsers.parse('a fórmula de biblioteca "{expressao}" para a folha "{folha}" '
                     'do plano de {ano:d}'))
def formula_biblioteca(app, expressao, folha, ano):
    from fluxocaixa.models import RubricaFormula

    db = _db()
    db.session.add(RubricaFormula(seq_qualificador=_q(folha, ano).seq_qualificador,
                                  nom_formula="Biblioteca AB",
                                  dsc_formula_expressao=expressao, ind_status='A'))
    db.session.commit()


@given(parsers.parse('o bloco "{bloco}" do plano de {ano:d} pertence ao setor "{sigla}"'))
def bloco_no_setor(app, bloco, ano, sigla):
    from fluxocaixa.services.setor_previsao_service import criar_setor, marcar_recorte

    setor = criar_setor(f"Setor {sigla}", sigla)
    marcar_recorte(_q(bloco, ano).seq_qualificador, setor.seq_setor_previsao)


# ---------------------------------------------------------------------------
# Ações
# ---------------------------------------------------------------------------

@when(parsers.parse('calculo a projeção "{modelo}" de {ano:d} pela rota avulsa para '
                    '"{codigo}"'))
def calcula_avulsa(client, contexto, modelo, ano, codigo):
    resp = client.post('/simulador/calcular-projecao', json={
        'tipo_modelo': modelo,
        'seq_qualificador': _q(codigo, ano - 1).seq_qualificador,
        'num_periodos': 12, 'ano_base': ano,
        'config': {'periodo_meses': 12, 'fator_ajuste': 1.0,
                   'considerar_sazonalidade': True},
    })
    assert resp.status_code == 200, resp.text
    contexto["projecao"] = resp.json()["projecao"]


@when(parsers.parse('leio a série de treino do ano-base {ano:d} com janela de '
                    '{janela:d} anos para "{codigo}"'))
def le_serie(app, contexto, ano, janela, codigo):
    from fluxocaixa.services import modelos_economicos_service as modelos

    contexto["serie"] = modelos.obter_serie_do_ano_base(
        [_q(codigo, ano - 1).seq_qualificador], ano, janela)


@when(parsers.parse('o exercício {novo:d} é aberto a partir de {origem:d}'))
def abre_exercicio(app, novo, origem):
    from fluxocaixa.services.qualificador_service import abrir_exercicio

    abrir_exercicio(origem, novo, confirmado=True)


@when("executo o cenário")
def executa(cenario, contexto):
    from fluxocaixa.services.simulador_cenario_service import executar_simulacao

    contexto["resultado"] = executar_simulacao(cenario.seq_simulador_cenario)


@when(parsers.parse('leio a projeção de receita do cenário para {ano:d} pela porta '
                    'dos relatórios'))
def le_projecao(cenario, contexto, ano):
    from fluxocaixa.services.relatorio.dfc_projecao import projecao_por_qualificador

    contexto["leitura"], _ = projecao_por_qualificador(
        cenario.seq_simulador_cenario, ano, 'C')


# ---------------------------------------------------------------------------
# Verificações
# ---------------------------------------------------------------------------

@then(parsers.parse('os doze meses projetados valem "{valor}"'))
def doze_meses(contexto, valor):
    valores = [round(float(p["valor_projetado"]), 2) for p in contexto["projecao"]]
    assert valores == [float(valor)] * 12


@then(parsers.parse('a série tem {n:d} pontos, todos positivos'))
def serie_positiva(contexto, n):
    serie = contexto["serie"]
    assert len(serie) == n
    assert (serie["valor"] > 0).all(), serie["valor"].tolist()


@then(parsers.parse('a folha "{folha}" do plano de {ano:d} projeta "{valor}" no ano'))
def folha_projeta(contexto, folha, ano, valor):
    seq = _q(folha, ano).seq_qualificador
    total = Decimal(0)
    for chave in ("projecao_receita_detalhada", "projecao_despesa_detalhada"):
        df = contexto["resultado"].get(chave)
        if df is None or not len(df):
            continue
        linhas = df[df["seq_qualificador"] == seq]
        total += Decimal(str(round(float(linhas["valor_projetado"].sum()), 2)))
    assert total.quantize(Decimal("0.01")) == Decimal(valor)


@then(parsers.parse('o ajuste do cenário aponta para a folha "{folha}" do plano de {ano:d}'))
def ajuste_aponta(cenario, folha, ano):
    from fluxocaixa.models import CenarioAjuste, CenarioConfig

    config = CenarioConfig.query.filter_by(
        seq_simulador_cenario=cenario.seq_simulador_cenario).one()
    _db().session.expire_all()
    ajustes = CenarioAjuste.query.filter_by(seq_cenario_config=config.seq_cenario_config).all()
    assert [a.seq_qualificador for a in ajustes] == [_q(folha, ano).seq_qualificador]


@then(parsers.parse('a marcação do cenário continua na folha "{folha}" do plano de {ano:d}'))
def marcacao_continua(cenario, folha, ano):
    from fluxocaixa.models import CenarioMetodo

    _db().session.expire_all()
    marcacoes = CenarioMetodo.query.filter_by(
        seq_simulador_cenario=cenario.seq_simulador_cenario).all()
    assert [m.seq_qualificador for m in marcacoes] == [_q(folha, ano).seq_qualificador]


@then(parsers.parse('a folha "{folha}" do plano de {ano:d} soma "{valor}" na leitura'))
def leitura_soma(contexto, folha, ano, valor):
    seq = _q(folha, ano).seq_qualificador
    total = sum((v for (s, _mes), v in contexto["leitura"].items() if s == seq), Decimal(0))
    assert total.quantize(Decimal("0.01")) == Decimal(valor), contexto["leitura"]


@then(parsers.parse('a versão publicada continua gravada na folha "{folha}" do plano '
                    'de {ano:d}'))
def versao_intacta(contexto, folha, ano):
    from fluxocaixa.models import ProjecaoValor

    linhas = ProjecaoValor.query.filter_by(
        seq_projecao_versao=contexto["versao"].seq_projecao_versao).all()
    assert linhas
    assert {linha.seq_qualificador for linha in linhas} == {_q(folha, ano).seq_qualificador}


@then(parsers.parse('a folha "{folha}" do plano de {ano:d} tem a fórmula de biblioteca '
                    '"{expressao}"'))
def formula_copiada(folha, ano, expressao):
    from fluxocaixa.models import RubricaFormula

    formula = RubricaFormula.query.filter_by(
        seq_qualificador=_q(folha, ano).seq_qualificador, ind_status='A').one()
    assert formula.dsc_formula_expressao == expressao


@then(parsers.parse('alterar a fórmula de {novo:d} para "{nova}" mantém "{antiga}" '
                    'em {origem:d}'))
def formula_por_valor(novo, nova, antiga, origem):
    from fluxocaixa.models import RubricaFormula

    db = _db()
    folha_novo = _q("1.86.1", novo).seq_qualificador
    folha_origem = _q("1.86.1", origem).seq_qualificador
    RubricaFormula.query.filter_by(seq_qualificador=folha_novo).one() \
        .dsc_formula_expressao = nova
    db.session.commit()
    db.session.expire_all()
    assert RubricaFormula.query.filter_by(
        seq_qualificador=folha_origem).one().dsc_formula_expressao == antiga


@then(parsers.parse('o bloco "{bloco}" do plano de {ano:d} pertence ao setor "{sigla}"'))
def bloco_do_setor(bloco, ano, sigla):
    from fluxocaixa.models import SetorPrevisao

    setor = SetorPrevisao.query.filter_by(sgl_setor=sigla).one()
    assert _q(bloco, ano).seq_setor_previsao == setor.seq_setor_previsao
