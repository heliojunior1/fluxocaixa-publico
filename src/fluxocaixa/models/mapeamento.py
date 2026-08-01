"""Cabeçalho de mapeamento da automação de lançamentos (spec R6).

Um mapeamento é o cabeçalho (ano, tipo, sistema de origem) que agrupa N itens
(`flc_item_mapeamento`), cada um ligando um qualificador **folha** a uma regra
de classificação sobre a staging.

`seq_sistema_origem` é FK: implementações típicas usam um rótulo de texto livre
apenas porque não tem essa tabela — nós temos. Por isso a unicidade é
(ano, tipo, sistema_origem) entre ativos: somos multi-origem por construção.
"""
from datetime import date

from sqlalchemy import Column, Date, ForeignKey, Index, Integer, String
from sqlalchemy.orm import relationship

from .base import Base

TIPO_RECEITA = '1'
TIPO_DESPESA = '2'
TIPOS_VALIDOS = (TIPO_RECEITA, TIPO_DESPESA)


class Mapeamento(Base):
    __tablename__ = 'flc_mapeamento'
    __table_args__ = (
        # a chave de unicidade (validada no serviço, entre ativos)
        Index('ix_flc_mapeamento_chave',
              'num_ano_exercicio', 'ind_tipo', 'seq_sistema_origem'),
    )

    seq_mapeamento = Column(Integer, primary_key=True)
    num_ano_exercicio = Column(Integer, nullable=False)
    ind_tipo = Column(String(1), nullable=False)  # 1=Receita, 2=Despesa
    seq_sistema_origem = Column(
        Integer, ForeignKey('flc_sistema_origem.seq_sistema_origem'), nullable=False
    )
    dsc_mapeamento = Column(String(255), nullable=False)
    ind_status = Column(String(1), default='A', nullable=False)
    dat_inclusao = Column(Date, default=date.today, nullable=False)
    cod_pessoa_inclusao = Column(Integer)
    dat_alteracao = Column(Date)
    cod_pessoa_alteracao = Column(Integer)

    sistema_origem = relationship('SistemaOrigem')
    itens = relationship(
        'ItemMapeamento', back_populates='mapeamento',
        cascade='all, delete-orphan',
    )
