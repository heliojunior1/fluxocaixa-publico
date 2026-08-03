"""Conector de banco SQL externo (spec R21).

Consulta um banco SQL de referência (Oracle, PostgreSQL, etc.) com uma
query parametrizável e traz os saldos para o modelo por fundo. Genérico: URL
SQLAlchemy, query com **bind parameters** (`:data_inicio`/`:data_fim`/`:ano`
— nunca substituição textual), somente-leitura (só SELECT/WITH), streaming em
lotes e mapeamento coluna→campo (reusa `mapeamento_json`). O ERP contábil externo é apenas a
configuração de referência.

Sem dependência nova: SQLAlchemy já é dependência; o driver do banco externo
(oracledb, pymysql, pyodbc, ...) é instalado pelo usuário conforme o dialeto.
Destino SALDO_FUNDO apenas — LANCAMENTO (staging, sinal contábil) é da Fase 4.
"""
import re

import sqlalchemy as sa
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..conector import Janela, ResultadoTeste
from ..mapeamento_json import LayoutApiRest, mapear_item

# Bind parameters que o conector fornece a partir da janela.
_BINDS_DISPONIVEIS = ("data_inicio", "data_fim", "ano")
_INICIO_LEITURA = ("SELECT", "WITH")


def _normalizar_query(query: str) -> str:
    """Remove comentários (`--` e `/* */`) e espaços para checar o comando."""
    sem_bloco = re.sub(r"/\*.*?\*/", " ", query, flags=re.DOTALL)
    sem_linha = re.sub(r"--[^\n]*", " ", sem_bloco)
    return sem_linha.strip()


class ConfigBancoSql(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # URL SQLAlchemy contém credenciais → secreta (${VAR})
    url_conexao: str = Field(json_schema_extra={"secreto": True})
    query: str
    cod_banco: str
    batch_size: int = 5000

    @field_validator("query")
    @classmethod
    def _somente_leitura(cls, v: str) -> str:
        normalizada = _normalizar_query(v)
        if not normalizada.upper().startswith(_INICIO_LEITURA):
            raise ValueError(
                "query deve começar com SELECT ou WITH (somente leitura)"
            )
        return v

    @field_validator("url_conexao")
    @classmethod
    def _destino_confinado(cls, v: str) -> str:
        """Confina o destino (R23): host interno e SQLite fora da raiz.

        `sqlite:////caminho/qualquer.db` é leitura de arquivo local com outra
        roupa — fechar só o conector de arquivo deixaria a porta dos fundos.
        """
        from ..confinamento import validar_url_conexao

        validar_url_conexao(v)
        return v

    @field_validator("batch_size")
    @classmethod
    def _batch_positivo(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("batch_size deve ser positivo")
        return v


def _montar_stmt(query: str, janela: Janela):
    """`text(query)` com bind params — só os que a query referencia."""
    valores = {
        "data_inicio": janela.data_inicio,
        "data_fim": janela.data_fim,
        "ano": janela.data_fim.year,
    }
    usados = {p: valores[p] for p in _BINDS_DISPONIVEIS if f":{p}" in query}
    stmt = sa.text(query)
    if usados:
        stmt = stmt.bindparams(**usados)
    return stmt


class ConectorBancoSql:
    tipo = "BANCO_SQL"
    layout_kind = "MAPEAMENTO"
    schema_config = ConfigBancoSql
    schema_layout = LayoutApiRest  # mapeamento coluna→campo (caminho = coluna)

    def testar_conexao(self, config: dict) -> ResultadoTeste:
        engine = None
        try:
            engine = sa.create_engine(config["url_conexao"])
            with engine.connect() as conn:
                conn.execute(sa.text("SELECT 1"))
            return ResultadoTeste(ok=True, mensagem="Conexão SQL OK")
        except Exception as exc:  # URL inválida / driver ausente / recusada
            return ResultadoTeste(ok=False, mensagem=str(exc))
        finally:
            if engine is not None:
                engine.dispose()

    def extrair(self, config: dict, layout: dict | None, janela: Janela):
        layout = layout or {}
        stmt = _montar_stmt(config["query"], janela)
        # Erro de query/conexão propaga → execução ERRO (falha da fonte, não
        # de uma linha); erro de mapeamento por linha vira ErroLinha pontual.
        engine = sa.create_engine(config["url_conexao"])
        try:
            with engine.connect().execution_options(stream_results=True) as conn:
                result = conn.execute(stmt)
                for row in result.yield_per(config.get("batch_size", 5000)):
                    yield mapear_item(
                        dict(row._mapping), layout,
                        cod_banco=config["cod_banco"], agencia="", conta="",
                    )
        finally:
            engine.dispose()
