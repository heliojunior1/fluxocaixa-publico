"""Staging genérica da automação de lançamentos (spec automacao-lancamentos R1).

Área de pouso dos dados brutos de fontes com destino LANCAMENTO: colunas
universais (data, valor, ano) + `json_atributos` com a linha CRUA da origem
(classificadores específicos da SEFAZ). As regras da F4.2 consultam o JSON.

É área de trabalho recarregável — NÃO tem soft-delete (`ind_status`); a F4.3
reprocessa/recarrega. Controle de processamento por linha:
`ind_status_processamento` 0=pendente / 1=ok / 2=erro.
"""
from datetime import date

from sqlalchemy import (
    JSON,
    Column,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
)

from .base import Base

STATUS_PENDENTE = '0'
STATUS_OK = '1'
STATUS_ERRO = '2'

DSC_ERRO_MAX = 500


class EtlStaging(Base):
    """Linha crua de lançamento aguardando classificação (F4.2)."""

    __tablename__ = 'flc_etl_staging'
    __table_args__ = (
        Index('ix_flc_etl_staging_fonte_data', 'seq_fonte_extracao', 'dat_referencia'),
        Index('ix_flc_etl_staging_exec_status',
              'seq_execucao_extracao', 'ind_status_processamento'),
        # o processamento (F4.3) junta por fonte, não por execução
        Index('ix_flc_etl_staging_fonte_status',
              'seq_fonte_extracao', 'ind_status_processamento'),
    )

    seq_etl_staging = Column(Integer, primary_key=True)
    seq_fonte_extracao = Column(
        Integer, ForeignKey('flc_fonte_extracao.seq_fonte_extracao'), nullable=False
    )
    seq_execucao_extracao = Column(
        Integer, ForeignKey('flc_execucao_extracao.seq_execucao_extracao'), nullable=False
    )
    num_ano_exercicio = Column(Integer)
    dat_referencia = Column(Date)
    val_referencia = Column(Numeric(18, 2))
    json_atributos = Column(JSON)  # a linha crua da origem
    ind_status_processamento = Column(String(1), default=STATUS_PENDENTE, nullable=False)
    dsc_erro = Column(String(DSC_ERRO_MAX))
    dat_inclusao = Column(Date, default=date.today, nullable=False)
    cod_pessoa_inclusao = Column(Integer)
    dat_alteracao = Column(Date)
    cod_pessoa_alteracao = Column(Integer)
