"""Log de processamento de mapeamento (spec automacao-lancamentos R15).

Espelha `flc_execucao_extracao` de propósito — mesmo vocabulário de status e
disparo, mesma tela mental.

Por que não reusar a execução de extração: o grão mente. Processamento é por
**mapeamento** (um sistema de origem tem N fontes), e o **resync não tem
execução de extração onde se pendurar** — ele nasce de alguém editar uma regra.
"""
from datetime import date

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import relationship

from .base import Base

DISPARO_AUTOMATICO = 'AUTOMATICO'
DISPARO_MANUAL = 'MANUAL'

STATUS_SUCESSO = 'SUCESSO'
STATUS_PARCIAL = 'PARCIAL'
STATUS_ERRO = 'ERRO'
STATUS_SEM_DADOS = 'SEM_DADOS'

LIMITE_DETALHE_ERROS = 4000


class ExecucaoMapeamento(Base):
    __tablename__ = 'flc_execucao_mapeamento'
    __table_args__ = (
        Index('ix_flc_execucao_mapeamento_map_data',
              'seq_mapeamento', 'dat_inicio_execucao'),
    )

    seq_execucao_mapeamento = Column(Integer, primary_key=True)
    seq_mapeamento = Column(
        Integer, ForeignKey('flc_mapeamento.seq_mapeamento'), nullable=False
    )
    dat_inicio_execucao = Column(DateTime, nullable=False)
    num_duracao_segundos = Column(Numeric(10, 3))
    cod_disparo = Column(String(10), nullable=False)   # AUTOMATICO | MANUAL
    cod_status = Column(String(10), nullable=False)    # SUCESSO|PARCIAL|ERRO|SEM_DADOS
    qtd_lancamentos_gerados = Column(Integer, default=0, nullable=False)
    qtd_linhas_erro = Column(Integer, default=0, nullable=False)
    qtd_lancamentos_removidos = Column(Integer, default=0, nullable=False)  # resync
    txt_detalhe_erros = Column(String(LIMITE_DETALHE_ERROS))
    dat_inclusao = Column(Date, default=date.today, nullable=False)
    cod_pessoa_inclusao = Column(Integer)

    mapeamento = relationship('Mapeamento')
