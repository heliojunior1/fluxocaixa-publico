"""Steps BDD — tela de mapeamentos (spec automacao-lancamentos R10/R11)."""
import json
from datetime import date
from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from ..conftest_extracao import (
    criar_fonte_fake,
    fonte_por_nome,
    garantir_conector_fake,
    garantir_sistema_origem,
)
from ..conftest_permissoes import criar_usuario_com_perfil
from .conftest_regra import (
    criar_mapeamento,
    garantir_qualificador,
    garantir_termos_padrao,
    mapeamento_por_chave,
    sistema_por_sigla,
)

scenarios("../automacao-lancamentos/tela_mapeamentos.feature")

LINHAS = [
    {"natureza": "11120000", "ug": "999001", "valor": "100.00"},
    {"natureza": "11120001", "ug": "999002", "valor": "200.00"},
    {"natureza": "22220000", "ug": "999001", "valor": "300.00"},
]


@pytest.fixture()
def contexto():
    return {}


@pytest.fixture(autouse=True)
def _estado_limpo(app):
    from fluxocaixa.models import EtlStaging, ItemMapeamento, Mapeamento
    from fluxocaixa.models.base import db

    db.session.rollback()
    db.session.query(ItemMapeamento).delete()
    db.session.query(Mapeamento).delete()
    db.session.query(EtlStaging).delete()
    db.session.commit()


def _cliente_perfil(app, perfil):
    from fastapi.testclient import TestClient

    login, senha, _ = criar_usuario_com_perfil(perfil)
    tc = TestClient(app, follow_redirects=False, headers={"Accept": "text/html"})
    resp = tc.post("/login", data={"usuario": login, "senha": senha})
    assert resp.status_code in (302, 303), f"login do perfil {perfil} falhou"
    return tc


# --------------------------------------------------------------------------
# Dado
# --------------------------------------------------------------------------

@given("que estou autenticado como administrador")
def autenticado_admin(app, client, contexto):
    from fluxocaixa.auth.contexto import definir_usuario_corrente

    definir_usuario_corrente(777)
    # Accept text/html: é o que o browser manda, e o que faz o handler global
    # devolver flash+redirect em vez de 400 JSON
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


@given(parsers.parse('linhas na staging do sistema de origem "{sigla}"'))
def staging_populada(app, sigla):
    from fluxocaixa.models import EtlStaging, ExecucaoExtracao
    from fluxocaixa.models.base import db

    garantir_conector_fake()
    garantir_sistema_origem(sigla)
    fonte = fonte_por_nome("Fonte Tela") or criar_fonte_fake(
        "Fonte Tela", sigla_sistema=sigla)

    execucao = ExecucaoExtracao(
        seq_fonte_extracao=fonte.seq_fonte_extracao,
        dat_inicio_execucao=date(2026, 7, 10), cod_disparo="MANUAL",
        cod_status="SUCESSO", dat_janela_inicio=date(2026, 7, 10),
        dat_janela_fim=date(2026, 7, 10),
    )
    db.session.add(execucao)
    db.session.flush()
    for linha in LINHAS:
        db.session.add(EtlStaging(
            seq_fonte_extracao=fonte.seq_fonte_extracao,
            seq_execucao_extracao=execucao.seq_execucao_extracao,
            num_ano_exercicio=2026, dat_referencia=date(2026, 7, 10),
            val_referencia=Decimal(linha["valor"]), json_atributos=dict(linha),
            ind_status_processamento='0',
        ))
    db.session.commit()


@given(parsers.parse('um mapeamento salvo com a regra "{regra}"'))
def mapeamento_salvo(app, contexto, regra):
    q = garantir_qualificador("1.1.1")
    mapeamento = criar_mapeamento(2026, "1", "SIS_X", [
        {"seq_qualificador": q.seq_qualificador, "txt_regra": regra},
    ])
    contexto["seq_mapeamento"] = mapeamento.seq_mapeamento
    contexto["regra"] = regra


# --------------------------------------------------------------------------
# Quando
# --------------------------------------------------------------------------

@when(parsers.parse('crio pela tela o mapeamento {ano:d} tipo "{tipo}" origem "{origem}" '
                    'com um item no qualificador "{num}" e regra "{regra}"'))
def cria_pela_tela(app, contexto, ano, tipo, origem, num, regra):
    q = garantir_qualificador(num)
    itens = [{"seq_qualificador": q.seq_qualificador, "txt_regra": regra,
              "ind_inversao_sinal": "0"}]
    contexto["resp"] = contexto["cliente"].post('/mapeamentos/salvar', data={
        'num_ano_exercicio': str(ano), 'ind_tipo': tipo,
        'seq_sistema_origem': str(sistema_por_sigla(origem).seq_sistema_origem),
        'dsc_mapeamento': f'Mapeamento {ano}',
        'itens_raw': json.dumps(itens),
    })


@when(parsers.parse('peço pela tela a validação da regra "{regra}"'))
def valida_regra(app, contexto, regra):
    contexto["resp"] = contexto["cliente"].post(
        '/mapeamentos/validar-regra', data={'txt_regra': regra})


@when(parsers.parse('peço pela tela a validação da regra montada com o valor "{valor}"'))
def valida_valor_builder(app, contexto, valor):
    contexto["resp"] = contexto["cliente"].post('/mapeamentos/validar-regra-builder', data={
        'nom_termo': 'Unidade Gestora', 'operador': 'IGUAL', 'valor': valor,
    })


@when(parsers.parse('peço pela tela o preview da regra "{regra}" para "{sigla}"'))
def pede_preview(app, contexto, regra, sigla):
    from fluxocaixa.models import Lancamento

    contexto["lancamentos_antes"] = Lancamento.query.count()
    contexto["resp"] = contexto["cliente"].post('/mapeamentos/preview-regra', data={
        'txt_regra': regra,
        'seq_sistema_origem': str(sistema_por_sigla(sigla).seq_sistema_origem),
        'num_ano_exercicio': '2026',
    })


@when("abro o mapeamento para edição")
def abre_edicao(app, contexto):
    contexto["resp"] = contexto["cliente"].get(
        f'/mapeamentos/form/{contexto["seq_mapeamento"]}')


@when("abro a lista de mapeamentos")
def abre_lista(app, contexto):
    contexto["resp"] = contexto["cliente"].get('/mapeamentos')


# --------------------------------------------------------------------------
# Então
# --------------------------------------------------------------------------

def _html(contexto):
    resp = contexto["resp"]
    if resp.status_code in (302, 303):
        resp = contexto["cliente"].get(resp.headers['location'])
    return resp.text


@then(parsers.parse('a lista de mapeamentos mostra o mapeamento {ano:d} tipo "{tipo}" '
                    'origem "{origem}"'))
def lista_mostra(app, contexto, ano, tipo, origem):
    assert mapeamento_por_chave(ano, tipo, origem) is not None, "não foi criado"
    assert f'Mapeamento {ano}' in contexto["cliente"].get('/mapeamentos').text


@then(parsers.parse('o item salvo tem a regra "{regra}"'))
def item_com_regra(app, contexto, regra):
    mapeamento = mapeamento_por_chave(2026, "1", "SIS_X")
    assert mapeamento.itens[0].txt_regra == regra


@then(parsers.parse('a tela de mapeamentos mostra erro contendo "{trecho}"'))
def tela_erro(app, contexto, trecho):
    html = _html(contexto)
    assert 'flash-erro' in html, "esperava flash de erro"
    assert trecho.lower() in html.lower(), html[:400]


@then(parsers.parse('o mapeamento {ano:d} tipo "{tipo}" origem "{origem}" não existe'))
def mapeamento_ausente(app, ano, tipo, origem):
    assert mapeamento_por_chave(ano, tipo, origem) is None


@then(parsers.parse('a validação responde inválida com mensagem contendo "{trecho}"'))
def validacao_invalida(contexto, trecho):
    dados = contexto["resp"].json()
    assert dados["ok"] is False, dados
    assert trecho.lower() in (dados["erro"] or "").lower(), dados


@then("a validação responde válida")
def validacao_valida(contexto):
    dados = contexto["resp"].json()
    assert dados["ok"] is True, dados


@then("nenhum mapeamento existe")
def nenhum_mapeamento(app):
    from fluxocaixa.models import Mapeamento
    from fluxocaixa.models.base import db

    db.session.expire_all()
    assert Mapeamento.query.count() == 0


@then(parsers.parse('o preview da tela retorna {n:d} linhas'))
def preview_conta(contexto, n):
    assert contexto["resp"].status_code == 200, contexto["resp"].text[:300]
    assert contexto["resp"].json()["total"] == n, contexto["resp"].json()


@then("nenhuma linha da staging teve o status alterado")
def staging_intacta(app):
    from fluxocaixa.models import EtlStaging
    from fluxocaixa.models.base import db

    db.session.expire_all()
    linhas = EtlStaging.query.all()
    assert linhas
    assert all(ln.ind_status_processamento == '0' for ln in linhas)


@then(parsers.parse('a regra é apresentada no builder com {n:d} linhas'))
def regra_no_builder(contexto, n):
    # quem decide builder × avançado é o SERVIDOR (parser); a tela só obedece
    dados = _regra_injetada(contexto["resp"].text)
    assert dados["modo"] == "builder", dados
    assert len(dados["linhas"]) == n, dados


@then("a regra é apresentada no modo avançado")
def regra_no_avancado(contexto):
    assert _regra_injetada(contexto["resp"].text)["modo"] == "avancado"


@then(parsers.parse('a regra apresentada é "{regra}"'))
def regra_preservada(contexto, regra):
    # o texto vai no estado JSON (o tojson do Jinja escapa aspas — é proteção
    # contra quebrar o <script>, então não se procura o texto cru no HTML)
    assert _regra_injetada(contexto["resp"].text)["txt_regra"] == regra


def _regra_injetada(html):
    """A tela injeta o estado das regras como JSON (padrão do editor de extração)."""
    marcador = 'id="regras-estado"'
    inicio = html.index(marcador)
    inicio = html.index('>', inicio) + 1
    fim = html.index('</script>', inicio)
    return json.loads(html[inicio:fim])[0]


@then("não vejo as ações de manutenção de mapeamento")
def sem_acoes(contexto):
    html = contexto["resp"].text
    assert 'data-testid="novo-mapeamento"' not in html
    assert 'data-testid="editar-' not in html
    assert 'data-testid="inativar-' not in html
