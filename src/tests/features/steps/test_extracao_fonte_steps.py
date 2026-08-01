"""Steps BDD — cadastro de fontes e registry de conectores (spec extracao-configuravel R1/R2)."""
import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from ..conftest_extracao import (
    CONFIG_FAKE_VALIDO,
    criar_fonte_fake,
    fonte_por_nome,
    garantir_conector_fake,
    garantir_fonte_ativa,
    garantir_sistema_origem,
)

scenarios("../extracao-configuravel/fonte_extracao.feature")


@pytest.fixture()
def contexto():
    return {}


def _criar(contexto, nome, **kwargs):
    from fluxocaixa.services.validacao import RegraNegocioError

    try:
        contexto["fonte"] = criar_fonte_fake(nome, **kwargs)
        contexto["erro"] = None
    except RegraNegocioError as exc:
        contexto["erro"] = exc.mensagem


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


@given('o conector de teste "FAKE" registrado', target_fixture="conector_fake")
def conector_fake_registrado(app):
    return garantir_conector_fake()


@given(parsers.parse('uma fonte "{nome}" do tipo "{tipo}"'))
def fonte_existente(app, nome, tipo):
    garantir_fonte_ativa(nome, tipo=tipo)


# --------------------------------------------------------------------------
# Quando
# --------------------------------------------------------------------------

@when(parsers.parse('crio a fonte "{nome}" do tipo "{tipo}" com cron "{cron}"'))
def cria_fonte_com_cron(app, contexto, nome, tipo, cron):
    _criar(contexto, nome, tipo=tipo, cron=cron)


@when(parsers.parse('crio a fonte "{nome}" do tipo "{tipo}" sem o campo obrigatório "{campo}"'))
def cria_fonte_sem_campo(app, contexto, nome, tipo, campo):
    config = {k: v for k, v in CONFIG_FAKE_VALIDO.items() if k != campo}
    _criar(contexto, nome, tipo=tipo, json_config=config)


@when(parsers.parse('crio a fonte "{nome}" do tipo "{tipo}" com destino "{destino}"'))
def cria_fonte_com_destino(app, contexto, nome, tipo, destino):
    _criar(contexto, nome, tipo=tipo, destino=destino)


@when(parsers.parse('registro outro conector com o tipo "{tipo}"'))
def registra_duplicado(app, contexto, tipo):
    from fluxocaixa.extracao import registry

    class Duplicado:
        schema_config = None

        def testar_conexao(self, config):  # pragma: no cover - nunca chamado
            raise NotImplementedError

        def extrair(self, config, janela):  # pragma: no cover - nunca chamado
            raise NotImplementedError

    Duplicado.tipo = tipo
    try:
        registry.registrar(Duplicado())
        contexto["erro_registro"] = None
    except ValueError as exc:
        contexto["erro_registro"] = str(exc)


# --------------------------------------------------------------------------
# Então
# --------------------------------------------------------------------------

@then(parsers.parse('a fonte "{nome}" existe ativa com auditoria preenchida'))
def fonte_existe_ativa(contexto, nome):
    assert contexto["erro"] is None, f"cadastro rejeitado: {contexto['erro']!r}"
    fonte = fonte_por_nome(nome)
    assert fonte is not None and fonte.ind_status == "A"
    assert fonte.dat_inclusao is not None
    assert fonte.cod_pessoa_inclusao is not None


@then(parsers.parse('o cadastro é rejeitado com mensagem contendo "{trecho}"'))
def cadastro_rejeitado(contexto, trecho):
    assert contexto["erro"] is not None, "esperava rejeição, cadastro passou"
    assert trecho.lower() in contexto["erro"].lower(), (
        f"esperava {trecho!r} em {contexto['erro']!r}"
    )


@then(parsers.parse('a fonte "{nome}" não existe'))
def fonte_nao_existe(nome):
    assert fonte_por_nome(nome) is None


@then(parsers.parse('o tipo "{tipo}" está entre os tipos de conector disponíveis'))
def tipo_disponivel(tipo):
    from fluxocaixa.extracao import registry

    assert tipo in registry.tipos_disponiveis()


@then("o registro é recusado por tipo duplicado")
def registro_recusado(contexto):
    assert contexto["erro_registro"] is not None
