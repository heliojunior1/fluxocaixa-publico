"""Steps BDD — DFC com estratégia Projetado (spec relatorios R9–R13).

Ataque na camada de serviço (`get_dfc_data`/`get_dfc_eventos`); a página é
coberta pelo Playwright. Isolamento: anos 2034+ para projeção (2031–2033 são
das ilhas dos KPIs; o seed demo vive em 2022–2026); versões/valores são
semeados direto em `flc_projecao_versao`/`flc_projecao_valor` (sem ML).
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../relatorios/dfc_projetado.feature")

ROTULO_SINTETICA = "Projeção do cenário (não detalhada)"


@pytest.fixture()
def contexto():
    return {}


def _db():
    from fluxocaixa.models.base import db

    return db


# --------------------------------------------------------------------------
# Helpers de massa
# --------------------------------------------------------------------------

def _qualificador(num: str):
    from fluxocaixa.models import Qualificador

    db = _db()
    db.session.rollback()
    existente = Qualificador.query.filter_by(num_qualificador=num).first()
    if existente:
        return existente
    partes = num.split(".")
    pai = _qualificador(".".join(partes[:-1])) if len(partes) > 1 else None
    q = Qualificador(
        num_qualificador=num,
        dsc_qualificador=f"Qualificador DFC {num}",
        cod_qualificador_pai=pai.seq_qualificador if pai else None,
    )
    db.session.add(q)
    db.session.commit()
    return q


def _lancamento_receita(qual_num: str, valor: str, dat: date):
    from fluxocaixa.models import Lancamento
    from fluxocaixa.services.dominio_lancamento import (
        TIPO_ENTRADA,
        resolver_origem,
        resolver_tipo,
    )

    db = _db()
    db.session.add(Lancamento(
        dat_lancamento=dat,
        seq_qualificador=_qualificador(qual_num).seq_qualificador,
        val_lancamento=Decimal(valor),
        cod_tipo_lancamento=resolver_tipo(TIPO_ENTRADA).cod_tipo_lancamento,
        cod_origem_lancamento=resolver_origem("Manual").cod_origem_lancamento,
        cod_pessoa_inclusao=1,
        ind_status='A',
    ))
    db.session.commit()


def _cenario(nome: str, periodicidade: str = 'MENSAL', ano_base: int = 2033):
    from fluxocaixa.models import SimuladorCenario

    db = _db()
    cenario = SimuladorCenario.query.filter_by(nom_cenario=nome).first()
    if cenario is None:
        cenario = SimuladorCenario(
            nom_cenario=nome,
            dsc_cenario=f"Cenário DFC {nome}",
            ano_base=ano_base,
            num_periodos=12,
            cod_periodicidade=periodicidade,
            ind_status='A',
        )
        db.session.add(cenario)
        db.session.commit()
    return cenario


def _versao(cenario, publicada: bool = True):
    from datetime import datetime

    from fluxocaixa.models import ProjecaoVersao

    db = _db()
    ordem = contador = ProjecaoVersao.query.filter_by(
        seq_simulador_cenario=cenario.seq_simulador_cenario
    ).count()
    versao = ProjecaoVersao(
        seq_simulador_cenario=cenario.seq_simulador_cenario,
        nom_versao=f"v{contador + 1} {cenario.nom_cenario}",
        dat_versao=datetime(2026, 1, 1, 12, 0, 0) + timedelta(days=ordem),
        ind_publicado='S' if publicada else 'N',
    )
    db.session.add(versao)
    db.session.commit()
    return versao


def _ultima_publicada(cenario):
    from fluxocaixa.models import ProjecaoVersao

    return (
        ProjecaoVersao.query.filter_by(
            seq_simulador_cenario=cenario.seq_simulador_cenario,
            ind_publicado='S',
        )
        .order_by(ProjecaoVersao.dat_versao.desc(),
                  ProjecaoVersao.seq_projecao_versao.desc())
        .first()
    )


def _valores(versao, seq_qualificador, cod_tipo: str, ano: int,
             valores_por_periodo: dict[int, str]):
    """Grava por PERÍODO (F6.3). Nos cenários MENSAL destes testes o período
    é o próprio mês; no ANUAL é sempre 1."""
    from fluxocaixa.models import ProjecaoValor

    db = _db()
    for num_periodo, valor in valores_por_periodo.items():
        db.session.add(ProjecaoValor(
            seq_projecao_versao=versao.seq_projecao_versao,
            seq_qualificador=seq_qualificador,
            cod_tipo=cod_tipo,
            ano=ano,
            num_periodo=num_periodo,
            val_projetado=Decimal(valor),
        ))
    db.session.commit()


def _publicada_com_mensal(nome_cenario, qual_num, valor, ano,
                          nova_versao=False, cod_tipo='C'):
    cenario = _cenario(nome_cenario)
    versao = _versao(cenario) if nova_versao or _ultima_publicada(cenario) is None \
        else _ultima_publicada(cenario)
    seq_qual = _qualificador(qual_num).seq_qualificador if qual_num else None
    _valores(versao, seq_qual, cod_tipo, ano, {m: valor for m in range(1, 13)})
    return cenario


def _get_dfc(contexto, periodo, ano, mes=None, estrategia='projetado',
             cenario=None):
    from fluxocaixa.services.relatorio.dfc_service import get_dfc_data
    from fluxocaixa.services.validacao import RegraNegocioError

    cenario_id = cenario.seq_simulador_cenario if cenario is not None else None
    try:
        contexto["dfc"] = get_dfc_data(
            periodo, ano, mes, list(range(1, 13)), estrategia, cenario_id
        )
    except RegraNegocioError as erro:
        contexto["erro"] = erro
    return contexto.get("dfc")


def _find_node(nodes, num: str):
    for node in nodes:
        if str(node["number"]) == num:
            return node
        achado = _find_node(node["children"], num)
        if achado:
            return achado
    return None


def _no(contexto, num: str) -> dict:
    node = _find_node(contexto["dfc"]["dre_data"], num)
    assert node is not None, f"qualificador {num} ausente da árvore do DFC"
    return node


def _sintetica(contexto, raiz_num: str) -> dict:
    raiz = _no(contexto, raiz_num)
    filhos = [f for f in raiz["children"] if f["name"] == ROTULO_SINTETICA]
    assert filhos, f"linha sintética ausente sob a raiz {raiz_num}"
    return filhos[0]


def _dec(v) -> Decimal:
    return Decimal(str(v)).quantize(Decimal("0.01"))


# --------------------------------------------------------------------------
# Dado
# --------------------------------------------------------------------------

@given(parsers.parse('um qualificador folha de receita "{num}" com lançamento de "{valor}" em "{dat}"'))
def qual_com_lancamento(app, num, valor, dat):
    _lancamento_receita(num, valor, date.fromisoformat(dat))


@given(parsers.parse('o qualificador "{num}" com lançamento de "{valor}" em "{dat}"'))
def qual_lancamento_extra(app, num, valor, dat):
    _lancamento_receita(num, valor, date.fromisoformat(dat))


@given(parsers.parse('um qualificador folha de receita "{num}" ativo'))
def qual_ativo(app, num):
    _qualificador(num)


@given(parsers.parse('um qualificador folha de receita "{num}" inativado com lançamento de "{valor}" em "{dat}"'))
def qual_inativo_com_lancamento(app, num, valor, dat):
    _lancamento_receita(num, valor, date.fromisoformat(dat))
    db = _db()
    q = _qualificador(num)
    q.ind_status = 'I'
    db.session.commit()


@given(parsers.parse('um qualificador folha de receita "{num}" com lançamento de "{valor}" no mês anterior ao corrente'))
def qual_lancamento_mes_anterior(app, contexto, num, valor):
    hoje = date.today()
    if hoje.month == 1:
        pytest.skip("sem mês fechado no ano corrente em janeiro")
    anterior = hoje.replace(day=1) - timedelta(days=1)
    contexto["mes_anterior"] = anterior.month
    _lancamento_receita(num, valor, anterior.replace(day=10))


@given(parsers.parse('um cenário "{nome}" com versão publicada projetando "{valor}" por mês para "{qual}" em "{ano}"'))
def cenario_publicado_mensal(app, nome, valor, qual, ano):
    _publicada_com_mensal(nome, qual, valor, int(ano))


@given(parsers.parse('um cenário "{nome}" com versão publicada projetando "{valor}" por mês para "{qual}" no ano corrente'))
def cenario_publicado_ano_corrente(app, nome, valor, qual):
    _publicada_com_mensal(nome, qual, valor, date.today().year)


@given(parsers.parse('a versão publicada do cenário "{nome}" também projeta "{valor}" por mês para "{qual}" em "{ano}"'))
def versao_projeta_tambem(app, nome, valor, qual, ano):
    cenario = _cenario(nome)
    versao = _ultima_publicada(cenario)
    _valores(versao, _qualificador(qual).seq_qualificador, 'C', int(ano),
             {m: valor for m in range(1, 13)})


@given(parsers.parse('o cenário "{nome}" ganha nova versão publicada projetando "{valor}" por mês para "{qual}" em "{ano}"'))
def nova_versao_publicada(app, nome, valor, qual, ano):
    _publicada_com_mensal(nome, qual, valor, int(ano), nova_versao=True)


@given(parsers.parse('um cenário manual "{nome}" com ano-base "{ano}" e apenas versão rascunho'))
def cenario_com_rascunho(app, monkeypatch, nome, ano):
    cenario = _cenario(nome, ano_base=int(ano))
    _versao(cenario, publicada=False)

    # O fallback ao vivo chama executar_simulacao, que importa libs de ML
    # opcionais (XGBoost etc.) — a suíte não pode depender delas. Stub
    # determinístico no mesmo padrão dos testes de projeção
    # (test_projecao_historico.py): o que se testa aqui é o CAMINHO do
    # fallback (flag ao_vivo + normalização), não os modelos.
    import pandas as pd

    from fluxocaixa.services import simulador_cenario_service

    def _simulacao_stub(seq):
        df = pd.DataFrame({
            "data": [date(2034, m, 1) for m in range(1, 13)],
            "valor_projetado": [100.0] * 12,
        })
        return {
            "projecao_receita": df,
            "projecao_despesa": pd.DataFrame({"data": [], "valor_projetado": []}),
            "projecao_receita_detalhada": None,
            "projecao_despesa_detalhada": None,
        }

    monkeypatch.setattr(simulador_cenario_service, "executar_simulacao",
                        _simulacao_stub)


@given(parsers.parse('um cenário ANUAL "{nome}" com ano-base "{ano}" e versão publicada projetando o total anual "{valor}" para "{qual}" em "{ano_proj}"'))
def cenario_anual_publicado(app, nome, ano, valor, qual, ano_proj):
    cenario = _cenario(nome, periodicidade='ANUAL', ano_base=int(ano))
    versao = _ultima_publicada(cenario) or _versao(cenario)
    _valores(versao, _qualificador(qual).seq_qualificador, 'C', int(ano_proj),
             {1: valor})


@given(parsers.parse('um cenário ANUAL "{nome}" com ano-base "{ano}" e versão publicada projetando o total anual agregado "{valor}" de receita em "{ano_proj}"'))
def cenario_anual_agregado(app, nome, ano, valor, ano_proj):
    cenario = _cenario(nome, periodicidade='ANUAL', ano_base=int(ano))
    versao = _ultima_publicada(cenario) or _versao(cenario)
    _valores(versao, None, 'C', int(ano_proj), {1: valor})


@given(parsers.parse('um cenário "{nome}" com versão publicada projetando "{valor}" por mês agregado de receita em "{ano}"'))
def cenario_agregado_receita(app, nome, valor, ano):
    _publicada_com_mensal(nome, None, valor, int(ano), cod_tipo='C')


@given(parsers.parse('a versão publicada do cenário "{nome}" também projeta "{valor}" por mês agregado de despesa em "{ano}"'))
def versao_agregada_despesa(app, nome, valor, ano):
    cenario = _cenario(nome)
    versao = _ultima_publicada(cenario)
    _valores(versao, None, 'D', int(ano), {m: valor for m in range(1, 13)})


# --------------------------------------------------------------------------
# Quando
# --------------------------------------------------------------------------

@when(parsers.parse('consulto o DFC de "{ano}" na visão anual com estratégia "{estrategia}"'))
def consulta_anual_estrategia(app, contexto, ano, estrategia):
    _get_dfc(contexto, 'ano', int(ano), estrategia=estrategia)


@when(parsers.parse('consulto o DFC projetado de "{ano}" sem cenário'))
def consulta_sem_cenario(app, contexto, ano):
    _get_dfc(contexto, 'ano', int(ano))


@when(parsers.parse('consulto o DFC projetado do mês "{ano_mes}" com o cenário "{nome}"'))
def consulta_mensal(app, contexto, ano_mes, nome):
    ano, mes = [int(x) for x in ano_mes.split("-")]
    _get_dfc(contexto, 'mes', ano, mes=mes, cenario=_cenario(nome))


@when(parsers.parse('consulto o DFC projetado de "{ano}" na visão anual com o cenário "{nome}"'))
def consulta_anual(app, contexto, ano, nome):
    _get_dfc(contexto, 'ano', int(ano), cenario=_cenario(nome))


@when(parsers.parse('consulto o DFC projetado do ano corrente na visão anual com o cenário "{nome}"'))
def consulta_anual_corrente(app, contexto, nome):
    _get_dfc(contexto, 'ano', date.today().year, cenario=_cenario(nome))


@when(parsers.parse('abro os eventos projetados da folha "{qual}" no mês "{mes}" de "{ano}" com o cenário "{nome}"'))
def abre_eventos_projetados(app, contexto, qual, mes, ano, nome):
    from fluxocaixa.services.relatorio.dfc_service import get_dfc_eventos

    cenario = _cenario(nome)
    seq = _qualificador(qual).seq_qualificador
    contexto["eventos"] = get_dfc_eventos(
        seq, 'ano', int(mes), str(ano), 'projetado',
        cenario.seq_simulador_cenario,
    )


# --------------------------------------------------------------------------
# Então
# --------------------------------------------------------------------------

def _todas_flags(nodes):
    for node in nodes:
        yield from node["proj"]
        yield from _todas_flags(node["children"])


@then("nenhuma célula do DFC está marcada como projetada")
def nenhuma_projetada(contexto):
    assert not any(_todas_flags(contexto["dfc"]["dre_data"]))


@then("o DFC não informa origem de projeção")
def sem_origem(contexto):
    assert contexto["dfc"].get("projecao_origem") is None


@then(parsers.parse('recebo erro de negócio do DFC mencionando "{trecho}"'))
def erro_negocio(contexto, trecho):
    assert "erro" in contexto, "esperava RegraNegocioError, mas a consulta passou"
    assert trecho.lower() in str(contexto["erro"]).lower()


@then(parsers.parse('a folha "{num}" soma "{valor}" nas colunas do mês'))
def folha_soma_mes(contexto, num, valor):
    node = _no(contexto, num)
    assert _dec(sum(node["values"][:-1])) == Decimal(valor)
    assert _dec(node["values"][-1]) == Decimal(valor)  # coluna TOTAIS


@then(parsers.parse('a folha "{num}" exibe "{valor}" na coluna do mês "{mes}" marcada como projetada'))
@then(parsers.parse('o nó pai "{num}" exibe "{valor}" na coluna do mês "{mes}"'))
def no_exibe_na_coluna(contexto, num, valor, mes):
    node = _no(contexto, num)
    idx = int(mes) - 1
    assert _dec(node["values"][idx]) == Decimal(valor), f"values={node['values']}"


@then(parsers.parse('a folha "{num}" exibe "{valor}" na coluna do mês anterior sem marcação'))
def folha_mes_anterior(contexto, num, valor):
    node = _no(contexto, num)
    idx = contexto["mes_anterior"] - 1
    assert _dec(node["values"][idx]) == Decimal(valor)
    assert node["proj"][idx] is False


@then(parsers.parse('a folha "{num}" exibe "{valor}" na coluna do mês corrente marcada como projetada'))
def folha_mes_corrente(contexto, num, valor):
    node = _no(contexto, num)
    idx = date.today().month - 1
    assert _dec(node["values"][idx]) == Decimal(valor)
    assert node["proj"][idx] is True


@then(parsers.parse('a origem da projeção é a versão publicada, sem cálculo ao vivo'))
def origem_publicada(contexto):
    origem = contexto["dfc"]["projecao_origem"]
    assert origem is not None and origem["ao_vivo"] is False
    assert origem["nom_versao"]


@then("a origem da projeção é cálculo ao vivo")
def origem_ao_vivo(contexto):
    origem = contexto["dfc"]["projecao_origem"]
    assert origem is not None and origem["ao_vivo"] is True


@then(parsers.parse('as colunas de dia da folha "{num}" estão zeradas'))
def dias_zerados(contexto, num):
    node = _no(contexto, num)
    assert all(_dec(v) == Decimal("0.00") for v in node["values"][:-1]), node["values"]


@then(parsers.parse('a coluna TOTAIS da folha "{num}" exibe "{valor}" marcada como projetada'))
def totais_projetado(contexto, num, valor):
    assert contexto["dfc"]["headers"][-1] == "TOTAIS"
    node = _no(contexto, num)
    assert _dec(node["values"][-1]) == Decimal(valor)
    assert node["proj"][-1] is True


@then(parsers.parse('o total do DFC na coluna do mês "{mes}" é "{valor}"'))
@then(parsers.parse('o total do DFC na coluna do mês "{mes}" inclui os "{valor}"'))
def total_coluna(contexto, mes, valor):
    idx = int(mes) - 1
    assert _dec(contexto["dfc"]["totals"][idx]) == Decimal(valor)


@then(parsers.parse('o saldo final do DFC na coluna do mês "{mes}" reflete o projetado'))
def saldo_final_reflete(contexto, mes):
    idx = int(mes) - 1
    dfc = contexto["dfc"]
    esperado = _dec(dfc["saldos_banco_anterior"][idx]) + _dec(dfc["totals"][idx])
    assert _dec(dfc["saldos_banco_final"][idx]) == esperado


@then("os eventos informam a origem da projeção citando a versão publicada")
def eventos_origem(contexto):
    eventos = contexto["eventos"]["eventos"]
    assert len(eventos) == 1, f"esperava 1 item informativo, veio {eventos}"
    assert eventos[0]["tipo"] == "Projetado"
    assert "versão" in eventos[0]["descricao"].lower()


@then("nenhum lançamento é listado")
def sem_lancamentos(contexto):
    eventos = contexto["eventos"]["eventos"]
    assert all(e["tipo"] == "Projetado" for e in eventos)


@then(parsers.parse('a raiz Receita tem a linha sintética "{rotulo}"'))
def raiz_receita_sintetica(contexto, rotulo):
    assert _sintetica(contexto, "1")["name"] == rotulo


@then(parsers.parse('a raiz Despesa tem a linha sintética "{rotulo}"'))
def raiz_despesa_sintetica(contexto, rotulo):
    assert _sintetica(contexto, "2")["name"] == rotulo


@then(parsers.parse('a linha sintética de receita exibe "{valor}" na coluna do mês "{mes}" marcada como projetada'))
def sintetica_receita_projetada(contexto, valor, mes):
    node = _sintetica(contexto, "1")
    idx = int(mes) - 1
    assert _dec(node["values"][idx]) == Decimal(valor)
    assert node["proj"][idx] is True


@then(parsers.parse('a linha sintética de receita exibe "{valor}" na coluna do mês "{mes}"'))
def sintetica_receita_valor(contexto, valor, mes):
    node = _sintetica(contexto, "1")
    assert _dec(node["values"][int(mes) - 1]) == Decimal(valor)


@then(parsers.parse('a linha sintética de despesa exibe "{valor}" na coluna do mês "{mes}" marcada como projetada'))
def sintetica_despesa_projetada(contexto, valor, mes):
    node = _sintetica(contexto, "2")
    idx = int(mes) - 1
    assert _dec(node["values"][idx]) == Decimal(valor)
    assert node["proj"][idx] is True
