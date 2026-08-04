"""Steps BDD — tradutor de regra pt-BR → predicado (spec automacao-lancamentos R7)."""
import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from ..conftest_extracao import garantir_sistema_origem
from .conftest_regra import (
    criar_mapeamento,
    criar_termo,
    garantir_qualificador,
    garantir_termos_padrao,
)

scenarios("../automacao-lancamentos/tradutor_regra.feature")


@pytest.fixture()
def contexto():
    return {}


@pytest.fixture(autouse=True)
def _mapeamentos_limpos(app):
    """O cenário de cadastro daqui cria um mapeamento que pode colidir com o de
    outro módulo da suíte (o banco persiste entre eles)."""
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


@given("os termos de regra padrão cadastrados")
def termos_padrao(app):
    garantir_termos_padrao()


@given(parsers.parse('o termo "{nom}" cadastrado para o atributo "{campo}"'))
def termo_atributo(app, nom, campo):
    from .conftest_regra import termo_por_nome

    if termo_por_nome(nom) is None:
        criar_termo(nom, "ATRIBUTO", campo, "TEXTO")


@given(parsers.parse('um sistema de origem "{sigla}" cadastrado'))
def sistema_cadastrado(app, sigla):
    garantir_sistema_origem(sigla)


@given(parsers.parse('um qualificador folha "{num}"'))
def qualificador_folha(app, num):
    garantir_qualificador(num)


@when(parsers.parse('traduzo a regra "{regra}"'))
def traduz(app, contexto, regra):
    from fluxocaixa.services.regra import traduzir_regra
    from fluxocaixa.services.validacao import RegraNegocioError

    try:
        expressao = traduzir_regra(regra)
        # compila o predicado para inspeção textual (literais embutidos: é só teste)
        contexto["sql"] = str(expressao.compile(compile_kwargs={"literal_binds": True}))
        contexto["erro"] = None
    except RegraNegocioError as exc:
        contexto["sql"] = None
        contexto["erro"] = exc.mensagem


@when(parsers.parse('crio o mapeamento {ano:d} origem "{origem}" '
                    'com um item no qualificador "{num}" e regra "{regra}"'))
def cria_com_regra(app, contexto, ano, origem, num, regra):
    from fluxocaixa.services.validacao import RegraNegocioError

    q = garantir_qualificador(num)
    try:
        criar_mapeamento(ano, origem, [
            {"seq_qualificador": q.seq_qualificador, "txt_regra": regra},
        ])
        contexto["erro"] = None
    except RegraNegocioError as exc:
        contexto["erro"] = exc.mensagem


@then(parsers.parse('o predicado referencia o atributo "{campo}"'))
def predicado_referencia(contexto, campo):
    assert contexto.get("erro") is None, f"rejeitado: {contexto.get('erro')!r}"
    assert campo in contexto["sql"], contexto["sql"]


@then(parsers.parse('o predicado não referencia o atributo "{campo}"'))
def predicado_nao_referencia(contexto, campo):
    # 'ug' é prefixo de 'ug_emitente': procura o campo entre aspas do json_extract
    assert f"'{campo}'" not in contexto["sql"], contexto["sql"]
    assert f'"{campo}"' not in contexto["sql"], contexto["sql"]


@then("a regra é traduzida com sucesso")
def traducao_ok(contexto):
    assert contexto.get("erro") is None, f"rejeitado: {contexto.get('erro')!r}"
    assert contexto["sql"]


@then("a tradução é rejeitada")
def traducao_rejeitada(contexto):
    assert contexto["erro"] is not None, "esperava rejeição"


@then(parsers.parse('a tradução é rejeitada com mensagem contendo "{trecho}"'))
def traducao_rejeitada_msg(contexto, trecho):
    assert contexto["erro"] is not None, "esperava rejeição"
    assert trecho.lower() in contexto["erro"].lower(), contexto["erro"]


@then(parsers.parse('o cadastro do mapeamento é rejeitado com mensagem contendo "{trecho}"'))
def cadastro_rejeitado(contexto, trecho):
    assert contexto["erro"] is not None, "esperava rejeição"
    assert trecho.lower() in contexto["erro"].lower(), contexto["erro"]
