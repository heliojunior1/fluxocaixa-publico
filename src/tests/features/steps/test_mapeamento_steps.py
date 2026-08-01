"""Steps BDD — cadastro de mapeamento e itens (spec automacao-lancamentos R6)."""
import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from ..conftest_extracao import garantir_sistema_origem
from .conftest_regra import (
    criar_mapeamento,
    garantir_qualificador,
    garantir_termos_padrao,
    mapeamento_por_chave,
)

scenarios("../automacao-lancamentos/mapeamento.feature")

REGRA_OK = "Unidade Gestora = '999001'"


@pytest.fixture()
def contexto():
    return {}


@pytest.fixture(autouse=True)
def _mapeamentos_limpos(app):
    """O banco persiste entre cenários do módulo; sem isso a checagem de
    duplicidade do cenário anterior mascara a validação que cada cenário testa."""
    from fluxocaixa.models import ItemMapeamento, Mapeamento
    from fluxocaixa.models.base import db

    db.session.rollback()
    db.session.query(ItemMapeamento).delete()
    db.session.query(Mapeamento).delete()
    db.session.commit()


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


@given(parsers.parse('um qualificador "{num}" com filhos ativos'))
def qualificador_com_filhos(app, num):
    pai = garantir_qualificador(num)
    garantir_qualificador(f"{num}.9", pai=pai)


@given(parsers.parse('o mapeamento {ano:d} tipo "{tipo}" origem "{origem}" cadastrado'))
def mapeamento_existente(app, ano, tipo, origem):
    q = garantir_qualificador("1.1.1")
    criar_mapeamento(ano, tipo, origem, [
        {"seq_qualificador": q.seq_qualificador, "txt_regra": REGRA_OK},
    ])


def _criar(contexto, ano, tipo, origem, itens):
    from fluxocaixa.services.validacao import RegraNegocioError

    try:
        contexto["mapeamento"] = criar_mapeamento(ano, tipo, origem, itens)
        contexto["erro"] = None
    except RegraNegocioError as exc:
        contexto["erro"] = exc.mensagem


@when(parsers.parse('crio o mapeamento {ano:d} tipo "{tipo}" origem "{origem}" '
                    'com um item no qualificador "{num}" e regra "{regra}"'))
def cria_com_item(app, contexto, ano, tipo, origem, num, regra):
    q = garantir_qualificador(num)
    _criar(contexto, ano, tipo, origem, [
        {"seq_qualificador": q.seq_qualificador, "txt_regra": regra},
    ])


@when(parsers.parse('crio o mapeamento {ano:d} tipo "{tipo}" origem "{origem}" sem itens'))
def cria_sem_itens(app, contexto, ano, tipo, origem):
    _criar(contexto, ano, tipo, origem, [])


@when(parsers.parse('crio o mapeamento {ano:d} tipo "{tipo}" origem "{origem}" '
                    'com dois itens no mesmo qualificador "{num}"'))
def cria_qualificador_repetido(app, contexto, ano, tipo, origem, num):
    q = garantir_qualificador(num)
    _criar(contexto, ano, tipo, origem, [
        {"seq_qualificador": q.seq_qualificador, "txt_regra": REGRA_OK},
        {"seq_qualificador": q.seq_qualificador, "txt_regra": "Natureza = '1112'"},
    ])


@when(parsers.parse('crio o mapeamento {ano:d} tipo "{tipo}" origem "{origem}" '
                    'com um item no qualificador "{num}" com inversão de sinal'))
def cria_com_inversao(app, contexto, ano, tipo, origem, num):
    q = garantir_qualificador(num)
    _criar(contexto, ano, tipo, origem, [
        {"seq_qualificador": q.seq_qualificador, "txt_regra": REGRA_OK,
         "ind_inversao_sinal": "1"},
    ])


@then(parsers.parse('o mapeamento {ano:d} tipo "{tipo}" origem "{origem}" '
                    'existe ativo com {n:d} item'))
def mapeamento_ok(contexto, ano, tipo, origem, n):
    assert contexto.get("erro") is None, f"rejeitado: {contexto.get('erro')!r}"
    m = mapeamento_por_chave(ano, tipo, origem)
    assert m is not None, "mapeamento não encontrado"
    ativos = [i for i in m.itens if i.ind_status == 'A']
    assert len(ativos) == n


@then(parsers.parse('o cadastro do mapeamento é rejeitado com mensagem contendo "{trecho}"'))
def mapeamento_rejeitado(contexto, trecho):
    assert contexto["erro"] is not None, "esperava rejeição"
    assert trecho.lower() in contexto["erro"].lower(), contexto["erro"]


@then(parsers.parse('o item do mapeamento tem inversão de sinal "{valor}"'))
def item_inversao(contexto, valor):
    assert contexto.get("erro") is None, f"rejeitado: {contexto.get('erro')!r}"
    m = contexto["mapeamento"]
    assert m.itens[0].ind_inversao_sinal == valor
