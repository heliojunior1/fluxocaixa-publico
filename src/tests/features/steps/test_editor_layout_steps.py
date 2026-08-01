"""Steps BDD — editor de layout na tela e preview (spec R17/R18)."""
import json
from datetime import date
from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from ..conftest_extracao import (
    fonte_por_nome,
    garantir_conector_fake,
    garantir_conta,
    garantir_sistema_origem,
)

scenarios("../extracao-configuravel/editor_layout.feature")

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "extracao"
PADRAO_NOME = "{:%Y%m%d}_0001_EXTRATO.csv"

LAYOUT_EXTRATO = {
    "separador": ";",
    "encoding": "utf-8-sig",
    "tem_header": True,
    "header_esperado": ["Banco", "Agência", "Conta", "Data", "Descrição", "Saldo"],
    "formato_data": "%d/%m/%Y",
    "formato_decimal": "PT_BR",
    "colunas": [
        {"origem": 0, "destino": "cod_banco"},
        {"origem": 1, "destino": "num_agencia"},
        {"origem": 2, "destino": "num_conta", "transformacao": "somente_digitos"},
        {"origem": 3, "destino": "dat_saldo", "transformacao": "data"},
        {"origem": 4, "destino": "cod_fundo+dsc_fundo", "transformacao": "codigo_antes_hifen"},
        {"origem": 5, "destino": "val_saldo", "transformacao": "decimal"},
    ],
}


@pytest.fixture()
def contexto():
    return {}


@pytest.fixture()
def pasta_ex(tmp_path):
    d = tmp_path / "arquivos"
    d.mkdir()
    return d


def _garantir_conector_arquivo():
    from fluxocaixa.extracao import registry
    from fluxocaixa.extracao.conectores.ftp_arquivo import ConectorFtpArquivo

    if "FTP_ARQUIVO" not in registry.tipos_disponiveis():
        registry.registrar(ConectorFtpArquivo())


def _escrever_dia(pasta, fixture, dia: date):
    (pasta / PADRAO_NOME.format(dia)).write_bytes((FIXTURES / fixture).read_bytes())


def _form_fonte(nome, pasta, layout):
    return {
        "cod_tipo_conector": "FTP_ARQUIVO",
        "nom_fonte": nome,
        "sigla_sistema": "SIS_X",
        "cod_destino": "SALDO_FUNDO",
        "txt_cron": "",
        "protocolo": "PASTA_LOCAL",
        "diretorio": str(pasta),
        "padrao_nome": PADRAO_NOME,
        "json_layout_raw": json.dumps(layout),
    }


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


@given('o conector "FTP_ARQUIVO" registrado')
def conector_arquivo_registrado(app):
    _garantir_conector_arquivo()


@given('o conector de teste "FAKE" registrado')
def conector_fake_registrado(app):
    garantir_conector_fake()


@given(parsers.parse('uma pasta de exemplo com o arquivo "{fixture}" para o dia "{dia}"'),
       target_fixture="pasta_preparada")
def pasta_com_arquivo(app, pasta_ex, fixture, dia):
    _escrever_dia(pasta_ex, fixture, date.fromisoformat(dia))
    return pasta_ex


@given("uma pasta de exemplo vazia", target_fixture="pasta_preparada")
def pasta_vazia(app, pasta_ex):
    return pasta_ex


@given("as contas de exemplo cadastradas")
def contas_exemplo(app):
    garantir_conta("104/0001/123456")
    garantir_conta("104/0001/987654")


@given(parsers.parse('uma fonte de arquivo "{nome}" com o layout de extrato na pasta de exemplo'))
def fonte_arquivo_existente(app, pasta_preparada, nome):
    from fluxocaixa.services.extracao_service import criar_fonte

    criar_fonte(
        nom_fonte=nome, cod_tipo_conector="FTP_ARQUIVO", sigla_sistema="SIS_X",
        json_config={"protocolo": "PASTA_LOCAL", "diretorio": str(pasta_preparada),
                     "padrao_nome": PADRAO_NOME},
        json_layout=LAYOUT_EXTRATO,
    )


# --------------------------------------------------------------------------
# Quando
# --------------------------------------------------------------------------

@when(parsers.parse('abro o formulário de nova fonte para o tipo "{tipo}"'))
def abro_form_nova(client, contexto, tipo):
    contexto["resp"] = client.get(f"/extracao/fontes/nova?tipo={tipo}")


@when(parsers.parse('abro o formulário de edição da fonte "{nome}"'))
def abro_form_edicao(client, contexto, nome):
    fonte = fonte_por_nome(nome)
    contexto["resp"] = client.get(f"/extracao/fontes/{fonte.seq_fonte_extracao}/editar")


@when(parsers.parse('cadastro pela tela a fonte "{nome}" apontando para a pasta com o layout de extrato'))
def cadastra_com_layout(client, contexto, pasta_preparada, nome):
    contexto["resp"] = client.post(
        "/extracao/fontes", data=_form_fonte(nome, pasta_preparada, LAYOUT_EXTRATO),
        headers={"Accept": "text/html"}, follow_redirects=True,
    )


@when(parsers.parse('cadastro pela tela a fonte "{nome}" com transformação de coluna "{transf}"'))
def cadastra_layout_invalido(client, contexto, pasta_preparada, nome, transf):
    layout = dict(LAYOUT_EXTRATO, colunas=[{"origem": 0, "destino": "cod_banco",
                                          "transformacao": transf}])
    contexto["resp"] = client.post(
        "/extracao/fontes", data=_form_fonte(nome, pasta_preparada, layout),
        headers={"Accept": "text/html"}, follow_redirects=True,
    )


@when(parsers.parse('faço o preview do arquivo "{fixture}" com o layout de extrato'))
def faz_preview(app, client, contexto, fixture):
    from fluxocaixa.models import ExecucaoExtracao

    contexto["exec_antes"] = ExecucaoExtracao.query.count()
    conteudo = (FIXTURES / fixture).read_bytes()
    contexto["resp"] = client.post(
        "/extracao/fontes/preview-layout",
        data={"json_layout_raw": json.dumps(LAYOUT_EXTRATO)},
        files={"arquivo": (fixture, conteudo, "text/csv")},
    )


# --------------------------------------------------------------------------
# Então
# --------------------------------------------------------------------------

@then("o formulário mostra a seção de layout do arquivo")
def form_tem_layout(contexto):
    assert 'data-testid="secao-layout"' in contexto["resp"].text


@then("o formulário não mostra a seção de layout do arquivo")
def form_sem_layout(contexto):
    assert 'data-testid="secao-layout"' not in contexto["resp"].text


@then(parsers.parse('a fonte "{nome}" tem o layout salvo'))
def fonte_tem_layout(nome):
    fonte = fonte_por_nome(nome)
    assert fonte is not None
    assert fonte.json_layout and fonte.json_layout.get("colunas")


@then(parsers.parse('executar a fonte "{nome}" para o dia "{dia}" grava {n:d} saldos'))
def executar_grava(app, nome, dia, n):
    from fluxocaixa.extracao.conector import Janela
    from fluxocaixa.services.extracao_service import executar_fonte

    d = date.fromisoformat(dia)
    fonte = fonte_por_nome(nome)
    execucao = executar_fonte(fonte.seq_fonte_extracao, janela=Janela(d, d))
    assert execucao.qtd_linhas_inseridas == n, (
        f"esperava {n}, veio {execucao.qtd_linhas_inseridas} "
        f"(status {execucao.cod_status}, detalhe {execucao.txt_detalhe_erros})"
    )


@then("o formulário de edição traz o layout salvo")
def edicao_traz_layout(contexto):
    html = contexto["resp"].text
    assert 'data-testid="secao-layout"' in html
    # o layout salvo é injetado para o JS pré-popular
    assert "somente_digitos" in html or "codigo_antes_hifen" in html


@then("o cadastro pela tela de layout é rejeitado")
def cadastro_layout_rejeitado(contexto):
    resp = contexto["resp"]
    assert resp.status_code == 200
    assert "inexistente" in resp.text.lower() or "transforma" in resp.text.lower()


@then(parsers.parse('a fonte "{nome}" não existe'))
def fonte_nao_existe(nome):
    assert fonte_por_nome(nome) is None


@then(parsers.parse("o preview retorna {n_linhas:d} linhas e {n_erros:d} erros"))
def preview_linhas_erros(contexto, n_linhas, n_erros):
    resp = contexto["resp"]
    assert resp.status_code == 200, resp.text
    dados = resp.json()
    assert len(dados["linhas"]) == n_linhas
    assert len(dados["erros"]) == n_erros


@then("o preview não registra execução")
def preview_sem_execucao(app, contexto):
    from fluxocaixa.models import ExecucaoExtracao
    from fluxocaixa.models.base import db

    db.session.expire_all()
    assert ExecucaoExtracao.query.count() == contexto["exec_antes"]


@then("o preview informa arquivo rejeitado")
def preview_rejeitado(contexto):
    resp = contexto["resp"]
    assert resp.status_code == 200, resp.text
    assert resp.json().get("rejeitado") is True
