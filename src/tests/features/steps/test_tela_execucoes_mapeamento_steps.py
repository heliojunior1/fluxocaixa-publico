"""Steps BDD — tela de execuções de mapeamento (spec R16)."""
import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from ..conftest_extracao import garantir_sistema_origem
from ..conftest_permissoes import criar_usuario_com_perfil
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
)

scenarios("../automacao-lancamentos/tela_execucoes_mapeamento.feature")


@pytest.fixture()
def contexto():
    return {}


@pytest.fixture(autouse=True)
def _limpo(app):
    limpar_estado_processamento()


def _cliente_perfil(app, perfil):
    from fastapi.testclient import TestClient

    login, senha, _ = criar_usuario_com_perfil(perfil)
    tc = TestClient(app, follow_redirects=False, headers={"Accept": "text/html"})
    resp = tc.post("/login", data={"usuario": login, "senha": senha})
    assert resp.status_code in (302, 303), f"login do perfil {perfil} falhou"
    return tc


@given("que estou autenticado como administrador")
def autenticado_admin(app, client, contexto, _admin_pronto):
    from fluxocaixa.auth.contexto import definir_usuario_corrente

    definir_usuario_corrente(777)
    client.headers.update({"Accept": "text/html"})
    client.follow_redirects = False
    contexto["cliente"] = client


@given("que estou autenticado como usuário só de consulta")
def autenticado_consulta(app, contexto):
    contexto["cliente"] = _cliente_perfil(app, "CONSULTA")


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


@given(parsers.parse('o mapeamento 2026 de "{sigla}" com o item "{num}" e regra "{regra}"'))
def mapeamento(app, contexto, sigla, num, regra):
    q = garantir_qualificador(num)
    m = criar_mapeamento(2026, sigla, [
        {"seq_qualificador": q.seq_qualificador, "txt_regra": regra},
    ])
    contexto["seq_mapeamento"] = m.seq_mapeamento


@given("que já processei o mapeamento")
def ja_processei(app, contexto):
    from fluxocaixa.services.processamento_service import processar_mapeamento

    processar_mapeamento(contexto["seq_mapeamento"], disparo="MANUAL")


@when("abro a tela de execuções de mapeamento")
def abre_tela(app, contexto):
    contexto["resp"] = contexto["cliente"].get('/mapeamentos/execucoes')


@when("disparo o processamento pela tela")
def dispara(app, contexto):
    contexto["resp"] = contexto["cliente"].post(
        f'/mapeamentos/processar/{contexto["seq_mapeamento"]}')


@then(parsers.parse('vejo a execução com situação "{status}" e {n:d} lançamentos gerados'))
def tela_mostra(app, contexto, status, n):
    html = contexto["resp"].text
    assert 'data-testid="tabela-execucoes-mapeamento"' in html
    execucao = ultima_execucao_mapeamento(contexto["seq_mapeamento"])
    assert f'execucao-mapeamento-linha-{execucao.seq_execucao_mapeamento}' in html
    assert status in html
    assert execucao.qtd_lancamentos_gerados == n


@then(parsers.parse('a execução de mapeamento tem disparo "{disparo}"'))
def execucao_disparo(app, contexto, disparo):
    execucao = ultima_execucao_mapeamento(contexto["seq_mapeamento"])
    assert execucao is not None, "nenhuma execução registrada"
    assert execucao.cod_disparo == disparo


@then(parsers.parse('foram criados {n:d} lançamentos no qualificador "{num}"'))
def n_lancamentos(app, n, num):
    assert len(lancamentos_do_qualificador(num)) == n


@then("não vejo a ação de processar")
def sem_acao(contexto):
    assert 'data-testid="processar-' not in contexto["resp"].text
