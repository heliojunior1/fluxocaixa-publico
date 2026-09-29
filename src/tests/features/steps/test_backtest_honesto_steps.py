"""Steps BDD — backtest mede o que a produção faz (spec previsao R16).

Ramo "8.8", ilhas 2081–2084, isolado por `qualificadores_ids`. Cada folha
nasce sob um pai do mesmo exercício — o backtest só enxerga folhas que têm
ancestral. Import tardio de `fluxocaixa`.
"""
from datetime import date
from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../previsao/backtest_honesto.feature")

RAMO = "8.8"


@pytest.fixture()
def contexto():
    return {}


def _limpar():
    from fluxocaixa.models import Lancamento, Qualificador
    from fluxocaixa.models.base import db

    db.session.rollback()
    quals = Qualificador.query.filter(
        Qualificador.num_qualificador.like(f"{RAMO}%")).all()
    seqs = [q.seq_qualificador for q in quals]
    if seqs:
        Lancamento.query.filter(Lancamento.seq_qualificador.in_(seqs)).delete(
            synchronize_session=False)
    for q in sorted(quals, key=lambda x: -len(x.num_qualificador)):
        db.session.delete(q)
    db.session.commit()


@pytest.fixture(autouse=True)
def _ilha(app):
    _limpar()
    yield
    _limpar()


def _folha(ano, raiz_pai=None, raiz_folha=None):
    """Pai "8.8" + folha "8.8.1" no exercício `ano`."""
    from fluxocaixa.models import Qualificador
    from fluxocaixa.models.base import db

    pai = Qualificador(num_qualificador=RAMO, dsc_qualificador="Bloco Backtest",
                       num_ano_exercicio=ano, cod_rubrica_raiz=raiz_pai,
                       ind_status="A")
    db.session.add(pai)
    db.session.commit()
    folha = Qualificador(num_qualificador=f"{RAMO}.1",
                         dsc_qualificador="Folha Backtest",
                         cod_qualificador_pai=pai.seq_qualificador,
                         num_ano_exercicio=ano, cod_rubrica_raiz=raiz_folha,
                         ind_status="A")
    db.session.add(folha)
    db.session.commit()
    return pai, folha


def _lancar_ano(q, ano, valor, tipo="Entrada"):
    from fluxocaixa.models import Lancamento
    from fluxocaixa.models.base import db
    from fluxocaixa.services.dominio_lancamento import resolver_origem, resolver_tipo

    for mes in range(1, 13):
        db.session.add(Lancamento(
            dat_lancamento=date(ano, mes, 15), seq_qualificador=q.seq_qualificador,
            val_lancamento=Decimal(str(valor)),
            cod_tipo_lancamento=resolver_tipo(tipo).cod_tipo_lancamento,
            cod_origem_lancamento=resolver_origem("Manual").cod_origem_lancamento,
            cod_pessoa_inclusao=1, ind_status="A"))
    db.session.commit()


def _anos(texto):
    return [int(a) for a in texto.replace(" e ", ",").split(",")]


# ----------------------------------------------------------------- dados

@given(parsers.parse("uma folha de despesa com {valor} por mês de {a1:d} a {a2:d}"),
       target_fixture="folhas")
def folha_despesa(valor, a1, a2):
    _, folha = _folha(a2)
    for ano in range(a1, a2 + 1):
        _lancar_ano(folha, ano, valor, "Saída")
    return [folha]


@given(parsers.parse("uma folha de receita com {v1} por mês em {a1:d} e {v2} por "
                     "mês em {a2:d}"), target_fixture="folhas")
def folha_receita_dois_anos(v1, a1, v2, a2):
    _, folha = _folha(a2)
    _lancar_ano(folha, a1, v1)
    _lancar_ano(folha, a2, v2)
    return [folha]


@given(parsers.parse("uma folha de receita com {v1} por mês em {a1:d}, {v2} em "
                     "{a2:d}, {v3} em {a3:d} e {v4} em {a4:d}"),
       target_fixture="folhas")
def folha_receita_quatro_anos(v1, a1, v2, a2, v3, a3, v4, a4):
    _, folha = _folha(a4)
    for valor, ano in ((v1, a1), (v2, a2), (v3, a3), (v4, a4)):
        _lancar_ano(folha, ano, valor)
    return [folha]


@given("a mesma folha de receita nos planos de 2083 e 2084, com a mesma raiz e "
       "histórico", target_fixture="folhas")
def folha_dois_planos():
    pai_a, folha_a = _folha(2083)
    _, folha_b = _folha(2084, raiz_pai=pai_a.cod_rubrica_raiz,
                        raiz_folha=folha_a.cod_rubrica_raiz)
    for ano in (2082, 2083):
        _lancar_ano(folha_a, ano, "1234.56")
    return [folha_a, folha_b]


# ----------------------------------------------------------------- ações

def _executar(contexto, folhas, modelos, treino, teste, **kwargs):
    from fluxocaixa.services.backtest_service import executar_backtest

    contexto["resultado"] = executar_backtest(
        anos_treino=_anos(treino), anos_teste=_anos(teste), modelos=modelos,
        qualificadores_ids=[f.seq_qualificador for f in folhas], **kwargs)


@when(parsers.parse("executo o backtest com média histórica treinando em "
                    "{treino} e testando {teste}"))
def backtest_media(contexto, folhas, treino, teste):
    _executar(contexto, folhas, ["MEDIA_HISTORICA"], treino, teste)


@when(parsers.parse("executo o backtest com média histórica das duas linhas "
                    "treinando em {treino} e testando {teste}"))
def backtest_duas_linhas(contexto, folhas, treino, teste):
    _executar(contexto, folhas, ["MEDIA_HISTORICA"], treino, teste)


@when(parsers.parse("executo o backtest com média histórica e crescimento, mês "
                    "de referência {mes:d}, treinando em {treino} e testando "
                    "{teste}"))
def backtest_com_crescimento(contexto, folhas, mes, treino, teste):
    _executar(contexto, folhas, ["MEDIA_HISTORICA", "CRESCIMENTO_ANO"], treino,
              teste, mes_referencia=mes)


# ---------------------------------------------------------- verificações

def _filho(contexto):
    filhos = contexto["resultado"]["resultados_filho"]
    assert len(filhos) == 1, filhos
    return filhos[0]


def _detalhe(contexto, modelo, ano):
    detalhes = _filho(contexto)["modelos"][modelo]["detalhes_por_ano"]
    return next(d for d in detalhes if d["ano_teste"] == ano)


@then(parsers.parse("o erro percentual da média histórica é {mape}"))
def mape_media(contexto, mape):
    assert _filho(contexto)["modelos"]["MEDIA_HISTORICA"]["mape"] == float(mape)


@then(parsers.parse("a projeção de {ano:d} não é zero"))
def projecao_nao_zero(contexto, ano):
    projecao = _detalhe(contexto, "MEDIA_HISTORICA", ano)["projecao"]
    assert sum(projecao.values()) > 0, projecao


@then(parsers.parse("o crescimento é medido apenas nos meses {m1:d} a {m2:d}"))
def crescimento_meses(contexto, m1, m2):
    intra = _filho(contexto)["intra_ano"]["CRESCIMENTO_ANO"]
    for detalhe in intra["detalhes_por_ano"]:
        assert detalhe["meses_avaliados"] == list(range(m1, m2 + 1)), detalhe


@then("o crescimento aparece na reprojeção intra-ano")
def crescimento_intra(contexto):
    filho = _filho(contexto)
    assert "CRESCIMENTO_ANO" in filho["intra_ano"]
    assert "CRESCIMENTO_ANO" not in filho["modelos"]


@then("o melhor modelo não é o crescimento")
def melhor_nao_crescimento(contexto):
    assert _filho(contexto)["melhor_modelo"] != "CRESCIMENTO_ANO"


@then("o ranking geral não contém o crescimento")
def ranking_sem_crescimento(contexto):
    ranking = contexto["resultado"]["ranking_geral"]["ranking"]
    assert all(r["modelo"] != "CRESCIMENTO_ANO" for r in ranking), ranking


@then(parsers.parse("a projeção de janeiro comparada com {ano:d} é {valor}"))
def projecao_janeiro(contexto, ano, valor):
    projecao = _detalhe(contexto, "MEDIA_HISTORICA", ano)["projecao"]
    assert round(projecao["1"], 2) == float(valor), projecao


@then("a rubrica aparece uma única vez no resultado")
def uma_vez(contexto):
    _filho(contexto)
