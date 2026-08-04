"""Steps BDD — fonte de recursos no lançamento (F9.2).

Specs `automacao-lancamentos` R17 (estampagem no processamento) e
`fonte-recurso` R7 (porta manual + filtro). Reusa os helpers do
processamento (`conftest_processamento`) e do motor de regras
(`conftest_regra`). Ilha de datas 2035 na porta manual.
"""
from datetime import date
from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from ..conftest_extracao import garantir_sistema_origem
from .conftest_processamento import (
    limpar_estado_processamento,
    linha_por_natureza,
    semear_staging,
)
from .conftest_regra import (
    criar_mapeamento,
    garantir_qualificador,
    garantir_termos_padrao,
)

scenarios("../fonte-recurso/fonte_lancamento.feature")


@pytest.fixture()
def contexto():
    return {}


@pytest.fixture(autouse=True)
def _limpo(app):
    limpar_estado_processamento()


def _db():
    from fluxocaixa.models.base import db

    return db


def _fonte(codigo: str, vigencia: int):
    from fluxocaixa.models import FonteRecurso

    ident, fonte = codigo.split(".", 1)
    return FonteRecurso.query.filter_by(
        cod_identificador_exercicio=ident, cod_fonte_stn=fonte,
        num_exercicio_vigencia=vigencia, ind_status='A').first()


def _lancamento_do_qualificador(num):
    from fluxocaixa.models import Lancamento, Qualificador

    _db().session.expire_all()
    q = Qualificador.query.filter_by(num_qualificador=num).first()
    assert q is not None
    return Lancamento.query.filter_by(
        seq_qualificador=q.seq_qualificador, ind_status='A').first()


# --------------------------------------------------------------------------
# Dado
# --------------------------------------------------------------------------

@given("que estou autenticado como administrador")
def autenticado_admin(app, _admin_pronto):
    from fluxocaixa.auth.contexto import definir_usuario_corrente

    definir_usuario_corrente(777)


@given(parsers.parse('um sistema de origem "{sigla}" cadastrado'))
def sistema_cadastrado(app, sigla):
    garantir_sistema_origem(sigla)


@given("os termos de regra padrão cadastrados")
def termos_padrao(app):
    garantir_termos_padrao()


@given(parsers.parse('um qualificador folha "{num}"'))
def qualificador_folha(app, num):
    garantir_qualificador(num)


@given(parsers.parse('linhas na staging de "{sigla}" com o atributo de fonte "{valor}"'))
def staging_com_fonte(app, sigla, valor):
    semear_staging(sigla, f"Fonte {sigla}", [
        {"natureza": "11120000", "ug": "999001", "valor": "100.00",
         "fonte_recurso": valor},
    ])


@given(parsers.parse('linhas na staging de "{sigla}" sem atributo de fonte'))
def staging_sem_fonte(app, sigla):
    semear_staging(sigla, f"Fonte {sigla}", [
        {"natureza": "11120000", "ug": "999001", "valor": "100.00"},
    ])


@given(parsers.parse('o mapeamento 2026 de "{sigla}" com o item "{num}" e regra "{regra}"'))
def mapeamento_um_item(app, contexto, sigla, num, regra):
    q = garantir_qualificador(num)
    mapeamento = criar_mapeamento(2026, sigla, [
        {"seq_qualificador": q.seq_qualificador, "txt_regra": regra},
    ])
    contexto["seq_mapeamento"] = mapeamento.seq_mapeamento


@given(parsers.parse('a fonte "{codigo}" cadastrada na vigência {vigencia:d} como "{vinculada}"'))
def fonte_cadastrada(app, codigo, vigencia, vinculada):
    from fluxocaixa.services.fonte_recurso_service import criar_fonte

    _db().session.rollback()
    if _fonte(codigo, vigencia) is None:
        ident, fonte = codigo.split(".", 1)
        criar_fonte(ident, fonte, f"Fonte de teste {codigo}", vigencia,
                    vinculada='L' if vinculada == 'livre' else 'V')


@given("anoto o total de fontes do catálogo")
def anota_total(app, contexto):
    from fluxocaixa.models import FonteRecurso

    contexto["total_fontes"] = FonteRecurso.query.count()


def _criar_manual(num, valor, dat, seq_fonte):
    from fluxocaixa.domain.lancamento import LancamentoCreate
    from fluxocaixa.models import OrigemLancamento
    from fluxocaixa.services.lancamento_service import create_lancamento

    q = garantir_qualificador(num)
    origem = OrigemLancamento.query.filter_by(dsc_origem_lancamento='Manual').first()
    return create_lancamento(LancamentoCreate(
        dat_lancamento=date.fromisoformat(dat),
        seq_qualificador=q.seq_qualificador,
        val_lancamento=Decimal(valor),
        cod_tipo_lancamento='C',
        cod_origem_lancamento=origem.cod_origem_lancamento,
        seq_fonte_recurso=seq_fonte,
    ))


@given(parsers.parse('crio um lançamento manual de {valor} em "{num}" na data "{dat}" com a fonte "{codigo}" da vigência {vigencia:d}'))
@when(parsers.parse('crio um lançamento manual de {valor} em "{num}" na data "{dat}" com a fonte "{codigo}" da vigência {vigencia:d}'))
def manual_com_fonte(app, num, valor, dat, codigo, vigencia):
    fonte = _fonte(codigo, vigencia)
    assert fonte is not None
    _criar_manual(num, valor, dat, fonte.seq_fonte_recurso)


@given(parsers.parse('crio um lançamento manual de {valor} em "{num}" na data "{dat}" sem fonte'))
@when(parsers.parse('crio um lançamento manual de {valor} em "{num}" na data "{dat}" sem fonte'))
def manual_sem_fonte(app, num, valor, dat):
    _criar_manual(num, valor, dat, None)


# --------------------------------------------------------------------------
# Quando / Então
# --------------------------------------------------------------------------

@when("processo o mapeamento")
def processa(app, contexto):
    from fluxocaixa.services.processamento_service import processar_mapeamento

    processar_mapeamento(contexto["seq_mapeamento"], disparo="MANUAL")


@when(parsers.parse('listo os lançamentos de "{dat}" filtrando pela fonte "{codigo}" da vigência {vigencia:d}'))
def lista_filtrada(app, contexto, dat, codigo, vigencia):
    from fluxocaixa.services.lancamento_service import list_lancamentos

    fonte = _fonte(codigo, vigencia)
    ref = date.fromisoformat(dat)
    lancs, total = list_lancamentos(
        start_date=ref, end_date=ref,
        seq_fonte_recurso=fonte.seq_fonte_recurso)
    contexto["listagem"] = lancs
    contexto["data_listagem"] = ref


@then(parsers.parse('o lançamento do qualificador "{num}" referencia a fonte "{codigo}" da vigência {vigencia:d}'))
def lancamento_com_fonte(num, codigo, vigencia):
    lanc = _lancamento_do_qualificador(num)
    fonte = _fonte(codigo, vigencia)
    assert lanc is not None and fonte is not None
    assert lanc.seq_fonte_recurso == fonte.seq_fonte_recurso


@then(parsers.parse('o lançamento do qualificador "{num}" não referencia fonte alguma'))
@then(parsers.parse('o lançamento manual de "{num}" não referencia fonte alguma'))
def lancamento_sem_fonte(num):
    lanc = _lancamento_do_qualificador(num)
    assert lanc is not None and lanc.seq_fonte_recurso is None


@then(parsers.parse('o lançamento manual de "{num}" referencia a fonte "{codigo}" da vigência {vigencia:d}'))
def manual_referencia_fonte(num, codigo, vigencia):
    lanc = _lancamento_do_qualificador(num)
    fonte = _fonte(codigo, vigencia)
    assert lanc is not None and lanc.seq_fonte_recurso == fonte.seq_fonte_recurso


@then(parsers.parse('a fonte "{codigo}" da vigência {vigencia:d} existe vinculada e pendente de revisão'))
def fonte_pendente(codigo, vigencia):
    _db().session.expire_all()
    fonte = _fonte(codigo, vigencia)
    assert fonte is not None
    assert fonte.ind_vinculada == 'V' and fonte.ind_pendente_revisao == 'S'


@then(parsers.parse('a linha de natureza "{natureza}" está classificada'))
def linha_classificada(natureza):
    linha = linha_por_natureza(natureza)
    assert linha is not None and linha.ind_status_processamento == '1'


@then("o total de fontes do catálogo não mudou")
def total_nao_mudou(contexto):
    from fluxocaixa.models import FonteRecurso

    _db().session.expire_all()
    assert FonteRecurso.query.count() == contexto["total_fontes"]


@then(parsers.parse('a listagem traz {qtd:d} lançamento'))
def listagem_qtd(contexto, qtd):
    assert len(contexto["listagem"]) == qtd


@then(parsers.parse('listo os lançamentos de "{dat}" sem filtro de fonte traz {qtd:d} lançamentos'))
def lista_sem_filtro(app, dat, qtd):
    from fluxocaixa.services.lancamento_service import list_lancamentos

    ref = date.fromisoformat(dat)
    lancs, total = list_lancamentos(start_date=ref, end_date=ref)
    assert total == qtd
