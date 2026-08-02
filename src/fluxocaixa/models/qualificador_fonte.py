"""Repartição de qualificador de receita por fonte (spec fonte-recurso R8–R9).

Os percentuais-FALLBACK da repartição da projeção por grupo de
disponibilidade (estágio C da estampagem): a fatia do ICMS que nasce
vinculada (ex.: FUNDEB) não pode entrar como livre na simulação (F7.2).

⚠️ Três invariantes:
- a soma dos percentuais ativos de um (qualificador, vigência) é 100 —
  validada NO CONJUNTO pelo serviço (gravação atômica; linha avulsa
  permitiria estados intermediários visíveis);
- qualificador SEM repartição vai ao grupo 'N' (não classificado) — nunca ao
  livre (o erro para cima que a v2.1 removeu);
- quando existir carga de previsão por fonte do sistema de origem, o DADO
  vence os percentuais (precedência registrada no requirement).
"""
from datetime import date

from sqlalchemy import Column, Date, ForeignKey, Integer, Numeric, String

from .base import Base


class QualificadorFonte(Base):
    __tablename__ = 'flc_qualificador_fonte'

    seq_qualificador_fonte = Column(Integer, primary_key=True)
    seq_qualificador = Column(
        Integer, ForeignKey('flc_qualificador.seq_qualificador'), nullable=False)
    seq_fonte_recurso = Column(
        Integer, ForeignKey('flc_fonte_recurso.seq_fonte_recurso'), nullable=False)
    #: 0–100, quatro casas (repartições legais têm frações)
    pct_reparticao = Column(Numeric(7, 4), nullable=False)
    #: vigência anual — as repartições constitucionais mudam por lei
    num_ano_vigencia = Column(Integer, nullable=False)
    ind_status = Column(String(1), default='A', nullable=False)
    dat_inclusao = Column(Date, default=date.today, nullable=False)
    cod_pessoa_inclusao = Column(Integer)
    dat_alteracao = Column(Date)
    cod_pessoa_alteracao = Column(Integer)
