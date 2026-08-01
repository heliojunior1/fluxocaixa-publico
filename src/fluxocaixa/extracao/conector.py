"""Contrato de conector da extração embutida (spec extracao-configuravel R2).

Um conector é um plugin: declara `tipo` (chave do registry), `schema_config`
(modelo Pydantic que valida o `json_config` da fonte e marca campos secretos
com `json_schema_extra={"secreto": True}`), sabe testar conexão e extrair
linhas para uma janela de datas. Conectores de produção chegam nas features
F3.2 (FTP/arquivo), F3.3 (API REST) e F3.4 (banco SQL).
"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable, Protocol, runtime_checkable

from pydantic import BaseModel


@dataclass(frozen=True)
class Janela:
    """Intervalo de datas de uma execução (inclusive nas duas pontas)."""

    data_inicio: date
    data_fim: date


@dataclass
class LinhaExtraida:
    """Linha normalizada que o conector entrega ao núcleo (vira `LinhaLote`)."""

    cod_banco: str
    num_agencia: str
    num_conta: str
    cod_fundo: str
    dsc_fundo: str
    val_saldo: Decimal
    val_aplicacoes: Decimal = Decimal("0")
    val_resgates: Decimal = Decimal("0")
    dat_saldo: date | None = None  # default: data fim da janela
    # Linha crua da origem, preenchida quando o layout liga `capturar_atributos`
    # (destino LANCAMENTO → staging). O caminho de saldo ignora este campo.
    json_atributos: dict | None = None


@dataclass
class ErroLinha:
    """Erro de conteúdo em UMA linha do arquivo — pontual, não aborta a extração.

    Conectores de arquivo (F3.2) emitem `ErroLinha` para linhas malformadas;
    `executar_fonte` soma-os aos erros do lote (spec R2/R3). Conectores que não
    produzem erros de linha (DEMO_MANUAL, ConectorFake) emitem só `LinhaExtraida`.
    """

    numero: int          # linha no arquivo (1-based, conta o header)
    arquivo: str         # nome do arquivo de origem
    mensagem: str        # motivo pt-BR, sem stack
    # aviso informativo (ex.: "API sem histórico"): vai ao detalhe da
    # execução, mas NÃO conta como erro (não incrementa qtd_linhas_erro)
    aviso: bool = False


@dataclass
class ResultadoTeste:
    ok: bool
    mensagem: str


@runtime_checkable
class Conector(Protocol):
    tipo: str
    schema_config: type[BaseModel]

    def testar_conexao(self, config: dict) -> ResultadoTeste:
        ...

    def extrair(
        self, config: dict, layout: dict | None, janela: Janela
    ) -> Iterable[LinhaExtraida | ErroLinha]:
        ...
