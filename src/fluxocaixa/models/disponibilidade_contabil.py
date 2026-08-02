"""Disponibilidade contábil/fiscal por fonte (spec fonte-recurso R10).

O número do RGF/balancete — vem da CONTABILIDADE, nunca é presumido
derivável do caixa (considera obrigações, RP, consignações). Carga por
planilha; revisão da mesma (data, fonte) inativa a anterior (histórico
preservado). Valor pode ser NEGATIVO (insuficiência reportada). A
conciliação com a operacional vive em `conciliacao_fonte_service`.
"""
from datetime import date

from sqlalchemy import Column, Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship

from .base import Base


class DisponibilidadeContabil(Base):
    __tablename__ = 'flc_disponibilidade_contabil'

    seq_disponibilidade = Column(Integer, primary_key=True)
    dat_referencia = Column(Date, nullable=False)
    seq_fonte_recurso = Column(
        Integer, ForeignKey('flc_fonte_recurso.seq_fonte_recurso'), nullable=False)
    val_disponibilidade = Column(Numeric(18, 2), nullable=False)
    ind_status = Column(String(1), default='A', nullable=False)
    dat_inclusao = Column(Date, default=date.today, nullable=False)
    cod_pessoa_inclusao = Column(Integer)
    dat_alteracao = Column(Date)
    cod_pessoa_alteracao = Column(Integer)

    fonte_recurso = relationship('FonteRecurso')
