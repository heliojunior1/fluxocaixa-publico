"""Steps BDD — movimento próprio de nó-pai no DFC (spec relatorios R20).

Ilha 2020, ramo `2.6.*` sob a raiz de despesa. Cenário sempre com versão
PUBLICADA: o caminho ao vivo importa libs de ML opcionais, e a suíte não pode
depender delas (mesma razão do stub em `test_dfc_projetado_steps.py`).
"""
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../relatorios/dfc_pai_proprio.feature")

#: ⚠️ ANO CORRENTE, não ilha no passado: `_recompor_pais` só roda com mês
#: aberto (`if meses_abertos:`), e num ano todo fechado o vazamento não se
#: manifesta — o teste passaria por vacuidade. Mesmo motivo da F5.2.
RAMO = "2.6"
CENARIO = "CEN_DFC_PROPRIO"


@pytest.fixture()
def contexto():
    return {}


def _db():
    from fluxocaixa.models.base import db

    return db


def _limpar():
    from fluxocaixa.models import (
        Lancamento, ProjecaoValor, ProjecaoVersao, Qualificador, SimuladorCenario,
    )

    db = _db()
    db.session.rollback()
    quals = Qualificador.query.filter(
        Qualificador.num_qualificador.like(f"{RAMO}%")
    ).all()
    if quals:
        seqs = [q.seq_qualificador for q in quals]
        Lancamento.query.filter(
            Lancamento.seq_qualificador.in_(seqs)
        ).delete(synchronize_session=False)
        ProjecaoValor.query.filter(
            ProjecaoValor.seq_qualificador.in_(seqs)
        ).delete(synchronize_session=False)
        db.session.commit()
        for q in sorted(quals, key=lambda x: -x.num_qualificador.count('.')):
            db.session.delete(q)
        db.session.commit()
    for c in SimuladorCenario.query.filter(
        SimuladorCenario.nom_cenario.like("CEN_DFC_PROPRIO%")
    ).all():
        for v in ProjecaoVersao.query.filter_by(
            seq_simulador_cenario=c.seq_simulador_cenario
        ).all():
            ProjecaoValor.query.filter_by(
                seq_projecao_versao=v.seq_projecao_versao
            ).delete(synchronize_session=False)
            db.session.delete(v)
        db.session.delete(c)
    db.session.commit()


@pytest.fixture(autouse=True)
def _ilha(app):
    _limpar()
    yield
    _limpar()


def _qual(num, pai_num=None):
    from fluxocaixa.models import Qualificador

    db = _db()
    pai = (Qualificador.query.filter_by(num_qualificador=pai_num).first()
           if pai_num else None)
    q = Qualificador.query.filter_by(num_qualificador=num).first()
    if q is None:
        q = Qualificador(num_qualificador=num,
                         dsc_qualificador=f"Rubrica DFC {num}",
                         ind_status='A')
        db.session.add(q)
    if pai is not None:
        q.cod_qualificador_pai = pai.seq_qualificador
    db.session.commit()
    return q


def _mes_anterior() -> date:
    hoje = date.today()
    if hoje.month == 1:
        pytest.skip("sem mês fechado no ano corrente em janeiro")
    return (hoje.replace(day=1) - timedelta(days=1)).replace(day=10)


def _lancar(num, valor, dia):
    from fluxocaixa.models import Lancamento
    from fluxocaixa.models.lancamento import TIPO_DEBITO
    from fluxocaixa.services.dominio_lancamento import resolver_origem

    db = _db()
    q = _qual(num)
    db.session.add(Lancamento(
        dat_lancamento=dia, seq_qualificador=q.seq_qualificador,
        val_lancamento=Decimal(valor), cod_tipo_lancamento=TIPO_DEBITO,
        cod_origem_lancamento=resolver_origem("Manual").cod_origem_lancamento,
        cod_pessoa_inclusao=1, ind_status='A',
    ))
    db.session.commit()


def _cenario_publicado(contexto, projecoes=(), mes=None):
    """Cenário com versão PUBLICADA. `projecoes` = [(num_qualificador, valor)]."""
    from fluxocaixa.models import ProjecaoValor, ProjecaoVersao, SimuladorCenario

    db = _db()
    cenario = SimuladorCenario.query.filter_by(nom_cenario=CENARIO).first()
    if cenario is None:
        cenario = SimuladorCenario(
            nom_cenario=CENARIO, dsc_cenario="R20", ano_base=date.today().year,
            num_periodos=12, cod_periodicidade='MENSAL',
            cod_metodo_base='MANUAL', ind_status='A',
            dat_criacao=date.today(), cod_pessoa_inclusao=1,
        )
        db.session.add(cenario)
        db.session.commit()
    versao = ProjecaoVersao(
        seq_simulador_cenario=cenario.seq_simulador_cenario,
        nom_versao="v1 R20", dat_versao=datetime.now(), ind_publicado='S',
    )
    db.session.add(versao)
    db.session.flush()
    for num, valor in projecoes:
        db.session.add(ProjecaoValor(
            seq_projecao_versao=versao.seq_projecao_versao,
            seq_qualificador=_qual(num).seq_qualificador,
            cod_tipo='D', ano=date.today().year,
            num_periodo=mes or date.today().month,
            val_projetado=Decimal(valor),
        ))
    db.session.commit()
    contexto["cenario"] = cenario
    return cenario


def _achar(nos, numero):
    """Procura o nó do código na árvore do DFC, em profundidade."""
    for no in nos:
        if str(no.get("number")) == numero:
            return no
        achado = _achar(no.get("children") or [], numero)
        if achado is not None:
            return achado
    return None


def _linha_propria(no):
    """A linha de movimento próprio entre os filhos, se existir."""
    for filho in (no.get("children") or []):
        if filho.get("proprio"):
            return filho
    return None


# --------------------------------------------------------------------------
# Dado
# --------------------------------------------------------------------------

@given(parsers.parse('o qualificador "{num}" com o filho "{filho}"'))
def dado_pai_com_filho(app, contexto, num, filho):
    _qual(num)
    _qual(filho, pai_num=num)


@given(parsers.parse('o qualificador folha "{num}" sem filhos'))
def dado_folha(app, contexto, num):
    _qual(num)


@given(parsers.parse('lançamentos próprios de "{valor}" em "{num}" no mês anterior ao corrente'))
def dado_lancamento_proprio(app, contexto, valor, num):
    dia = _mes_anterior()
    contexto["mes_anterior"] = dia.month
    _lancar(num, valor, dia)


@given(parsers.parse('lançamentos de "{valor}" em "{num}" no mês anterior ao corrente'))
def dado_lancamento(app, contexto, valor, num):
    dia = _mes_anterior()
    contexto["mes_anterior"] = dia.month
    _lancar(num, valor, dia)


@given("um cenário publicado para o ano corrente")
def dado_cenario(app, contexto):
    _cenario_publicado(contexto)


@given(parsers.parse('um cenário publicado projetando "{valor}" para "{num}" no mês corrente'))
def dado_cenario_projetando(app, contexto, valor, num):
    _cenario_publicado(contexto, projecoes=[(num, valor)])


@given(parsers.parse('que "{num}" ganha o filho "{filho}" depois da publicação'))
def dado_ganha_filho_depois(app, contexto, num, filho):
    _qual(filho, pai_num=num)


# --------------------------------------------------------------------------
# Quando
# --------------------------------------------------------------------------

def _consultar(contexto, estrategia):
    from fluxocaixa.services.relatorio.dfc_service import get_dfc_data

    _db().session.expire_all()
    cenario = contexto.get("cenario")
    dados = get_dfc_data(
        "ano", date.today().year, None, list(range(1, 13)), estrategia,
        cenario.seq_simulador_cenario if cenario is not None else None,
    )
    contexto.setdefault("arvores", {})[estrategia] = dados["dre_data"]
    contexto["arvore"] = dados["dre_data"]


@when(parsers.parse('consulto o DFC do ano corrente na estratégia "{estrategia}"'))
def quando_consulto(app, contexto, estrategia):
    _consultar(contexto, estrategia)


@when(parsers.parse('abro o detalhamento da linha de movimento próprio de "{num}"'))
def quando_abro_detalhe(app, contexto, num):
    from fluxocaixa.services.relatorio.dfc_service import get_dfc_eventos

    _consultar(contexto, "realizado")
    no = _achar(contexto["arvore"], num)
    linha = _linha_propria(no)
    assert linha is not None, f"{num} não tem linha de movimento próprio"
    contexto["eventos"] = get_dfc_eventos(
        linha["id"], "ano", contexto["mes_anterior"], str(date.today().year),
        "realizado", None, proprio=True,
    )


# --------------------------------------------------------------------------
# Então
# --------------------------------------------------------------------------

@then(parsers.parse('o nó "{num}" exibe o mesmo valor no mês anterior nas duas estratégias'))
def entao_mesmo_valor_mes_anterior(contexto, num):
    """A comparação é na COLUNA do mês FECHADO.

    Somar o ano inteiro não serviria: nos meses abertos o projetado substitui o
    realizado por previsão pura — por desenho da F5.2. O que não pode acontecer
    é o mês fechado perder a parcela própria do pai na recomposição.
    """
    idx = contexto["mes_anterior"] - 1
    valores = {}
    for estrategia, arvore in contexto["arvores"].items():
        no = _achar(arvore, num)
        assert no is not None, f"{num} não encontrado em {estrategia}"
        valores[estrategia] = round(no["values"][idx], 2)
    assert len(set(valores.values())) == 1, valores


@then(parsers.parse('o nó "{num}" tem uma linha de movimento próprio'))
def entao_tem_linha(contexto, num):
    no = _achar(contexto["arvore"], num)
    assert no is not None, num
    assert _linha_propria(no) is not None, \
        [f.get("name") for f in (no.get("children") or [])]


@then(parsers.parse('o nó "{num}" não tem linha de movimento próprio'))
def entao_sem_linha(contexto, num):
    no = _achar(contexto["arvore"], num)
    assert no is not None, num
    assert _linha_propria(no) is None, _linha_propria(no)


@then(parsers.parse('o total do nó "{num}" é a soma dos seus filhos'))
def entao_soma_dos_filhos(contexto, num):
    no = _achar(contexto["arvore"], num)
    for i in range(len(no["values"])):
        soma = sum(f["values"][i] for f in no["children"])
        assert abs(no["values"][i] - soma) < 0.01, (i, no["values"][i], soma)


@then(parsers.parse('o nó "{num}" exibe "{valor}" na coluna do mês corrente'))
def entao_valor_mes_corrente(contexto, num, valor):
    no = _achar(contexto["arvore"], num)
    assert no is not None, num
    idx = date.today().month - 1
    assert abs(abs(no["values"][idx]) - float(valor)) < 0.01, \
        (no["values"][idx], valor)


@then(parsers.parse('vejo apenas lançamentos que somam "{valor}"'))
def entao_eventos_somam(contexto, valor):
    eventos = contexto["eventos"]
    itens = eventos.get("eventos") or eventos.get("items") or []
    total = sum(abs(float(e.get("valor", 0))) for e in itens)
    assert abs(total - float(valor)) < 0.01, (total, itens)
