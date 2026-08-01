"""Steps BDD — classificação da staging em lançamentos (spec R12/R13)."""
from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from ..conftest_extracao import garantir_sistema_origem
from .conftest_processamento import (
    LINHAS_PADRAO,
    lancamentos_do_qualificador,
    limpar_estado_processamento,
    linha_por_natureza,
    semear_staging,
)
from .conftest_regra import (
    criar_mapeamento,
    garantir_qualificador,
    garantir_termos_padrao,
)

scenarios("../automacao-lancamentos/processamento.feature")


@pytest.fixture()
def contexto():
    return {}


@pytest.fixture(autouse=True)
def _limpo(app):
    limpar_estado_processamento()


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


@given(parsers.parse('linhas na staging de "{sigla}" no ano {ano:d}'))
def staging(app, sigla, ano):
    semear_staging(sigla, f"Fonte {sigla}", LINHAS_PADRAO, ano=ano)


@given("uma linha pendente de valor zero que casa com a regra")
def linha_zero(app, contexto):
    _, criadas = semear_staging(
        "SIS_P", "Fonte SIS_P Zero",
        [{"natureza": "11129999", "ug": "999001", "valor": "0.00"}])
    contexto["seq_linha_zero"] = criadas[0].seq_etl_staging


@given(parsers.parse('um lançamento manual no qualificador "{num}"'))
def lancamento_manual(app, contexto, num):
    from datetime import date

    from fluxocaixa.models import Lancamento
    from fluxocaixa.models.base import db
    from fluxocaixa.services.dominio_lancamento import resolver_origem, resolver_tipo

    q = garantir_qualificador(num)
    manual = Lancamento(
        dat_lancamento=date(2026, 7, 10), seq_qualificador=q.seq_qualificador,
        val_lancamento=Decimal("42.00"),
        cod_tipo_lancamento=resolver_tipo("Entrada").cod_tipo_lancamento,
        cod_origem_lancamento=resolver_origem("Manual").cod_origem_lancamento,
        cod_pessoa_inclusao=777, ind_status='A',
    )
    db.session.add(manual)
    db.session.commit()
    contexto["seq_manual"] = manual.seq_lancamento


def _criar_mapeamento(contexto, tipo, sigla, num, regra, inversao="0"):
    q = garantir_qualificador(num)
    mapeamento = criar_mapeamento(2026, tipo, sigla, [
        {"seq_qualificador": q.seq_qualificador, "txt_regra": regra,
         "ind_inversao_sinal": inversao},
    ])
    contexto["seq_mapeamento"] = mapeamento.seq_mapeamento
    return mapeamento


@given(parsers.parse('o mapeamento 2026 tipo "{tipo}" de "{sigla}" com o item "{num}" '
                     'e regra "{regra}"'))
def mapeamento_um_item(app, contexto, tipo, sigla, num, regra):
    _criar_mapeamento(contexto, tipo, sigla, num, regra)


@given(parsers.parse('o mapeamento 2026 tipo "{tipo}" de "{sigla}" com o item "{num}" '
                     'e regra "{regra}" com inversão'))
def mapeamento_com_inversao(app, contexto, tipo, sigla, num, regra):
    _criar_mapeamento(contexto, tipo, sigla, num, regra, inversao="1")


@given(parsers.parse('o mapeamento 2026 tipo "{tipo}" de "{sigla}" com dois itens '
                     'que casam com a mesma linha'))
def mapeamento_conflito(app, contexto, tipo, sigla):
    # a linha natureza=11120000/ug=999001 casa com AMBOS os itens
    q1 = garantir_qualificador("1.1.1")
    q2 = garantir_qualificador("1.1.2")
    mapeamento = criar_mapeamento(2026, tipo, sigla, [
        {"seq_qualificador": q1.seq_qualificador,
         "txt_regra": "Natureza começa com '11120000'"},
        {"seq_qualificador": q2.seq_qualificador,
         "txt_regra": "Unidade Gestora = '999001'"},
    ])
    contexto["seq_mapeamento"] = mapeamento.seq_mapeamento


@given("que já processei o mapeamento")
def ja_processei(app, contexto):
    from fluxocaixa.services.processamento_service import processar_mapeamento

    processar_mapeamento(contexto["seq_mapeamento"], disparo="MANUAL")


@when("processo o mapeamento")
def processa(app, contexto):
    from fluxocaixa.services.processamento_service import processar_mapeamento

    contexto["execucao"] = processar_mapeamento(
        contexto["seq_mapeamento"], disparo="MANUAL")


@then(parsers.parse('foram criados {n:d} lançamentos no qualificador "{num}"'))
def n_lancamentos(app, n, num):
    assert len(lancamentos_do_qualificador(num)) == n


@then(parsers.parse('continuam existindo {n:d} lançamentos no qualificador "{num}"'))
def continuam_n(app, n, num):
    assert len(lancamentos_do_qualificador(num)) == n


@then(parsers.parse('os lançamentos têm origem "{origem}" e tipo "{tipo}"'))
def origem_e_tipo(app, origem, tipo):
    from fluxocaixa.services.dominio_lancamento import resolver_origem, resolver_tipo

    lancs = lancamentos_do_qualificador("1.1.1")
    assert lancs, "nenhum lançamento criado"
    cod_origem = resolver_origem(origem).cod_origem_lancamento
    cod_tipo = resolver_tipo(tipo).cod_tipo_lancamento
    for lanc in lancs:
        assert lanc.cod_origem_lancamento == cod_origem
        assert lanc.cod_tipo_lancamento == cod_tipo


@then("os valores dos lançamentos são Decimal com 2 casas")
def valores_decimal(app):
    for lanc in lancamentos_do_qualificador("1.1.1"):
        val = Decimal(lanc.val_lancamento)
        assert val == val.quantize(Decimal("0.01"))


@then(parsers.parse('os lançamentos do qualificador "{num}" têm valores negativos'))
def valores_negativos(app, num):
    lancs = lancamentos_do_qualificador(num)
    assert lancs, "nenhum lançamento criado"
    # F6.1b: o valor gravado é sempre positivo e o sinal vive no tipo — a
    # asserção econômica ("saída de caixa") passa pela costura, não pela coluna.
    assert all(Decimal(l.valor_com_sinal) < 0 for l in lancs), [
        f"{l.cod_tipo_lancamento} {l.val_lancamento}" for l in lancs]


@then("nenhum lançamento foi criado para a linha em conflito")
def sem_lancamento_conflito(app, contexto):
    linha = linha_por_natureza("11120000")
    from fluxocaixa.models import Lancamento

    assert Lancamento.query.filter_by(
        seq_etl_staging=linha.seq_etl_staging).count() == 0


@then("a linha em conflito fica com erro citando os qualificadores")
def linha_conflito_erro(app):
    linha = linha_por_natureza("11120000")
    assert linha.ind_status_processamento == '2', linha.ind_status_processamento
    assert linha.dsc_erro and "1.1.1" in linha.dsc_erro and "1.1.2" in linha.dsc_erro, \
        linha.dsc_erro


@then(parsers.parse('a linha de natureza "{natureza}" continua pendente e sem erro'))
def linha_pendente(app, natureza):
    linha = linha_por_natureza(natureza)
    assert linha.ind_status_processamento == '0'
    assert not linha.dsc_erro


@then("cada lançamento criado referencia a linha de staging que o originou")
def rastro(app):
    lancs = lancamentos_do_qualificador("1.1.1")
    assert lancs, "nenhum lançamento criado"
    for lanc in lancs:
        assert lanc.seq_etl_staging is not None


@then("as linhas que geraram lançamento ficam processadas")
def linhas_processadas(app):
    from fluxocaixa.models import EtlStaging
    from fluxocaixa.models.base import db

    db.session.expire_all()
    for lanc in lancamentos_do_qualificador("1.1.1"):
        linha = EtlStaging.query.get(lanc.seq_etl_staging)
        assert linha.ind_status_processamento == '1'


@then("nenhum lançamento foi criado para a linha de valor zero")
def sem_lancamento_zero(app, contexto):
    from fluxocaixa.models import Lancamento
    from fluxocaixa.models.base import db

    db.session.expire_all()
    assert Lancamento.query.filter_by(
        seq_etl_staging=contexto["seq_linha_zero"]).count() == 0


@then("o lançamento manual permanece inalterado")
def manual_intacto(app, contexto):
    from fluxocaixa.models import Lancamento
    from fluxocaixa.models.base import db

    db.session.expire_all()
    manual = Lancamento.query.get(contexto["seq_manual"])
    assert manual is not None, "o processamento apagou um lançamento manual"
    assert manual.ind_status == 'A'
    assert Decimal(manual.val_lancamento) == Decimal("42.00")
    assert manual.seq_etl_staging is None
