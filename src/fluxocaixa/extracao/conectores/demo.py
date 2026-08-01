"""Conector de demonstração DEMO_MANUAL (spec extracao-configuravel R13).

Andaime de E2E e demonstração local — NÃO é conector de produção. Registrado
apenas quando `EXTRACAO_DEMO_CONNECTOR` está habilitada. Produz uma única
linha de saldo fictícia a partir da própria configuração, para exercitar o
fluxo cadastrar → testar → executar → histórico sem depender de um sistema
externo. Os conectores reais chegam nas features F3.2 (FTP/arquivo), F3.3
(API REST) e F3.4 (banco SQL).
"""
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from ..conector import Janela, LinhaExtraida, ResultadoTeste


class ConfigDemo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cod_banco: str = Field(description="Código do banco (ex.: 001)")
    num_agencia: str = Field(description="Número da agência (ex.: 0001)")
    num_conta: str = Field(description="Número da conta (ex.: 12345-6)")
    cod_fundo: str = Field(description="Código do fundo (ex.: 9999)")
    dsc_fundo: str = Field(default="Fundo demonstração", description="Descrição do fundo")
    val_saldo: Decimal = Field(description="Valor de saldo fictício a gerar")
    # Campo secreto opcional — só para exercitar o mascaramento na tela
    token: str | None = Field(
        default=None,
        json_schema_extra={"secreto": True},
        description="Token de exemplo (referencie por ${VAR})",
    )


class ConectorDemoManual:
    tipo = "DEMO_MANUAL"
    schema_config = ConfigDemo

    def testar_conexao(self, config: dict) -> ResultadoTeste:
        return ResultadoTeste(ok=True, mensagem="Conector de demonstração pronto")

    def extrair(self, config: dict, layout: dict | None, janela: Janela):
        yield LinhaExtraida(
            cod_banco=config["cod_banco"],
            num_agencia=config["num_agencia"],
            num_conta=config["num_conta"],
            cod_fundo=config["cod_fundo"],
            dsc_fundo=config.get("dsc_fundo") or "Fundo demonstração",
            val_saldo=Decimal(str(config["val_saldo"])),
            dat_saldo=janela.data_fim,
        )
