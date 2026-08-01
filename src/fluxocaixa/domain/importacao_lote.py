"""DTOs do endpoint de ingestão de saldos em lote (spec saldo-por-fundo R16).

camelCase por alias — contrato estável para ETLs externos (Airflow etc.).
Valores monetários tipados como Decimal: o Pydantic converte da string do
JSON sem passar por float (preserva precisão).
"""
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class LinhaImportacaoIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    cod_banco: str = Field(alias="codBanco")
    num_agencia: str = Field(alias="numAgencia")
    num_conta: str = Field(alias="numConta")
    cod_fundo: str = Field(alias="codFundo")
    dsc_fundo: str = Field(default="", alias="dscFundo")
    val_saldo: Decimal = Field(alias="valSaldo")
    val_aplicacoes: Decimal = Field(default=Decimal("0"), alias="valAplicacoes")
    val_resgates: Decimal = Field(default=Decimal("0"), alias="valResgates")
    dat_saldo: date | None = Field(default=None, alias="datSaldo")


class LoteImportacaoIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    # Sigla do sistema de origem (EXTRATO_BANCARIO, ...) ou ausente → IMPORTADO
    origem: str | None = None
    dat_saldo: date = Field(alias="dataSaldo")
    arquivo_origem: str | None = Field(default=None, alias="arquivoOrigem")
    linhas: list[LinhaImportacaoIn] = Field(default_factory=list)


class DetalheErroOut(BaseModel):
    linha: int
    mensagem: str


class ResultadoImportacaoOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    linhas_inseridas: int = Field(serialization_alias="linhasInseridas")
    linhas_com_erro: int = Field(serialization_alias="linhasComErro")
    fundos_auto_cadastrados: list[str] = Field(serialization_alias="fundosAutoCadastrados")
    detalhe_erros: list[DetalheErroOut] = Field(serialization_alias="detalheErros")
    arquivo_origem: str | None = Field(default=None, serialization_alias="arquivoOrigem")
    falha_sistemica: bool = Field(serialization_alias="falhaSistemica")
