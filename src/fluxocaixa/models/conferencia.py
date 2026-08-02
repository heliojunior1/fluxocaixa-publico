"""Conferência do desembolso (spec desembolso R14–R16).

Reconstruída na F7.1c: o grão continua o DIA, mas a tabela guarda apenas os
**valores apurados de fonte externa** — o que se digita/importa para conferir
contra o calculado. ⚠️ Todas as colunas deriváveis da versão antiga (saldo
anterior, liberações, pagamentos, saldo final…) SUMIRAM: são função de
liberações/apropriações/lançamentos/transferências e são calculadas na
leitura (`conferencia_desembolso_service`) — persistir criaria uma segunda
verdade (princípio do saldo agregado F2.1).
"""
from datetime import date

from sqlalchemy import Column, Date, Integer, Numeric, String

from .base import Base


class Conferencia(Base):
    __tablename__ = 'flc_conferencia'

    dat_conferencia = Column(Date, primary_key=True)
    #: apurado de fonte externa para as liberações do dia (opcional)
    val_apurado_liberacoes = Column(Numeric(18, 2))
    #: apurado de fonte externa para os pagamentos do dia (opcional)
    val_apurado_pagamentos = Column(Numeric(18, 2))
    ind_status = Column(String(1), default='A', nullable=False, server_default='A')
    dat_inclusao = Column(Date, default=date.today, nullable=True)
    cod_pessoa_inclusao = Column(Integer)
    dat_alteracao = Column(Date)
    cod_pessoa_alteracao = Column(Integer)
