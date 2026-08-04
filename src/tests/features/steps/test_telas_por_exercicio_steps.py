"""Steps BDD — leitura e telas por exercício (cadastros-nucleo R28, F10.4).

Imports de app sempre tardios (isolamento de banco da suíte).
"""
import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../cadastros-nucleo/telas_por_exercicio.feature")

ANOS_ILHA = (2078, 2079, 2080)


@pytest.fixture()
def contexto():
    return {}


def _db():
    from fluxocaixa.models.base import db

    return db


def _limpar():
    from fluxocaixa.models import Lancamento, Qualificador

    db = _db()
    db.session.rollback()
    quals = Qualificador.query.filter(
        Qualificador.num_ano_exercicio.in_(ANOS_ILHA)).all()
    if quals:
        seqs = [q.seq_qualificador for q in quals]
        Lancamento.query.filter(
            Lancamento.seq_qualificador.in_(seqs)
        ).delete(synchronize_session=False)
        db.session.commit()
        # filhos antes dos pais
        for q in sorted(quals, key=lambda x: -x.num_qualificador.count('.')):
            db.session.delete(q)
        db.session.commit()


@pytest.fixture(autouse=True)
def _ilha(client):
    _limpar()
    yield
    _limpar()


@given(parsers.parse(
    'um plano no exercício {ano:d} com a folha de receita "{dsc_folha}"'))
def dado_plano(ano, dsc_folha, contexto):
    from fluxocaixa.services import qualificador_service as svc

    raiz_r = svc.create_qualificador(
        "1", f"Receita Ilha {ano}", num_ano_exercicio=ano)
    svc.create_qualificador(
        "1.1", dsc_folha, cod_qualificador_pai=raiz_r.seq_qualificador,
        num_ano_exercicio=ano)
    raiz_d = svc.create_qualificador(
        "2", f"Despesa Ilha {ano}", num_ano_exercicio=ano)
    svc.create_qualificador(
        "2.1", f"Despesa Folha {ano}",
        cod_qualificador_pai=raiz_d.seq_qualificador, num_ano_exercicio=ano)
    contexto.setdefault("planos", []).append(ano)


@when(parsers.parse('resolvo o plano do ano {ano:d}'))
def quando_resolvo(ano, contexto):
    from fluxocaixa.services.qualificador_service import (
        resolver_exercicio_do_plano,
    )

    contexto["resolvido"] = resolver_exercicio_do_plano(ano)


@when(parsers.parse('abro a tela de qualificadores no exercício {ano:d}'))
def quando_abro_tela(ano, contexto, client):
    resposta = client.get(f"/qualificadores?exercicio={ano}")
    assert resposta.status_code == 200
    contexto["html"] = resposta.text


@when(parsers.parse(
    'cadastro pela tela a rubrica "{num}" chamada "{dsc}" no exercício {ano:d}'))
def quando_cadastro_pela_tela(num, dsc, ano, contexto, client):
    resposta = client.post("/qualificadores/add", data={
        "num_qualificador": num,
        "dsc_qualificador": dsc,
        "cod_qualificador_pai": "",
        "num_ano_exercicio": str(ano),
    }, follow_redirects=False)
    assert resposta.status_code in (302, 303), resposta.text[:500]


@when(parsers.parse('gero o DFC anual de {ano:d}'))
def quando_gero_dfc(ano, contexto):
    from fluxocaixa.services.relatorio.dfc_service import get_dfc_data

    contexto["dfc"] = get_dfc_data(
        periodo="ano", ano_selecionado=ano, mes_selecionado=None,
        meses_selecionados=list(range(1, 13)), estrategia="realizado",
        cenario_selecionado_id=None)


@then(parsers.parse('o exercício resolvido é {ano:d}'))
def entao_resolvido(ano, contexto):
    assert contexto["resolvido"] == ano


@then(parsers.parse('a tela lista "{presente}" e não lista "{ausente}"'))
def entao_tela_lista(presente, ausente, contexto):
    assert presente in contexto["html"]
    assert ausente not in contexto["html"]


@then(parsers.parse('a rubrica "{dsc}" existe no exercício {ano:d}'))
def entao_rubrica_existe(dsc, ano):
    from fluxocaixa.models import Qualificador

    q = Qualificador.query.filter_by(
        dsc_qualificador=dsc, num_ano_exercicio=ano).first()
    assert q is not None


def _descricoes(nos):
    descricoes = []
    for no in nos:
        descricoes.append(no.get("name") or no.get("dsc") or "")
        descricoes.extend(_descricoes(no.get("children", [])))
    return descricoes


@then(parsers.parse('a árvore do DFC contém "{presente}" e não contém "{ausente}"'))
def entao_arvore_dfc(presente, ausente, contexto):
    dados = contexto["dfc"].get("dre_data") or contexto["dfc"].get("data") or []
    descricoes = " | ".join(_descricoes(dados))
    assert presente in descricoes, descricoes
    assert ausente not in descricoes, descricoes
