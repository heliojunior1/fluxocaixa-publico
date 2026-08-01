"""Testes unitários do motor de parser de arquivo (spec R14/R16).

Puros — sem banco. Verificam Decimal explícito, BOM, formatos e as
transformações declarativas com dados fictícios.
"""
from datetime import date
from decimal import Decimal

import pytest

# IMPORTANTE: NÃO importar `fluxocaixa` no topo — isso cria o engine ligado ao
# banco default durante a coleção do pytest, ANTES do fixture `app` definir
# DATABASE_URL=test.db (ver conftest). Imports são lazy dentro das funções.

LAYOUT = {
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

HEADER = "Banco;Agência;Conta;Data;Descrição;Saldo\n"


def _bytes(texto: str, com_bom: bool = True) -> bytes:
    enc = "utf-8-sig" if com_bom else "utf-8"
    return texto.encode(enc)


def _emitidos(conteudo: bytes):
    from fluxocaixa.extracao.conector import ErroLinha, LinhaExtraida
    from fluxocaixa.extracao.parser_arquivo import parsear

    itens = list(parsear(conteudo, LAYOUT, "teste.csv"))
    linhas = [e for e in itens if isinstance(e, LinhaExtraida)]
    erros = [e for e in itens if isinstance(e, ErroLinha)]
    return linhas, erros


def test_decimal_ptbr_preciso():
    linhas, erros = _emitidos(_bytes(HEADER + "104;0001;12345-6;10/07/2026;9999-ALFA;1.234.567,89\n"))
    assert not erros
    assert linhas[0].val_saldo == Decimal("1234567.89")


def test_bom_consumido():
    linhas, _ = _emitidos(_bytes(HEADER + "104;0001;12345-6;10/07/2026;9999-ALFA;10,00\n", com_bom=True))
    assert linhas[0].cod_banco == "104"  # sem prefixo de BOM


def test_data_e_conta_normalizada():
    linhas, _ = _emitidos(_bytes(HEADER + "104;0001;12.345-6;10/07/2026;9999-ALFA;10,00\n"))
    assert linhas[0].dat_saldo == date(2026, 7, 10)
    assert linhas[0].num_conta == "123456"


def test_codigo_antes_hifen():
    linhas, _ = _emitidos(_bytes(HEADER + "104;0001;12345-6;10/07/2026;5462-CAIXA FI BRASIL;10,00\n"))
    assert (linhas[0].cod_fundo, linhas[0].dsc_fundo) == ("5462", "CAIXA FI BRASIL")


def test_header_divergente_rejeita_arquivo():
    from fluxocaixa.extracao.parser_arquivo import ParserArquivoError, parsear

    ruim = "A;B;C;D;E;F\n" + "104;0001;12345-6;10/07/2026;9999-ALFA;10,00\n"
    with pytest.raises(ParserArquivoError):
        list(parsear(_bytes(ruim), LAYOUT, "ruim.csv"))


def test_linha_com_poucas_colunas_e_pontual():
    conteudo = HEADER + "104;0001;12345-6;10/07/2026;9999-ALFA;10,00\n" + "104;0001;SO_TRES\n"
    linhas, erros = _emitidos(_bytes(conteudo))
    assert len(linhas) == 1 and len(erros) == 1
    assert erros[0].numero == 3


def test_descricao_sem_hifen_vira_erro():
    linhas, erros = _emitidos(_bytes(HEADER + "104;0001;12345-6;10/07/2026;SEM CODIGO;10,00\n"))
    assert not linhas and len(erros) == 1


def test_decimal_us():
    from fluxocaixa.extracao.conector import LinhaExtraida
    from fluxocaixa.extracao.parser_arquivo import parsear

    layout_us = dict(LAYOUT, formato_decimal="US")
    itens = list(parsear(_bytes(HEADER + "104;0001;12345-6;10/07/2026;9999-ALFA;1,234.56\n"), layout_us, "us.csv"))
    linhas = [e for e in itens if isinstance(e, LinhaExtraida)]
    assert linhas[0].val_saldo == Decimal("1234.56")
