"""Steps BDD — telas de fontes e execuções (spec extracao-configuravel R10–R13)."""
from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

from ..conftest_extracao import (
    execucoes_da_fonte,
    fonte_por_nome,
    garantir_conector_fake,
    garantir_conta,
    garantir_fonte_ativa,
    garantir_fundo,
    garantir_sistema_origem,
    linha_extraida,
)
from ..conftest_permissoes import criar_usuario_com_perfil

scenarios("../extracao-configuravel/telas.feature")


@pytest.fixture()
def contexto():
    return {}


def _db():
    from fluxocaixa.models.base import db

    return db


def _registrar_execucao(nome, status, *, inseridas=0, erros=0, detalhe=None):
    from fluxocaixa.models import ExecucaoExtracao

    fonte = fonte_por_nome(nome)
    db = _db()
    execucao = ExecucaoExtracao(
        seq_fonte_extracao=fonte.seq_fonte_extracao,
        dat_inicio_execucao=datetime.now(),
        num_duracao_segundos=0,
        cod_disparo="MANUAL",
        cod_status=status,
        dat_janela_inicio=date.today(),
        dat_janela_fim=date.today(),
        qtd_linhas_inseridas=inseridas,
        qtd_linhas_erro=erros,
        qtd_fundos_auto_cadastrados=0,
        txt_detalhe_erros=detalhe,
    )
    db.session.add(execucao)
    db.session.commit()
    return execucao


def _cliente_perfil(app, perfil):
    login, senha, _ = criar_usuario_com_perfil(perfil)
    tc = TestClient(app)
    resp = tc.post("/login", data={"usuario": login, "senha": senha}, follow_redirects=False)
    assert resp.status_code in (302, 303)
    return tc


# --------------------------------------------------------------------------
# Dado
# --------------------------------------------------------------------------

@given("que estou autenticado como administrador")
def autenticado_admin(app, _admin_pronto, client):
    from fluxocaixa.auth.contexto import definir_usuario_corrente

    definir_usuario_corrente(777)


@given(parsers.parse('um sistema de origem "{sigla}" cadastrado'))
def sistema_cadastrado(app, sigla):
    garantir_sistema_origem(sigla)


@given('o conector de teste "FAKE" registrado', target_fixture="conector_fake")
def conector_fake_registrado(app):
    return garantir_conector_fake()


@given(parsers.parse('uma fonte de tela "{nome}" do tipo "{tipo:w}"'))
def fonte_de_tela(app, nome, tipo):
    garantir_fonte_ativa(nome, tipo=tipo)


@given(parsers.parse('uma fonte de tela "{nome}" do tipo "{tipo:w}" com token "{token}"'))
def fonte_de_tela_token(app, nome, tipo, token):
    garantir_fonte_ativa(nome, tipo=tipo, token=token)


@given(parsers.parse('uma conta de tela "{ident}"'))
def conta_de_tela(app, ident):
    garantir_conta(ident)


@given(parsers.parse('um fundo de tela "{cod}"'))
def fundo_de_tela(app, cod):
    garantir_fundo(cod)


@given(parsers.parse('que o conector de tela devolve um saldo de "{valor}" para a conta "{ident}" e fundo "{cod}"'))
def conector_tela_devolve(app, conector_fake, valor, ident, cod):
    conector_fake.linhas.append(linha_extraida(ident, cod, valor))


@given(parsers.parse('uma execução "{status}" registrada para a fonte "{nome}"'))
def execucao_registrada(app, status, nome):
    inseridas = 2 if status in ("PARCIAL", "SUCESSO") else 0
    erros = 1 if status == "PARCIAL" else 0
    _registrar_execucao(nome, status, inseridas=inseridas, erros=erros)


@given(parsers.parse('uma execução com erro na conta "{ident}" registrada para a fonte "{nome}"'))
def execucao_com_erro(app, ident, nome):
    import json

    detalhe = json.dumps([{"linha": 1, "mensagem": f"Conta {ident} não cadastrada"}],
                         ensure_ascii=False)
    _registrar_execucao(nome, "ERRO", inseridas=0, erros=1, detalhe=detalhe)


@given(parsers.parse('um cliente HTTP autenticado com o perfil "{perfil}"'), target_fixture="cliente_perfil")
def cliente_perfil(app, perfil):
    return _cliente_perfil(app, perfil)


@given("que nenhum conector de extração está registrado")
def nenhum_conector(app):
    from fluxocaixa.extracao import registry

    for tipo in list(registry.tipos_disponiveis()):
        registry.remover(tipo)


@given(parsers.parse('que a variável "{var}" não está definida'))
def var_nao_definida(monkeypatch, var):
    monkeypatch.delenv(var, raising=False)


@given(parsers.parse('que a variável "{var}" está habilitada'))
def var_habilitada(monkeypatch, var):
    monkeypatch.setenv(var, "1")


# --------------------------------------------------------------------------
# Quando
# --------------------------------------------------------------------------

@when("abro a tela de fontes")
def abro_tela_fontes(client, contexto):
    contexto["resp"] = client.get("/extracao/fontes")


@when("o cliente abre a tela de fontes")
def cliente_abre_fontes(cliente_perfil, contexto):
    contexto["resp"] = cliente_perfil.get("/extracao/fontes")


@when(parsers.parse('inativo a fonte "{nome}" pela tela sem confirmar'))
def inativa_sem_confirmar(client, nome):
    fonte = fonte_por_nome(nome)
    client.post(f"/extracao/fontes/{fonte.seq_fonte_extracao}/inativar",
                data={}, follow_redirects=False)


@when(parsers.parse('inativo a fonte "{nome}" pela tela com confirmação'))
def inativa_com_confirmacao(client, nome):
    fonte = fonte_por_nome(nome)
    client.post(f"/extracao/fontes/{fonte.seq_fonte_extracao}/inativar",
                data={"confirmado": "true"}, follow_redirects=False)


@when(parsers.parse('aciono testar conexão da fonte "{nome}" pela tela'))
def aciona_testar(client, contexto, nome):
    fonte = fonte_por_nome(nome)
    contexto["resp"] = client.post(
        f"/extracao/fontes/{fonte.seq_fonte_extracao}/testar-conexao"
    )


@when(parsers.parse('aciono executar agora da fonte "{nome}" pela tela'))
def aciona_executar(client, contexto, nome):
    fonte = fonte_por_nome(nome)
    contexto["resp"] = client.post(
        f"/api/extracao/fontes/{fonte.seq_fonte_extracao}/executar", json={}
    )


@when("abro a tela de execuções")
def abro_execucoes(client, contexto):
    contexto["resp"] = client.get("/extracao/execucoes")


@when(parsers.parse('abro a tela de execuções filtrando pela fonte "{nome}"'))
def abro_execucoes_filtro(client, contexto, nome):
    fonte = fonte_por_nome(nome)
    contexto["resp"] = client.get(f"/extracao/execucoes?fonte={fonte.seq_fonte_extracao}")


@when(parsers.parse('abro o formulário de nova fonte para o tipo "{tipo}"'))
def abro_form_nova(client, contexto, tipo):
    contexto["resp"] = client.get(f"/extracao/fontes/nova?tipo={tipo}")


@when(parsers.parse('abro o formulário de edição da fonte "{nome}"'))
def abro_form_edicao(client, contexto, nome):
    fonte = fonte_por_nome(nome)
    contexto["resp"] = client.get(f"/extracao/fontes/{fonte.seq_fonte_extracao}/editar")


@when(parsers.parse('crio pela tela a fonte "{nome}" do tipo "{tipo:w}" sem o campo "{campo}"'))
def cria_pela_tela_sem_campo(client, contexto, nome, tipo, campo):
    # follow_redirects: RegraNegocioError vira flash + redirect 303; ao seguir,
    # a próxima página renderiza a mensagem no data-testid="flash-erro".
    contexto["resp"] = client.post(
        "/extracao/fontes",
        data={"nom_fonte": nome, "cod_tipo_conector": tipo,
              "sigla_sistema": "SIS_X", "cod_destino": "SALDO_FUNDO", "txt_cron": ""},
        headers={"Accept": "text/html"},  # como um POST de formulário do navegador
        follow_redirects=True,
    )


@when("os conectores disponíveis são registrados")
def registra_conectores(app, contexto):
    from fluxocaixa.extracao import registry
    from fluxocaixa.extracao.conectores import registrar_conectores_disponiveis

    registry.remover("DEMO_MANUAL")
    registrar_conectores_disponiveis()


# --------------------------------------------------------------------------
# Então
# --------------------------------------------------------------------------

def _html(contexto):
    return contexto["resp"].text


@then(parsers.parse('a tela de fontes mostra "{nome}" com o status "{status}"'))
def tela_mostra_status(contexto, nome, status):
    html = _html(contexto)
    assert nome in html
    assert status in html


@then("a tela não oferece a ação de nova fonte")
def sem_acao_nova(contexto):
    assert 'data-testid="nova-fonte"' not in _html(contexto)


@then(parsers.parse('a fonte "{nome}" continua ativa'))
def fonte_continua_ativa(nome):
    assert fonte_por_nome(nome).ind_status == "A"


@then(parsers.parse('a fonte "{nome}" fica inativa'))
def fonte_fica_inativa(nome):
    assert fonte_por_nome(nome).ind_status == "I"


@then("a tela de fontes mostra o estado vazio de conectores")
def estado_vazio(contexto):
    assert 'data-testid="fontes-sem-conector"' in _html(contexto)


@then("o resultado do teste é sucesso")
def resultado_teste_sucesso(contexto):
    resp = contexto["resp"]
    assert resp.status_code == 200, resp.text
    assert resp.json()["ok"] is True


@then(parsers.parse('nenhuma execução foi registrada para a fonte de tela "{nome}"'))
def nenhuma_execucao_tela(nome):
    assert execucoes_da_fonte(nome) == []


@then(parsers.parse('a resposta da execução tem status "{status}"'))
def resposta_execucao_status(contexto, status):
    resp = contexto["resp"]
    assert resp.status_code == 200, resp.text
    assert resp.json()["codStatus"] == status


@then(parsers.parse('a última execução da fonte de tela "{nome}" tem disparo "{disparo}"'))
def ultima_execucao_disparo(nome, disparo):
    execucoes = execucoes_da_fonte(nome)
    assert execucoes and execucoes[-1].cod_disparo == disparo


@then(parsers.parse('a tela de execuções mostra o status "{status}"'))
def tela_execucoes_status(contexto, status):
    assert status in _html(contexto)


def _corpo_tabela(contexto):
    """Só as linhas da tabela — evita casar com o <select> de filtro."""
    html = _html(contexto)
    return html[html.find("<tbody"):] if "<tbody" in html else html


@then(parsers.parse('a tela de execuções lista a fonte "{nome}"'))
def execucoes_lista_fonte(contexto, nome):
    assert nome in _corpo_tabela(contexto)


@then(parsers.parse('a tela de execuções não lista a fonte "{nome}"'))
def execucoes_nao_lista_fonte(contexto, nome):
    assert nome not in _corpo_tabela(contexto)


@then(parsers.parse('o detalhe da execução menciona "{trecho}"'))
def detalhe_menciona(contexto, trecho):
    assert trecho in _html(contexto)


@then(parsers.parse('o formulário tem um campo "{campo}" obrigatório'))
def form_campo_obrigatorio(contexto, campo):
    html = _html(contexto)
    assert f'name="{campo}"' in html


@then(parsers.parse('o formulário tem o campo secreto "{campo}" mascarado'))
def form_campo_secreto(contexto, campo):
    html = _html(contexto)
    assert f'name="{campo}"' in html
    assert 'type="password"' in html


@then(parsers.parse('o formulário não pré-preenche o valor "{valor}" no campo secreto'))
def form_nao_expoe_segredo(contexto, valor):
    assert valor not in _html(contexto)


@then(parsers.parse('o cadastro pela tela é rejeitado com mensagem contendo "{trecho}"'))
def cadastro_tela_rejeitado(contexto, trecho):
    resp = contexto["resp"]
    assert resp.status_code == 200, resp.text  # já seguiu o redirect do flash
    assert trecho.lower() in resp.text.lower()


@then(parsers.parse('a fonte de tela "{nome}" não existe'))
def fonte_tela_nao_existe(nome):
    assert fonte_por_nome(nome) is None


@then(parsers.parse('o tipo "{tipo}" não está entre os conectores disponíveis'))
def tipo_nao_disponivel(tipo):
    from fluxocaixa.extracao import registry

    assert tipo not in registry.tipos_disponiveis()


@then(parsers.parse('o tipo "{tipo}" está entre os conectores disponíveis'))
def tipo_disponivel(tipo):
    from fluxocaixa.extracao import registry

    assert tipo in registry.tipos_disponiveis()
