"""Motor de parsing de arquivo texto dirigido por layout (spec R14/R16).

Genérico e parametrizável por `json_layout` — o extrato bancário em arquivo texto é apenas uma
configuração de referência, nada é fixo por banco. Puro (sem I/O): recebe
`bytes` e o layout, devolve `LinhaExtraida | ErroLinha`. Header divergente
(quando há `header_esperado`) rejeita o arquivo inteiro (`ParserArquivoError`);
erro de conteúdo em uma linha vira `ErroLinha` pontual, sem abortar as demais.
"""
import csv
import io
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from pydantic import BaseModel, ConfigDict, field_validator

from .conector import ErroLinha, LinhaExtraida

# Campos de destino válidos de LinhaExtraida (o composto trata 1 col → 2 campos)
_DESTINOS_SIMPLES = {
    "cod_banco", "num_agencia", "num_conta", "cod_fundo", "dsc_fundo",
    "val_saldo", "val_aplicacoes", "val_resgates", "dat_saldo",
}
_DESTINO_COMPOSTO = "cod_fundo+dsc_fundo"


class ParserArquivoError(Exception):
    """Arquivo inteiro rejeitado (ex.: header divergente do esperado)."""


class ColunaLayout(BaseModel):
    model_config = ConfigDict(extra="forbid")

    origem: int | str            # índice (int) ou nome de header (str)
    destino: str
    transformacao: str | None = None

    @field_validator("destino")
    @classmethod
    def _destino_valido(cls, v: str) -> str:
        if v != _DESTINO_COMPOSTO and v not in _DESTINOS_SIMPLES:
            raise ValueError(
                f"destino inválido: '{v}' "
                f"(válidos: {', '.join(sorted(_DESTINOS_SIMPLES))} ou '{_DESTINO_COMPOSTO}')"
            )
        return v


class LayoutArquivo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    separador: str = ";"
    encoding: str = "utf-8-sig"
    tem_header: bool = True
    header_esperado: list[str] | None = None
    formato_data: str = "%d/%m/%Y"
    formato_decimal: str = "PT_BR"       # PT_BR | US
    colunas: list[ColunaLayout]

    @field_validator("formato_decimal")
    @classmethod
    def _decimal_valido(cls, v: str) -> str:
        if v not in ("PT_BR", "US"):
            raise ValueError("formato_decimal deve ser 'PT_BR' ou 'US'")
        return v

    @field_validator("colunas")
    @classmethod
    def _transformacoes_conhecidas(cls, cols: list[ColunaLayout]) -> list[ColunaLayout]:
        for c in cols:
            if c.transformacao is not None and c.transformacao not in TRANSFORMACOES:
                raise ValueError(
                    f"transformação desconhecida: '{c.transformacao}' "
                    f"(disponíveis: {', '.join(sorted(TRANSFORMACOES))})"
                )
        return cols


# --------------------------------------------------------------------------
# Transformações declarativas — registro extensível (R16)
# --------------------------------------------------------------------------

def _somente_digitos(valor: str, layout: LayoutArquivo):
    return re.sub(r"[^0-9]", "", valor)


def _codigo_antes_hifen(valor: str, layout: LayoutArquivo):
    """Uma coluna → (cod_fundo, dsc_fundo). Parte esquerda deve ser numérica."""
    if "-" not in valor:
        raise ValueError(f"descrição sem '-' separando o código do fundo: '{valor}'")
    cod, _, dsc = valor.partition("-")
    cod, dsc = cod.strip(), dsc.strip()
    if not re.fullmatch(r"\d+", cod):
        raise ValueError(f"código de fundo não numérico: '{cod}'")
    return cod, dsc


def _data(valor: str, layout: LayoutArquivo) -> date:
    return datetime.strptime(valor, layout.formato_data).date()


def _decimal(valor: str, layout: LayoutArquivo) -> Decimal:
    if not valor or not any(c.isdigit() for c in valor):
        raise ValueError(f"valor decimal inválido: '{valor}'")
    if layout.formato_decimal == "PT_BR":
        normalizado = valor.replace(".", "").replace(",", ".")
    else:  # US
        normalizado = valor.replace(",", "")
    try:
        return Decimal(normalizado).quantize(Decimal("0.01"))
    except InvalidOperation:
        raise ValueError(f"valor decimal inválido: '{valor}'")


# nome → callable(valor:str, layout) -> valor transformado (ou tupla no composto)
TRANSFORMACOES = {
    "somente_digitos": _somente_digitos,
    "codigo_antes_hifen": _codigo_antes_hifen,
    "data": _data,
    "decimal": _decimal,
}


# --------------------------------------------------------------------------
# Motor
# --------------------------------------------------------------------------

def _indice(coluna: ColunaLayout, header: list[str] | None, nome_arquivo: str) -> int:
    if isinstance(coluna.origem, int):
        return coluna.origem
    if header is None:
        raise ParserArquivoError(
            f"{nome_arquivo}: coluna por nome '{coluna.origem}' exige header"
        )
    try:
        return header.index(coluna.origem)
    except ValueError:
        raise ParserArquivoError(
            f"{nome_arquivo}: coluna '{coluna.origem}' ausente no header"
        )


def _aplicar_coluna(coluna: ColunaLayout, valor: str, layout: LayoutArquivo, destino: dict):
    valor = valor.strip()
    if coluna.transformacao:
        resultado = TRANSFORMACOES[coluna.transformacao](valor, layout)
    else:
        resultado = valor
    if coluna.destino == _DESTINO_COMPOSTO:
        destino["cod_fundo"], destino["dsc_fundo"] = resultado
    else:
        destino[coluna.destino] = resultado


def parsear(conteudo: bytes, layout: dict, nome_arquivo: str):
    """Gera `LinhaExtraida | ErroLinha` a partir do conteúdo bruto e do layout.

    `ParserArquivoError` (arquivo inteiro rejeitado) para header divergente.
    """
    cfg = LayoutArquivo.model_validate(layout)
    texto = io.TextIOWrapper(io.BytesIO(conteudo), encoding=cfg.encoding, newline="")
    reader = csv.reader(texto, delimiter=cfg.separador)

    header = None
    primeira_linha_dados = 1
    if cfg.tem_header:
        try:
            header = [c.strip() for c in next(reader)]
        except StopIteration:
            header = []
        primeira_linha_dados = 2
        if cfg.header_esperado is not None and header != cfg.header_esperado:
            raise ParserArquivoError(
                f"{nome_arquivo}: header {header} diverge do esperado "
                f"{cfg.header_esperado} — arquivo rejeitado"
            )

    n_colunas = len(cfg.colunas)
    indices = [_indice(c, header, nome_arquivo) for c in cfg.colunas]

    for i, row in enumerate(reader, start=primeira_linha_dados):
        if not row or all(not c.strip() for c in row):
            continue  # linha em branco
        max_idx = max(indices) if indices else -1
        if len(row) <= max_idx:
            yield ErroLinha(
                numero=i, arquivo=nome_arquivo,
                mensagem=f"linha com {len(row)} colunas, insuficiente para o layout ({n_colunas})",
            )
            continue
        destino: dict = {}
        try:
            for coluna, idx in zip(cfg.colunas, indices):
                _aplicar_coluna(coluna, row[idx], cfg, destino)
            yield LinhaExtraida(
                cod_banco=destino.get("cod_banco", ""),
                num_agencia=destino.get("num_agencia", ""),
                num_conta=destino.get("num_conta", ""),
                cod_fundo=destino.get("cod_fundo", ""),
                dsc_fundo=destino.get("dsc_fundo", ""),
                val_saldo=destino.get("val_saldo", Decimal("0")),
                val_aplicacoes=destino.get("val_aplicacoes", Decimal("0")),
                val_resgates=destino.get("val_resgates", Decimal("0")),
                dat_saldo=destino.get("dat_saldo"),
            )
        except ValueError as exc:
            yield ErroLinha(numero=i, arquivo=nome_arquivo, mensagem=str(exc))
