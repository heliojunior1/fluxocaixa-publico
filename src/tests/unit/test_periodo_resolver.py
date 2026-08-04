"""Varreduras do `periodo_resolver` (F6.3) — o que uma tabela BDD não cobre.

O BDD fixa as datas que a intuição erra (viradas ISO, dia 16, semana 53). Aqui
o alvo é outro: **varrer anos inteiros** e provar invariantes em todas as datas,
não em amostras escolhidas. Erro de calendário se esconde exatamente nos dias
que ninguém pensou em tabelar.
"""
from datetime import date, timedelta

import pytest


# ⚠️ NADA de `from fluxocaixa... import` no topo: a fixture `client` fixa o
# `DATABASE_URL` de teste ANTES de importar o pacote, e um import em tempo de
# COLETA amarra o engine ao banco errado — para a suíte inteira, não só para
# este arquivo. Estes testes não precisam de banco, mas a coleta é global.
@pytest.fixture(scope="module")
def pr():
    from fluxocaixa.services import periodo_resolver

    return periodo_resolver


@pytest.fixture(scope="module")
def RegraNegocioError():
    from fluxocaixa.services.validacao import RegraNegocioError as erro

    return erro


# 2020 é ano ISO longo (53 semanas), 2021 começa dentro da semana 53 de 2020 e
# 2024 é bissexto — os três casos que quebram implementação ingênua.
ANOS = (2020, 2021, 2024, 2026)

#: repetido aqui de propósito — o parametrize roda na COLETA, antes da fixture.
PERIODICIDADES = ("ANUAL", "MENSAL", "QUINZENAL", "SEMANAL")


def test_a_lista_local_de_periodicidades_nao_derivou_do_modulo(pr):
    """A cópia acima existe só porque o `parametrize` roda antes da fixture.

    Sem esta trava, uma periodicidade nova entraria no módulo e as varreduras
    simplesmente não a cobririam — passando verdes por omissão.
    """
    assert PERIODICIDADES == pr.PERIODICIDADES


def _todas_as_datas(ano, margem_dias=0):
    """Todos os dias do ano, opcionalmente com margem nos dois extremos.

    A margem existe para a semana ISO: a semana 1 de um ano pode começar em
    30/12 do anterior, e sem os dias vizinhos a varredura enxerga o período
    pela metade — e acusaria o resolver de um erro que é da varredura.
    """
    dia = date(ano, 1, 1) - timedelta(days=margem_dias)
    fim = date(ano, 12, 31) + timedelta(days=margem_dias)
    while dia <= fim:
        yield dia
        dia += timedelta(days=1)


@pytest.mark.parametrize("ano", ANOS)
@pytest.mark.parametrize("periodicidade", PERIODICIDADES)
def test_todo_dia_resolve_para_periodo_valido(ano, periodicidade, pr):
    """Nenhum dia do ano cai fora da faixa da sua periodicidade."""
    for dia in _todas_as_datas(ano):
        _ano, periodo = pr.resolver(dia, periodicidade)
        pr.validar_periodo(periodicidade, periodo)  # levanta se sair da faixa


@pytest.mark.parametrize("ano", ANOS)
@pytest.mark.parametrize("periodicidade", PERIODICIDADES)
def test_mes_do_periodo_e_o_mes_de_alguma_data_do_periodo(ano, periodicidade, pr):
    """O mês derivado tem de ser o mês de alguma data real do período.

    É o invariante que pega o erro clássico da semana ISO: usar o mês da
    segunda-feira (que pode estar no mês anterior) em vez do da quinta.
    """
    if periodicidade == pr.ANUAL:
        pytest.skip("ANUAL não tem mês único — devolve None por contrato")
    meses_vistos: dict[tuple[int, int], set[int]] = {}
    for dia in _todas_as_datas(ano, margem_dias=7):
        chave = tuple(pr.resolver(dia, periodicidade))
        meses_vistos.setdefault(chave, set()).add(dia.month)

    for (ano_p, periodo), meses in meses_vistos.items():
        derivado = pr.mes_do_periodo(periodicidade, ano_p, periodo)
        assert derivado in meses, (periodicidade, ano_p, periodo, derivado, meses)


@pytest.mark.parametrize("ano", ANOS)
@pytest.mark.parametrize("periodicidade", PERIODICIDADES)
def test_data_inicial_do_periodo_resolve_de_volta(ano, periodicidade, pr, RegraNegocioError):
    """Ida e volta: a primeira data de um período resolve para esse período."""
    for periodo in range(1, pr.MAXIMO_POR_PERIODICIDADE[periodicidade] + 1):
        try:
            inicio = pr.data_inicial_do_periodo(periodicidade, ano, periodo)
        except RegraNegocioError:
            # semana 53 num ano ISO de 52 — não existe, e a recusa é de
            # NEGÓCIO (mensagem pt-BR), não um ValueError cru virando 500
            assert periodicidade == pr.SEMANAL and periodo == 53
            continue
        assert tuple(pr.resolver(inicio, periodicidade)) == (ano, periodo)


@pytest.mark.parametrize("periodicidade", PERIODICIDADES)
def test_serie_de_datas_e_estritamente_crescente_e_sem_repeticao(periodicidade, pr):
    """A série da projeção não pode repetir nem voltar no tempo.

    Antes da F6.3 toda periodicidade usava passo mensal: uma série "semanal" de
    52 pontos cobria 52 MESES. O passo errado aparece aqui como espaçamento.
    """
    datas = pr.serie_de_datas(periodicidade, 2026, 30)
    assert len(datas) == 30
    assert datas == sorted(datas)
    assert len(set(datas)) == 30

    periodos = [tuple(pr.resolver(d, periodicidade)) for d in datas]
    assert len(set(periodos)) == 30, "duas datas caíram no mesmo período"


def test_serie_semanal_tem_passo_de_sete_dias(pr):
    datas = pr.serie_de_datas(pr.SEMANAL, 2026, 60)
    assert all((b - a) == timedelta(days=7) for a, b in zip(datas, datas[1:]))


def test_serie_quinzenal_da_a_volta_no_ano(pr):
    """Depois da 24ª quinzena o ano vira — não existe "quinzena 25"."""
    datas = pr.serie_de_datas(pr.QUINZENAL, 2026, 25)
    assert tuple(pr.resolver(datas[23], pr.QUINZENAL)) == (2026, 24)
    assert tuple(pr.resolver(datas[24], pr.QUINZENAL)) == (2027, 1)


@pytest.mark.parametrize("valor", [None, "", "DECENAL", "SEMANA", "12"])
def test_periodicidade_invalida_e_erro_de_negocio(valor, pr, RegraNegocioError):
    with pytest.raises(RegraNegocioError):
        pr.normalizar(valor)


@pytest.mark.parametrize("valor", ["mensal ", " Semanal", "QuInZeNaL"])
def test_periodicidade_e_normalizada_antes_de_validar(valor, pr):
    """Espaço e caixa não são erro de negócio — vêm de form e de banco."""
    assert pr.normalizar(valor) in pr.PERIODICIDADES


def test_rotulo_mensal_delega_ao_nome_do_mes(pr):
    assert pr.rotulo_periodo(pr.MENSAL, 2026, 3) is None
    assert pr.rotulo_periodo(pr.QUINZENAL, 2026, 7) == "Q7"
    assert pr.rotulo_periodo(pr.SEMANAL, 2020, 53) == "S53"
    assert pr.rotulo_periodo(pr.ANUAL, 2026, 1) == "2026"
