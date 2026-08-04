"""Steps BDD — identidade dos itens na alteração (spec automacao-lancamentos R6).

`dat_ultima_execucao` é o marco que a F4.3 consome. Recriar os itens a cada save
zeraria esse marco e faria a limpeza cirúrgica virar recarga total.
"""
from datetime import date

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from ..conftest_extracao import garantir_sistema_origem
from .conftest_regra import (
    criar_mapeamento,
    garantir_qualificador,
    garantir_termos_padrao,
    sistema_por_sigla,
)

scenarios("../automacao-lancamentos/identidade_itens.feature")

REGRA_OK = "Unidade Gestora = '999001'"
DAT_EXEC = date(2026, 7, 1)


@pytest.fixture()
def contexto():
    return {}


@pytest.fixture(autouse=True)
def _mapeamentos_limpos(app):
    from fluxocaixa.models import ItemMapeamento, Mapeamento
    from fluxocaixa.models.base import db

    db.session.rollback()
    db.session.query(ItemMapeamento).delete()
    db.session.query(Mapeamento).delete()
    db.session.commit()


def _item_do_qualificador(mapeamento, num):
    from fluxocaixa.models.base import db

    db.session.expire_all()
    for item in mapeamento.itens:
        if item.qualificador.num_qualificador == num:
            return item
    return None


def _payload(item, **over):
    """Item existente → dict de POST (com a PK, que é o que dá identidade)."""
    base = {
        "seq_item_mapeamento": item.seq_item_mapeamento,
        "seq_qualificador": item.seq_qualificador,
        "txt_regra": item.txt_regra,
        "ind_inversao_sinal": item.ind_inversao_sinal,
    }
    base.update(over)
    return base


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


@given(parsers.parse('um mapeamento com um item já processado no qualificador "{num}"'))
def mapeamento_processado(app, contexto, num):
    from fluxocaixa.models.base import db

    q = garantir_qualificador(num)
    mapeamento = criar_mapeamento(2026, "SIS_X", [
        {"seq_qualificador": q.seq_qualificador, "txt_regra": REGRA_OK},
    ])
    # simula o que a F4.3 fará ao processar o item
    item = mapeamento.itens[0]
    item.dat_ultima_execucao = DAT_EXEC
    db.session.commit()

    contexto["mapeamento"] = mapeamento
    contexto["seq_mapeamento"] = mapeamento.seq_mapeamento
    contexto["seq_item"] = item.seq_item_mapeamento


@given(parsers.parse('um item ativo no qualificador "{num}"'))
def item_extra(app, contexto, num):
    from fluxocaixa.services.mapeamento_service import alterar_mapeamento

    q = garantir_qualificador(num)
    mapeamento = contexto["mapeamento"]
    itens = [_payload(i) for i in mapeamento.itens]
    itens.append({"seq_qualificador": q.seq_qualificador, "txt_regra": "Natureza = '1112'"})
    contexto["mapeamento"] = alterar_mapeamento(
        contexto["seq_mapeamento"], 2026,
        sistema_por_sigla("SIS_X").seq_sistema_origem,
        "Mapeamento 2026/1/SIS_X", itens,
    )


@given(parsers.parse('outro mapeamento {ano:d} com um item no qualificador "{num}"'))
def outro_mapeamento(app, contexto, ano, num):
    q = garantir_qualificador(num)
    outro = criar_mapeamento(ano, "SIS_X", [
        {"seq_qualificador": q.seq_qualificador, "txt_regra": REGRA_OK},
    ])
    contexto["item_alheio"] = outro.itens[0].seq_item_mapeamento
    contexto["seq_qualificador_alheio"] = q.seq_qualificador


# --------------------------------------------------------------------------
# Quando
# --------------------------------------------------------------------------

def _alterar(contexto, itens, dsc="Mapeamento 2026/1/SIS_X"):
    from fluxocaixa.services.mapeamento_service import alterar_mapeamento
    from fluxocaixa.services.validacao import RegraNegocioError

    try:
        contexto["mapeamento"] = alterar_mapeamento(
            contexto["seq_mapeamento"], 2026,
            sistema_por_sigla("SIS_X").seq_sistema_origem, dsc, itens,
        )
        contexto["erro"] = None
    except RegraNegocioError as exc:
        contexto["erro"] = exc.mensagem


@when("altero apenas a descrição do mapeamento, reenviando o item igual")
def altera_so_descricao(app, contexto):
    itens = [_payload(i) for i in contexto["mapeamento"].itens]
    _alterar(contexto, itens, dsc="Outra descrição")


@when(parsers.parse('altero a regra desse item para "{regra}"'))
def altera_regra(app, contexto, regra):
    itens = [_payload(i, txt_regra=regra) for i in contexto["mapeamento"].itens]
    _alterar(contexto, itens)


@when(parsers.parse('acrescento um item no qualificador "{num}"'))
def acrescenta_item(app, contexto, num):
    q = garantir_qualificador(num)
    itens = [_payload(i) for i in contexto["mapeamento"].itens]
    itens.append({"seq_qualificador": q.seq_qualificador, "txt_regra": "Natureza = '1112'"})
    _alterar(contexto, itens)


@when(parsers.parse('altero o mapeamento reenviando apenas o item do qualificador "{num}"'))
def altera_removendo(app, contexto, num):
    manter = _item_do_qualificador(contexto["mapeamento"], num)
    _alterar(contexto, [_payload(manter)])


@when("altero o mapeamento enviando um item que pertence ao outro mapeamento")
def altera_com_item_alheio(app, contexto):
    _alterar(contexto, [{
        "seq_item_mapeamento": contexto["item_alheio"],
        "seq_qualificador": contexto["seq_qualificador_alheio"],
        "txt_regra": REGRA_OK,
    }])


# --------------------------------------------------------------------------
# Então
# --------------------------------------------------------------------------

def _item_atual(contexto):
    from fluxocaixa.models import ItemMapeamento
    from fluxocaixa.models.base import db

    db.session.expire_all()
    return ItemMapeamento.query.get(contexto["seq_item"])


@then("o item mantém o mesmo identificador")
def item_mesmo_id(app, contexto):
    assert contexto.get("erro") is None, f"rejeitado: {contexto.get('erro')!r}"
    item = _item_atual(contexto)
    assert item is not None, "o item foi recriado (identificador perdido)"
    assert item.ind_status == 'A'


@then("o item mantém a data de última execução")
def item_mantem_marco(app, contexto):
    assert _item_atual(contexto).dat_ultima_execucao == DAT_EXEC


@then("o item não tem data de alteração")
def item_sem_alteracao(app, contexto):
    item = _item_atual(contexto)
    assert item.dat_alteracao is None, (
        f"carimbou dat_alteracao sem o item ter mudado: {item.dat_alteracao}"
    )


@then("o item tem data de alteração")
def item_com_alteracao(app, contexto):
    assert _item_atual(contexto).dat_alteracao is not None


@then(parsers.parse('o mapeamento tem {n:d} itens ativos'))
def mapeamento_n_ativos(app, contexto, n):
    from fluxocaixa.models.base import db

    db.session.expire_all()
    ativos = [i for i in contexto["mapeamento"].itens if i.ind_status == 'A']
    assert len(ativos) == n


@then(parsers.parse('o item do qualificador "{num}" não tem data de última execução'))
def item_novo_sem_marco(app, contexto, num):
    item = _item_do_qualificador(contexto["mapeamento"], num)
    assert item is not None and item.dat_ultima_execucao is None


@then(parsers.parse('o item do qualificador "{num}" fica inativo'))
def item_inativado(app, contexto, num):
    item = _item_do_qualificador(contexto["mapeamento"], num)
    assert item is not None, "o item foi apagado em vez de inativado"
    assert item.ind_status == 'I'


@then(parsers.parse('o item do qualificador "{num}" mantém a data de última execução'))
def item_inativo_mantem_marco(app, contexto, num):
    assert _item_do_qualificador(contexto["mapeamento"], num).dat_ultima_execucao == DAT_EXEC


@then(parsers.parse('a alteração é rejeitada com mensagem contendo "{trecho}"'))
def alteracao_rejeitada(contexto, trecho):
    assert contexto["erro"] is not None, "esperava rejeição"
    assert trecho.lower() in contexto["erro"].lower(), contexto["erro"]


@then("o item fica sem data de última execução")
def item_sem_marco(app, contexto):
    assert _item_atual(contexto).dat_ultima_execucao is None, (
        "o marco sobreviveu à alteração de conteúdo — o item nunca seria "
        "detectado como sujo se editado e processado no mesmo dia"
    )
