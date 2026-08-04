from datetime import date

from sqlalchemy import Column, Date, Integer, String

from .base import Base


class Orgao(Base):
    """Órgão — dimensão SOMENTE do desembolso (decisão da seção 5.1 do módulo).

    PK é o próprio código orçamentário (`cod_orgao`), como a referência
    identifica órgãos e como `flc_pagamento` já aponta. Status + auditoria
    chegaram na F7.1a (antes o cadastro era só seed, sem tela).
    """
    __tablename__ = 'flc_orgao'
    cod_orgao = Column(Integer, primary_key=True)
    nom_orgao = Column(String(100), nullable=False)
    # server_default espelha a migração 0019 (ALTER em tabela populada exige
    # default no banco; sem espelhar aqui o anti-deriva acusaria diferença)
    ind_status = Column(String(1), default='A', server_default='A', nullable=False)
    # nullable como na 0016: linhas pré-existentes (seed antigo) ficam nulas
    dat_inclusao = Column(Date, default=date.today, nullable=True)
    cod_pessoa_inclusao = Column(Integer)
    dat_alteracao = Column(Date)
    cod_pessoa_alteracao = Column(Integer)
