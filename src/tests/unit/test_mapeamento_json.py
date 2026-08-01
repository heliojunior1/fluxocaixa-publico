"""Testes unitários do resolvedor de mapeamento JSON (spec R20).

Puros — sem banco. Imports de `fluxocaixa` lazy (isolamento de banco).
"""
from decimal import Decimal


LAYOUT = {
    "lista_path": "listaFundosInvestimento",
    "campos": [
        {"caminho": "codigoFundoInvestimento", "destino": "cod_fundo"},
        {"caminho": "nomeFundoInvestimento", "destino": "dsc_fundo"},
        {"caminho": "valorSaldoBruto", "destino": "val_saldo"},
    ],
}


def test_navegar_pontilhado():
    from fluxocaixa.extracao.mapeamento_json import navegar

    obj = {"a": {"b": [{"c": 42}]}}
    assert navegar(obj, "a.b.0.c") == 42


def test_itens_lista_path():
    from fluxocaixa.extracao.mapeamento_json import itens

    resp = {"listaFundosInvestimento": [{"x": 1}, {"x": 2}]}
    assert len(itens(resp, "listaFundosInvestimento")) == 2


def test_itens_sem_lista_path_um_item():
    from fluxocaixa.extracao.mapeamento_json import itens

    resp = {"codigoFundoInvestimento": 1}
    assert itens(resp, None) == [resp]


def test_mapear_item_decimal():
    from fluxocaixa.extracao.conector import LinhaExtraida
    from fluxocaixa.extracao.mapeamento_json import mapear_item

    item = {"codigoFundoInvestimento": 9101, "nomeFundoInvestimento": "ALFA",
            "valorSaldoBruto": 1850432.10}
    linha = mapear_item(item, LAYOUT, cod_banco="001", agencia="0001", conta="12345")
    assert isinstance(linha, LinhaExtraida)
    assert linha.cod_fundo == "9101"
    assert linha.num_conta == "12345"
    assert linha.val_saldo == Decimal("1850432.10")


def test_mapear_item_campo_ausente_vira_erro():
    from fluxocaixa.extracao.conector import ErroLinha
    from fluxocaixa.extracao.mapeamento_json import mapear_item

    item = {"nomeFundoInvestimento": "ALFA", "valorSaldoBruto": 10.0}
    r = mapear_item(item, LAYOUT, cod_banco="001", agencia="0001", conta="12345")
    assert isinstance(r, ErroLinha)
    assert "ausente" in r.mensagem


def test_transformacao_invalida_no_layout_rejeitada():
    import pytest
    from pydantic import ValidationError

    from fluxocaixa.extracao.mapeamento_json import LayoutApiRest

    with pytest.raises(ValidationError):
        LayoutApiRest.model_validate({
            "campos": [{"caminho": "x", "destino": "val_saldo", "transformacao": "decimal"}],
        })
