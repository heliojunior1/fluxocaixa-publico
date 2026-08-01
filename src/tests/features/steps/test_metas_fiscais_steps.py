"""Steps BDD — metas fiscais por categoria explícita (spec relatorios R17–R19).

Ilha 2018, ramo `2.7`/`2.8` sob a raiz de despesa. A receita da RCL usa `1.7`,
livre na raiz de receita.
"""
from datetime import date
from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../relatorios/metas_fiscais.feature")

ANO = 2018
DIA = date(ANO, 6, 15)
RAMOS = ("2.7", "2.8", "1.7")


@pytest.fixture()
def contexto():
    return {}


def _db():
    from fluxocaixa.models.base import db

    return db


def _limpar():
    from fluxocaixa.models import CategoriaFiscal, Lancamento, Qualificador

    db = _db()
    db.session.rollback()
    filtro = Qualificador.num_qualificador.like(f"{RAMOS[0]}%")
    for ramo in RAMOS[1:]:
        filtro = filtro | Qualificador.num_qualificador.like(f"{ramo}%")
    quals = Qualificador.query.filter(filtro).all()
    if quals:
        seqs = [q.seq_qualificador for q in quals]
        Lancamento.query.filter(
            Lancamento.seq_qualificador.in_(seqs)
        ).delete(synchronize_session=False)
        db.session.commit()
        for q in sorted(quals, key=lambda x: -x.num_qualificador.count('.')):
            db.session.delete(q)
        db.session.commit()
    # limiares alterados por cenário voltam ao padrão do seed
    for sigla, limite in (("PESSOAL", 60), ("SAUDE", 15), ("EDUCACAO", 25)):
        cat = CategoriaFiscal.query.filter_by(txt_sigla=sigla).first()
        if cat is not None:
            cat.val_limite = Decimal(limite)
    db.session.commit()


@pytest.fixture(autouse=True)
def _ilha(app):
    _limpar()
    yield
    _limpar()


def _no(num, dsc=None, pai_num=None, sigla=None):
    from fluxocaixa.models import CategoriaFiscal, Qualificador

    db = _db()
    pai = (Qualificador.query.filter_by(num_qualificador=pai_num).first()
           if pai_num else None)
    q = Qualificador.query.filter_by(num_qualificador=num).first()
    if q is None:
        q = Qualificador(num_qualificador=num,
                         dsc_qualificador=dsc or f"Rubrica {num}",
                         ind_status='A')
        db.session.add(q)
    if dsc:
        q.dsc_qualificador = dsc
    q.cod_qualificador_pai = pai.seq_qualificador if pai else None
    if sigla:
        cat = CategoriaFiscal.query.filter_by(txt_sigla=sigla).first()
        assert cat is not None, f"categoria {sigla} não semeada"
        q.cod_categoria_fiscal = cat.seq_categoria_fiscal
    db.session.commit()
    return q


def _lancar(num_qualificador, valor, tipo):
    from fluxocaixa.models import Lancamento, Qualificador
    from fluxocaixa.services.dominio_lancamento import resolver_origem

    db = _db()
    q = Qualificador.query.filter_by(num_qualificador=num_qualificador).first()
    db.session.add(Lancamento(
        dat_lancamento=DIA, seq_qualificador=q.seq_qualificador,
        val_lancamento=Decimal(valor), cod_tipo_lancamento=tipo,
        cod_origem_lancamento=resolver_origem("Manual").cod_origem_lancamento,
        cod_pessoa_inclusao=1, ind_status='A',
    ))
    db.session.commit()


def _meta(contexto, nome):
    for m in contexto["metas"]:
        if m["nome"] == nome:
            return m
    raise AssertionError(
        f"meta '{nome}' não encontrada em {[m['nome'] for m in contexto['metas']]}")


# --------------------------------------------------------------------------
# Dado
# --------------------------------------------------------------------------

@given(parsers.parse('a folha "{num}" chamada "{dsc}" sem marcação'))
def dado_folha(app, contexto, num, dsc):
    _no(num, dsc=dsc)


@given(parsers.parse('a folha "{num}" chamada "{dsc}" marcada como "{sigla}"'))
def dado_folha_marcada(app, contexto, num, dsc, sigla):
    _no(num, dsc=dsc, sigla=sigla)


@given(parsers.parse('o bloco "{num}" chamado "{dsc}" marcado como "{sigla}"'))
def dado_bloco(app, contexto, num, dsc, sigla):
    _no(num, dsc=dsc, sigla=sigla)


@given(parsers.parse('a folha "{num}" chamada "{dsc}" sem marcação sob "{pai}"'))
def dado_folha_sob(app, contexto, num, dsc, pai):
    _no(num, dsc=dsc, pai_num=pai)


@given(parsers.parse('lançamentos de "{valor}" em "{num}" no ano'))
def dado_lancamentos(app, contexto, valor, num):
    from fluxocaixa.models.lancamento import TIPO_DEBITO

    _lancar(num, valor, TIPO_DEBITO)


@given(parsers.parse('receita realizada de "{valor}" no ano'))
def dado_receita(app, contexto, valor):
    from fluxocaixa.models.lancamento import TIPO_CREDITO

    _no("1.7", dsc="Receita da ilha 2018")
    _lancar("1.7", valor, TIPO_CREDITO)


@given(parsers.parse('a meta de superávit primário do ano informada como "{valor}"'))
def dado_meta_superavit(app, contexto, valor):
    from fluxocaixa.services.meta_fiscal_service import definir_meta_superavit

    definir_meta_superavit(ANO, Decimal(valor))
    contexto["meta_superavit"] = Decimal(valor)


# --------------------------------------------------------------------------
# Quando
# --------------------------------------------------------------------------

def _consultar(contexto):
    from fluxocaixa.services.relatorio.ldo_orcamento_service import get_ldo_orcamento_data

    _db().session.expire_all()
    contexto["metas"] = get_ldo_orcamento_data(ANO)["metas_fiscais"]


@when("consulto as metas fiscais do ano")
def quando_consulto(app, contexto):
    _consultar(contexto)


@when("consulto as metas fiscais do ano novamente")
def quando_consulto_de_novo(app, contexto):
    _consultar(contexto)


@when(parsers.parse('o piso da categoria "{sigla}" passa a "{valor}"'))
def quando_muda_piso(app, contexto, sigla, valor):
    from fluxocaixa.models import CategoriaFiscal

    db = _db()
    cat = CategoriaFiscal.query.filter_by(txt_sigla=sigla).first()
    cat.val_limite = Decimal(valor)
    db.session.commit()


# --------------------------------------------------------------------------
# Então
# --------------------------------------------------------------------------

@then(parsers.parse('a meta "{nome}" tem percentual "{esperado}"'))
def entao_percentual(contexto, nome, esperado):
    meta = _meta(contexto, nome)
    assert abs(float(meta["percentual"]) - float(esperado)) < 0.05, meta


@then(parsers.parse('a meta "{nome}" mede sobre "{base}"'))
def entao_base(contexto, nome, base):
    assert _meta(contexto, nome)["base"] == base, _meta(contexto, nome)


@then("nenhuma meta de aplicação tem percentual acima de zero")
def entao_nenhuma_aplicacao(contexto):
    acima = [
        m for m in contexto["metas"]
        if m["nome"].startswith("Aplicação") and float(m["percentual"]) > 0
    ]
    assert not acima, acima


@then(parsers.parse('a meta "{nome}" está fora do piso'))
def entao_fora_do_piso(contexto, nome):
    assert _meta(contexto, nome)["status"] != 'DENTRO DA META', _meta(contexto, nome)


@then(parsers.parse('a meta "{nome}" está dentro do piso'))
def entao_dentro_do_piso(contexto, nome):
    assert _meta(contexto, nome)["status"] == 'DENTRO DA META', _meta(contexto, nome)


@then("não existe meta de dívida consolidada")
def entao_sem_divida(contexto):
    nomes = [m["nome"] for m in contexto["metas"]]
    assert not any("Dívida" in n for n in nomes), nomes


@then(parsers.parse('a meta "{nome}" compara com "{valor}"'))
def entao_compara_com(contexto, nome, valor):
    meta = _meta(contexto, nome)
    esperado = float(valor)
    # o rótulo é formatado ("≥ R$ 1.5 K"); a comparação é sobre o valor bruto
    assert abs(float(meta["val_meta"]) - esperado) < 0.01, meta
