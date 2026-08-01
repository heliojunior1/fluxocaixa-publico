"""Steps BDD — detecção de item sujo e resync cirúrgico (spec R14)."""
import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from ..conftest_extracao import garantir_sistema_origem
from .conftest_processamento import (
    LINHAS_PADRAO,
    lancamentos_do_qualificador,
    limpar_estado_processamento,
    semear_staging,
    ultima_execucao_mapeamento,
)
from .conftest_regra import (
    criar_mapeamento,
    garantir_qualificador,
    garantir_termos_padrao,
    sistema_por_sigla,
)

scenarios("../automacao-lancamentos/resync.feature")


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
def staging(app, contexto, sigla, ano):
    semear_staging(sigla, f"Fonte {sigla}", LINHAS_PADRAO, ano=ano)
    contexto["sigla"] = sigla


@given(parsers.parse('um mapeamento com os itens "{n1}" em "{r1}" e "{n2}" em "{r2}"'))
def mapeamento_dois_itens(app, contexto, n1, r1, n2, r2):
    q1, q2 = garantir_qualificador(n1), garantir_qualificador(n2)
    mapeamento = criar_mapeamento(2026, "1", contexto["sigla"], [
        {"seq_qualificador": q1.seq_qualificador, "txt_regra": r1},
        {"seq_qualificador": q2.seq_qualificador, "txt_regra": r2},
    ])
    contexto["seq_mapeamento"] = mapeamento.seq_mapeamento


@given(parsers.parse('um mapeamento com o item "{num}" em "{regra}"'))
def mapeamento_um_item(app, contexto, num, regra):
    q = garantir_qualificador(num)
    mapeamento = criar_mapeamento(2026, "1", contexto["sigla"], [
        {"seq_qualificador": q.seq_qualificador, "txt_regra": regra},
    ])
    contexto["seq_mapeamento"] = mapeamento.seq_mapeamento


@given("um mapeamento com dois itens que casam com a mesma linha")
def mapeamento_conflito(app, contexto):
    q1, q2 = garantir_qualificador("1.1.1"), garantir_qualificador("1.1.2")
    mapeamento = criar_mapeamento(2026, "1", contexto["sigla"], [
        {"seq_qualificador": q1.seq_qualificador,
         "txt_regra": "Natureza começa com '11120000'"},
        {"seq_qualificador": q2.seq_qualificador,
         "txt_regra": "Unidade Gestora = '999001'"},
    ])
    contexto["seq_mapeamento"] = mapeamento.seq_mapeamento


@given(parsers.parse('que o item "{num}" nunca foi processado'))
def item_nunca_processado(app, contexto, num):
    assert _item(contexto, num).dat_ultima_execucao is None


@given("que já processei o mapeamento hoje")
@given("que já processei o mapeamento")
def ja_processei(app, contexto):
    from fluxocaixa.services.processamento_service import processar_mapeamento

    processar_mapeamento(contexto["seq_mapeamento"], disparo="MANUAL")
    contexto["lancs_antes"] = {
        num: {l.seq_lancamento for l in lancamentos_do_qualificador(num)}
        for num in ("1.1.1", "1.1.2")
    }


def _item(contexto, num):
    from fluxocaixa.models import Mapeamento
    from fluxocaixa.models.base import db

    db.session.expire_all()
    mapeamento = Mapeamento.query.get(contexto["seq_mapeamento"])
    for item in mapeamento.itens:
        if item.qualificador.num_qualificador == num:
            return item
    raise AssertionError(f"item {num} não encontrado")


def _payload(item, **over):
    dados = {
        "seq_item_mapeamento": item.seq_item_mapeamento,
        "seq_qualificador": item.seq_qualificador,
        "txt_regra": item.txt_regra,
        "ind_inversao_sinal": item.ind_inversao_sinal,
    }
    dados.update(over)
    return dados


def _alterar_e_processar(contexto, num, regra=None):
    from fluxocaixa.models import Mapeamento
    from fluxocaixa.services.mapeamento_service import alterar_mapeamento
    from fluxocaixa.services.processamento_service import processar_mapeamento

    mapeamento = Mapeamento.query.get(contexto["seq_mapeamento"])
    itens = []
    for item in mapeamento.itens:
        if regra is not None and item.qualificador.num_qualificador == num:
            itens.append(_payload(item, txt_regra=regra))
        else:
            itens.append(_payload(item))
    alterar_mapeamento(
        contexto["seq_mapeamento"], mapeamento.num_ano_exercicio, mapeamento.ind_tipo,
        sistema_por_sigla(contexto["sigla"]).seq_sistema_origem,
        mapeamento.dsc_mapeamento, itens,
    )
    contexto["execucao"] = processar_mapeamento(
        contexto["seq_mapeamento"], disparo="MANUAL")


@when(parsers.parse('altero a regra do item "{num}" para "{regra}" e processo'))
def altera_e_processa(app, contexto, num, regra):
    _alterar_e_processar(contexto, num, regra)


@when(parsers.parse('corrijo a regra do item "{num}" para "{regra}" e processo'))
def corrige_e_processa(app, contexto, num, regra):
    _alterar_e_processar(contexto, num, regra)


@when("salvo o mapeamento reenviando o item igual e processo")
def salva_igual_e_processa(app, contexto):
    _alterar_e_processar(contexto, None, None)


@when("processo o mapeamento")
def processa(app, contexto):
    from fluxocaixa.services.processamento_service import processar_mapeamento

    contexto["execucao"] = processar_mapeamento(
        contexto["seq_mapeamento"], disparo="MANUAL")


@then(parsers.parse('o qualificador "{num}" tem {n:d} lançamento'))
def qualificador_n(app, num, n):
    assert len(lancamentos_do_qualificador(num)) == n


@then(parsers.parse('os lançamentos do qualificador "{num}" permanecem intactos'))
def intactos(app, contexto, num):
    atuais = {l.seq_lancamento for l in lancamentos_do_qualificador(num)}
    assert atuais == contexto["lancs_antes"][num], (
        f"resync vazou para {num}: antes {contexto['lancs_antes'][num]}, agora {atuais}"
    )


@then(parsers.parse('o item "{num}" tem data de última execução'))
def item_carimbado(app, contexto, num):
    assert _item(contexto, num).dat_ultima_execucao is not None


@then("processar de novo não remove nenhum lançamento")
def reprocessar_nao_remove(app, contexto):
    from fluxocaixa.services.processamento_service import processar_mapeamento

    execucao = processar_mapeamento(contexto["seq_mapeamento"], disparo="MANUAL")
    assert execucao.qtd_lancamentos_removidos == 0, execucao.qtd_lancamentos_removidos


@then("nenhum lançamento foi removido")
def nada_removido(app, contexto):
    assert contexto["execucao"].qtd_lancamentos_removidos == 0, (
        "salvar sem mudar o item disparou resync — o item foi marcado sujo à toa"
    )


@then(parsers.parse('a linha que estava em erro vira lançamento no qualificador "{num}"'))
def linha_erro_vira_lancamento(app, num):
    from .conftest_processamento import linha_por_natureza

    linha = linha_por_natureza("11120000")
    assert linha.ind_status_processamento == '1', linha.ind_status_processamento
    assert any(l.seq_etl_staging == linha.seq_etl_staging
               for l in lancamentos_do_qualificador(num))


@when(parsers.parse('altero a regra do item "{num}" para "{regra}"'))
def altera_regra_sem_processar(app, contexto, num, regra):
    from fluxocaixa.models import Mapeamento
    from fluxocaixa.services.mapeamento_service import alterar_mapeamento

    mapeamento = Mapeamento.query.get(contexto["seq_mapeamento"])
    itens = [_payload(i, txt_regra=regra) if i.qualificador.num_qualificador == num
             else _payload(i) for i in mapeamento.itens]
    alterar_mapeamento(
        contexto["seq_mapeamento"], mapeamento.num_ano_exercicio, mapeamento.ind_tipo,
        sistema_por_sigla(contexto["sigla"]).seq_sistema_origem,
        mapeamento.dsc_mapeamento, itens,
    )


@then(parsers.parse('o item "{num}" fica sem data de última execução'))
def item_sem_marco(app, contexto, num):
    assert _item(contexto, num).dat_ultima_execucao is None, (
        "o marco sobreviveu à alteração — o item nunca seria detectado como sujo "
        "no mesmo dia"
    )
