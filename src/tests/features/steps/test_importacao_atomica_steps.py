"""Steps BDD — contexto no token e lote atômico (importacao-arquivos R7/R8).

Ilha 2067/2068. Import tardio de `fluxocaixa`.
"""
from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../importacao-arquivos/importacao_atomica.feature")

ORGAO = 70020


@pytest.fixture()
def contexto():
    return {"sessao": {}}


def _db():
    from fluxocaixa.models.base import db

    return db


def _limpar():
    from fluxocaixa.models import (
        ExecucaoEvento,
        ExecucaoOrcamentaria,
        Loa,
        Qualificador,
    )

    db = _db()
    db.session.rollback()
    for num in ("1.69.1", "2.69.1"):
        q = Qualificador.query.filter_by(num_qualificador=num).first()
        if q is not None:
            Loa.query.filter_by(seq_qualificador=q.seq_qualificador).delete()
    for doc in ExecucaoOrcamentaria.query.filter_by(num_ano=2067).all():
        ExecucaoEvento.query.filter_by(seq_execucao=doc.seq_execucao).delete()
        db.session.delete(doc)
    db.session.commit()


@pytest.fixture(autouse=True)
def _ilha(app):
    _limpar()
    yield
    _limpar()


def _garantir_qualificador(num, dsc):
    from fluxocaixa.models import Qualificador

    db = _db()
    partes = num.split(".")
    pai = None
    for i in range(1, len(partes) + 1):
        codigo = ".".join(partes[:i])
        q = Qualificador.query.filter_by(num_qualificador=codigo).first()
        if q is None:
            q = Qualificador(
                num_qualificador=codigo,
                dsc_qualificador=dsc if codigo == num else f"Nó {codigo}",
                cod_qualificador_pai=pai.seq_qualificador if pai else None,
                ind_status='A')
            db.session.add(q)
            db.session.commit()
        pai = q
    return pai


@given(parsers.parse('um qualificador folha de importação "{num}"'),
       target_fixture="qualificador")
def qualificador(app, num):
    return _garantir_qualificador(num, "Rubrica Importação Atômica")


@given(parsers.parse('um órgão de importação {cod:d} e um qualificador folha '
                     'de despesa "{num}"'), target_fixture="massa_execucao")
def massa_execucao(app, cod, num):
    from fluxocaixa.models import Orgao

    db = _db()
    orgao = Orgao.query.filter_by(cod_orgao=cod).first()
    if orgao is None:
        orgao = Orgao(cod_orgao=cod, nom_orgao=f"Órgão Importação {cod}",
                      ind_status='A', cod_pessoa_inclusao=1)
        db.session.add(orgao)
        db.session.commit()
    q = _garantir_qualificador(num, "Despesa Importação Atômica")
    return {"orgao": cod, "qualificador": q}


def _preview_loa(contexto, ano, valor):
    from fluxocaixa.services.preprocessamento import criar_preview

    csv = f"qualificador;valor\n1.69.1;{valor}\n".encode()
    token, preview = criar_preview(
        "loa", csv, f"loa-{ano}.csv", contexto["sessao"],
        contexto={"ano": ano})
    return token


@given(parsers.parse("um preview de LOA para o ano {ano:d} com valor {valor}"))
def preview_a(app, contexto, qualificador, ano, valor):
    contexto["token_a"] = _preview_loa(contexto, ano, valor)


@given(parsers.parse("um segundo preview de LOA para o ano {ano:d} com valor "
                     "{valor}"))
def preview_b(app, contexto, qualificador, ano, valor):
    contexto["token_b"] = _preview_loa(contexto, ano, valor)


def _preview_execucao(contexto, linhas_csv):
    from fluxocaixa.services.preprocessamento import criar_preview

    cabecalho = "estagio;numero;pai;orgao;qualificador;fonte;valor;data"
    csv = (cabecalho + "\n" + "\n".join(linhas_csv) + "\n").encode()
    token, preview = criar_preview(
        "execucao", csv, "execucao.csv", contexto["sessao"],
        contexto={"ano": 2067})
    contexto["token_execucao"] = token
    return preview


@given("um preview de execução 2067 com um empenho válido e uma liquidação "
       "de pai inexistente")
def preview_execucao_com_erro(app, contexto, massa_execucao):
    preview = _preview_execucao(contexto, [
        f"E;E2067-1;;{ORGAO};2.69.1;1.500;1000.00;2067-03-01",
        f"L;L2067-1;E-NAO-EXISTE;{ORGAO};2.69.1;1.500;400.00;2067-03-10",
    ])
    assert preview.total_erro == 0, "as duas linhas devem passar no preview"


@given("um preview de execução 2067 com um empenho e sua liquidação encadeada")
def preview_execucao_valido(app, contexto, massa_execucao):
    _preview_execucao(contexto, [
        f"E;E2067-2;;{ORGAO};2.69.1;1.500;1000.00;2067-03-01",
        f"L;L2067-2;E2067-2;{ORGAO};2.69.1;1.500;400.00;2067-03-10",
    ])


@when("confirmo o primeiro preview")
def confirma_primeiro(app, contexto):
    from fluxocaixa.services.preprocessamento import confirmar

    contexto["resultado"] = confirmar(contexto["token_a"], contexto["sessao"])


@when("confirmo o preview de execução")
def confirma_execucao(app, contexto):
    from fluxocaixa.services.preprocessamento import confirmar

    contexto["resultado"] = confirmar(
        contexto["token_execucao"], contexto["sessao"])


@when("inspeciono as classes dos adapters registrados")
def inspeciona_adapters(app, contexto):
    from fluxocaixa.services import preprocessamento_adapters as mod
    from fluxocaixa.services.preprocessamento import _ADAPTERS  # noqa: F401

    ofensores = []
    for nome in dir(mod):
        objeto = getattr(mod, nome)
        if not isinstance(objeto, type) or not nome.startswith("_Adapter"):
            continue
        for atributo in ("_ano", "_data", "_exercicio"):
            if hasattr(objeto, atributo):
                ofensores.append(f"{nome}.{atributo}")
    contexto["ofensores"] = ofensores


@then(parsers.parse('a LOA de {ano:d} para "{num}" vale {valor}'))
def loa_vale(app, ano, num, valor):
    from fluxocaixa.models import Loa, Qualificador

    _db().session.expire_all()
    q = Qualificador.query.filter_by(num_qualificador=num).first()
    registro = Loa.query.filter_by(
        num_ano=ano, seq_qualificador=q.seq_qualificador, ind_status='A').first()
    assert registro is not None, f"LOA de {ano} não gravada"
    assert registro.val_loa == Decimal(valor)


@then(parsers.parse('não existe LOA de {ano:d} para "{num}"'))
def loa_nao_existe(app, ano, num):
    from fluxocaixa.models import Loa, Qualificador

    q = Qualificador.query.filter_by(num_qualificador=num).first()
    registro = Loa.query.filter_by(
        num_ano=ano, seq_qualificador=q.seq_qualificador, ind_status='A').first()
    assert registro is None, (
        f"a confirmação do preview A gravou no ano {ano} — o contexto do "
        "preview B vazou (estado de classe compartilhado)")


@then("nenhum adapter guarda contexto em atributo de classe")
def sem_estado_de_classe(contexto):
    assert contexto["ofensores"] == [], contexto["ofensores"]


@then(parsers.parse("nenhum documento de execução de {ano:d} foi gravado"))
def nenhum_documento(app, ano):
    from fluxocaixa.models import ExecucaoOrcamentaria

    _db().session.expire_all()
    docs = ExecucaoOrcamentaria.query.filter_by(num_ano=ano, ind_status='A').all()
    assert docs == [], (
        f"{len(docs)} documentos gravados — o lote parcial entrou e o funil "
        "exibiria um estado que nunca existiu")


@then("o resultado reporta o erro da liquidação")
def erro_da_liquidacao(contexto):
    erros = contexto["resultado"].get("erros", [])
    assert erros, "nenhum erro reportado"
    assert any("E-NAO-EXISTE" in e or "pai" in e.lower() or "não encontrado" in e.lower()
               for e in erros), erros
    assert contexto["resultado"].get("sucesso") == 0


@then(parsers.parse("os {n:d} documentos de execução de {ano:d} foram gravados"))
def documentos_gravados(app, n, ano):
    from fluxocaixa.models import ExecucaoOrcamentaria

    _db().session.expire_all()
    docs = ExecucaoOrcamentaria.query.filter_by(num_ano=ano, ind_status='A').all()
    assert len(docs) == n, [d.num_documento for d in docs]


@then("o resultado reporta zero erros")
def zero_erros(contexto):
    assert contexto["resultado"].get("erros") == [], contexto["resultado"]
