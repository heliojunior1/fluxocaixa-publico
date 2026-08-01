"""Item de mapeamento — qualificador folha + regra (spec R6).

Cada item liga um qualificador **folha** a uma `txt_regra` (linguagem de
negócio pt-BR, traduzida por `services/regra`). `ind_inversao_sinal` é só
persistido aqui; sua aplicação ao valor é da F4.3.

`dat_ultima_execucao` nasce sem consumidor: a F4.3 detecta item "sujo" por
`dat_alteracao > dat_ultima_execucao`. Criar a coluna agora evita uma segunda
migração.
"""
from datetime import date

from sqlalchemy import Column, Date, ForeignKey, Index, Integer, String
from sqlalchemy.orm import relationship

from .base import Base

TXT_REGRA_MAX = 2000

INVERSAO_NAO = '0'
INVERSAO_SIM = '1'


class ItemMapeamento(Base):
    __tablename__ = 'flc_item_mapeamento'
    __table_args__ = (
        Index('ix_flc_item_mapeamento_mapeamento', 'seq_mapeamento', 'ind_status'),
    )

    seq_item_mapeamento = Column(Integer, primary_key=True)
    seq_mapeamento = Column(
        Integer, ForeignKey('flc_mapeamento.seq_mapeamento'), nullable=False
    )
    seq_qualificador = Column(
        Integer, ForeignKey('flc_qualificador.seq_qualificador'), nullable=False
    )
    txt_regra = Column(String(TXT_REGRA_MAX))
    ind_inversao_sinal = Column(String(1), default=INVERSAO_NAO, nullable=False)
    dat_ultima_execucao = Column(Date)  # carimbada pela F4.3
    ind_status = Column(String(1), default='A', nullable=False)
    dat_inclusao = Column(Date, default=date.today, nullable=False)
    cod_pessoa_inclusao = Column(Integer)
    dat_alteracao = Column(Date)  # insumo da detecção de sujo (F4.3)
    cod_pessoa_alteracao = Column(Integer)

    mapeamento = relationship('Mapeamento', back_populates='itens')
    qualificador = relationship('Qualificador')
