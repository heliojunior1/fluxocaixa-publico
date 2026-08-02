"""Dotação + créditos adicionais (spec execucao-orcamentaria R1–R2).

Primeira gradação do funil LOA → caixa: o AUTORIZADO vivo. `flc_dotacao` é o
cabeçalho (inicial por ano × qualificador folha de despesa, único entre
ativos); `flc_credito_adicional` é o livro — eventos imutáveis e datados com
referência do ato obrigatória (art. 167 CF). ⚠️ A dotação ATUALIZADA é sempre
derivada dos eventos (`dotacao_service.dotacao_atualizada`), nunca coluna —
princípio do liberado pendente. Corrigir evento é lançar o contrário.
"""
from datetime import date

from sqlalchemy import Column, Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship

from .base import Base

#: suplementar / especial / extraordinário somam; redução-anulação subtrai
TIPOS_CREDITO_SOMA = ('S', 'E', 'X')
TIPO_CREDITO_REDUCAO = 'R'


class Dotacao(Base):
    __tablename__ = 'flc_dotacao'

    seq_dotacao = Column(Integer, primary_key=True)
    num_ano = Column(Integer, nullable=False)
    seq_qualificador = Column(
        Integer, ForeignKey('flc_qualificador.seq_qualificador'), nullable=False)
    val_dotacao_inicial = Column(Numeric(18, 2), nullable=False)
    ind_status = Column(String(1), default='A', nullable=False)
    dat_inclusao = Column(Date, default=date.today, nullable=False)
    cod_pessoa_inclusao = Column(Integer)
    dat_alteracao = Column(Date)
    cod_pessoa_alteracao = Column(Integer)

    qualificador = relationship('Qualificador')
    creditos = relationship('CreditoAdicional', back_populates='dotacao')


class CreditoAdicional(Base):
    __tablename__ = 'flc_credito_adicional'

    seq_credito = Column(Integer, primary_key=True)
    seq_dotacao = Column(Integer, ForeignKey('flc_dotacao.seq_dotacao'), nullable=False)
    cod_tipo_credito = Column(String(1), nullable=False)
    val_credito = Column(Numeric(18, 2), nullable=False)
    dat_credito = Column(Date, nullable=False)
    #: lei/decreto que abriu o crédito — evento sem ato legal não existe
    dsc_referencia_ato = Column(String(120), nullable=False)
    ind_status = Column(String(1), default='A', nullable=False)
    dat_inclusao = Column(Date, default=date.today, nullable=False)
    cod_pessoa_inclusao = Column(Integer)

    dotacao = relationship('Dotacao', back_populates='creditos')
