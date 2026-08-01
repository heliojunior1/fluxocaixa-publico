"""DTOs da execução manual de fonte de extração (spec extracao-configuravel R6)."""
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ExecucaoManualIn(BaseModel):
    """Janela opcional de backfill — par validado no serviço (`montar_janela`)."""

    model_config = ConfigDict(populate_by_name=True)

    data_inicio: date | None = Field(default=None, alias="dataInicio")
    data_fim: date | None = Field(default=None, alias="dataFim")


class ExecucaoOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    seq_execucao_extracao: int = Field(serialization_alias="seqExecucao")
    cod_status: str = Field(serialization_alias="codStatus")
    cod_disparo: str = Field(serialization_alias="codDisparo")
    dat_inicio_execucao: datetime = Field(serialization_alias="datInicioExecucao")
    num_duracao_segundos: Decimal | None = Field(
        default=None, serialization_alias="numDuracaoSegundos"
    )
    dat_janela_inicio: date = Field(serialization_alias="datJanelaInicio")
    dat_janela_fim: date = Field(serialization_alias="datJanelaFim")
    qtd_linhas_inseridas: int = Field(serialization_alias="qtdLinhasInseridas")
    qtd_linhas_erro: int = Field(serialization_alias="qtdLinhasErro")
    qtd_fundos_auto_cadastrados: int = Field(
        serialization_alias="qtdFundosAutoCadastrados"
    )
