"""Steps BDD — conector de arquivo e motor de parser (spec R2/R3, R14–R16)."""
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from ..conftest_extracao import (
    execucoes_da_fonte,
    fonte_por_nome,
    garantir_conta,
    garantir_sistema_origem,
)

scenarios("../extracao-configuravel/conector_arquivo.feature")

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
def pasta_arquivos(tmp_path):
    d = tmp_path / "arquivos"
    d.mkdir()
    return d


def _garantir_conector_arquivo():
    from fluxocaixa.extracao import registry
    from fluxocaixa.extracao.conectores.ftp_arquivo import ConectorFtpArquivo

    if "FTP_ARQUIVO" not in registry.tipos_disponiveis():
        registry.registrar(ConectorFtpArquivo())


def _criar_fonte_arquivo(nome, pasta, *, json_layout=None):
    from fluxocaixa.services.extracao_service import criar_fonte

    return criar_fonte(
        nom_fonte=nome,
        cod_tipo_conector="FTP_ARQUIVO",
        sigla_sistema="SIS_X",
        json_config={
            "protocolo": "PASTA_LOCAL",
            "diretorio": str(pasta),
            "padrao_nome": PADRAO_NOME,
        },
        json_layout=json_layout if json_layout is not None else LAYOUT_EXTRATO,
    )


def _escrever_arquivo_do_dia(pasta, fixture, dia: date):
    conteudo = (FIXTURES / fixture).read_bytes()
    destino = pasta / PADRAO_NOME.format(dia)
    destino.write_bytes(conteudo)


def _dia(s: str) -> date:
    return date.fromisoformat(s)


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


@given(parsers.parse('o arquivo de exemplo "{fixture}" com o layout de extrato'))
def arquivo_de_exemplo(contexto, fixture):
    contexto["conteudo"] = (FIXTURES / fixture).read_bytes()
    contexto["nome_arquivo"] = fixture


@given(parsers.parse('uma conta de arquivo "{ident}"'))
def conta_de_arquivo(app, ident):
    garantir_conta(ident)


@given(parsers.parse('uma fonte de arquivo "{nome}" com o arquivo "{fixture}" para o dia "{dia}"'))
def fonte_com_arquivo(app, pasta_arquivos, nome, fixture, dia):
    _escrever_arquivo_do_dia(pasta_arquivos, fixture, _dia(dia))
    _criar_fonte_arquivo(nome, pasta_arquivos)


@given(parsers.parse('uma fonte de arquivo "{nome}" sem arquivo para o dia "{dia}"'))
def fonte_sem_arquivo(app, pasta_arquivos, nome, dia):
    _criar_fonte_arquivo(nome, pasta_arquivos)


# --------------------------------------------------------------------------
# Quando
# --------------------------------------------------------------------------

@when("parseio o arquivo pelo layout")
def parseia_arquivo(contexto):
    from fluxocaixa.extracao.conector import ErroLinha, LinhaExtraida
    from fluxocaixa.extracao.parser_arquivo import ParserArquivoError, parsear

    try:
        emitidos = list(parsear(contexto["conteudo"], LAYOUT_EXTRATO, contexto["nome_arquivo"]))
        contexto["linhas"] = [e for e in emitidos if isinstance(e, LinhaExtraida)]
        contexto["erros"] = [e for e in emitidos if isinstance(e, ErroLinha)]
        contexto["arquivo_rejeitado"] = False
    except ParserArquivoError:
        contexto["arquivo_rejeitado"] = True


@when(parsers.parse('cadastro uma fonte de arquivo com transformação de layout "{transf}"'))
def cadastra_transformacao_invalida(app, pasta_arquivos, contexto, transf):
    from fluxocaixa.services.validacao import RegraNegocioError

    layout = dict(LAYOUT_EXTRATO)
    layout["colunas"] = [
        {"origem": 0, "destino": "cod_banco", "transformacao": transf},
    ]
    try:
        _criar_fonte_arquivo("Fonte Transf Ruim", pasta_arquivos, json_layout=layout)
        contexto["erro_cadastro"] = None
    except RegraNegocioError as exc:
        contexto["erro_cadastro"] = exc.mensagem


@when(parsers.parse('cadastro uma fonte de arquivo com padrão de nome "{padrao}"'))
def cadastra_padrao_traversal(app, pasta_arquivos, contexto, padrao):
    from fluxocaixa.services.extracao_service import criar_fonte
    from fluxocaixa.services.validacao import RegraNegocioError

    try:
        criar_fonte(
            nom_fonte="Fonte Traversal",
            cod_tipo_conector="FTP_ARQUIVO",
            sigla_sistema="SIS_X",
            json_config={
                "protocolo": "PASTA_LOCAL",
                "diretorio": str(pasta_arquivos),
                "padrao_nome": padrao,
            },
            json_layout=LAYOUT_EXTRATO,
        )
        contexto["erro_cadastro"] = None
    except RegraNegocioError as exc:
        contexto["erro_cadastro"] = exc.mensagem


@when(parsers.parse('executo a fonte de arquivo "{nome}" para o dia "{dia}"'))
def executa_fonte_dia(app, contexto, nome, dia):
    from fluxocaixa.extracao.conector import Janela
    from fluxocaixa.services.extracao_service import executar_fonte

    contexto["fonte_nome"] = nome
    d = _dia(dia)
    fonte = fonte_por_nome(nome)
    executar_fonte(fonte.seq_fonte_extracao, janela=Janela(data_inicio=d, data_fim=d))


@when(parsers.parse('executo a fonte de arquivo "{nome}" de "{ini}" a "{fim}"'))
def executa_fonte_janela(app, contexto, nome, ini, fim):
    from fluxocaixa.extracao.conector import Janela
    from fluxocaixa.services.extracao_service import executar_fonte

    contexto["fonte_nome"] = nome
    fonte = fonte_por_nome(nome)
    executar_fonte(
        fonte.seq_fonte_extracao,
        janela=Janela(data_inicio=_dia(ini), data_fim=_dia(fim)),
    )


# --------------------------------------------------------------------------
# Então
# --------------------------------------------------------------------------

@then(parsers.parse("obtenho {n_linhas:d} linhas e {n_erros:d} erros de linha"))
def obtenho_linhas_erros(contexto, n_linhas, n_erros):
    assert not contexto.get("arquivo_rejeitado"), "arquivo foi rejeitado inteiro"
    assert len(contexto["linhas"]) == n_linhas
    assert len(contexto["erros"]) == n_erros


@then(parsers.parse('a primeira linha tem saldo "{valor}" e fundo "{cod}"'))
def primeira_linha_saldo_fundo(contexto, valor, cod):
    linha = contexto["linhas"][0]
    assert linha.val_saldo == Decimal(valor)
    assert linha.cod_fundo == cod


@then(parsers.parse('a primeira linha tem número de conta "{num}"'))
def primeira_linha_conta(contexto, num):
    assert contexto["linhas"][0].num_conta == num


@then(parsers.parse('a primeira linha tem fundo "{cod}" e descrição "{dsc}"'))
def primeira_linha_fundo_dsc(contexto, cod, dsc):
    linha = contexto["linhas"][0]
    assert linha.cod_fundo == cod
    assert linha.dsc_fundo == dsc


@then("o parse rejeita o arquivo inteiro")
def parse_rejeita(contexto):
    assert contexto.get("arquivo_rejeitado") is True


@then(parsers.parse("algum erro de linha aponta a linha {n:d}"))
def erro_aponta_linha(contexto, n):
    assert any(e.numero == n for e in contexto["erros"])


@then("o primeiro campo de dados não contém caractere de BOM")
def sem_bom(contexto):
    assert contexto["linhas"][0].cod_banco == "104"
    assert "﻿" not in contexto["linhas"][0].cod_banco


@then("o cadastro de arquivo é rejeitado")
def cadastro_rejeitado(contexto):
    assert contexto["erro_cadastro"] is not None


@then(parsers.parse('a execução de arquivo registra status "{status}" com {ok:d} inseridas e {erro:d} com erro'))
def execucao_arquivo_status(contexto, status, ok, erro):
    execucoes = execucoes_da_fonte(contexto["fonte_nome"])
    assert execucoes, f"nenhuma execução para {contexto['fonte_nome']!r}"
    e = execucoes[-1]
    assert e.cod_status == status, (
        f"esperava {status}, veio {e.cod_status} (detalhe: {e.txt_detalhe_erros!r})"
    )
    assert (e.qtd_linhas_inseridas, e.qtd_linhas_erro) == (ok, erro)
