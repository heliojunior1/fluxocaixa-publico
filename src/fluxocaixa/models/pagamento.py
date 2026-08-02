"""Pagamento — o desembolso financeiro (spec desembolso R6–R8).

Alinhado às convenções na F7.1b (antes: 18 linhas sem status/auditoria/
origem). ⚠️ Distinções que não podem se perder:

- **Pagamento orçamentário ≠ desembolso financeiro**: este registro é o
  financeiro (manual ou, com o funil F8.x, alimentado pela integração —
  `cod_origem` 'A'); os dois nunca se fundem, são conciliados (F8.3).
- **Qualificador é exigido pelo SERVIÇO em escrita nova**; a coluna permanece
  nullable porque o legado pode ter nulos e não se fabrica classificação
  retroativa (D1 do change).
- **A fonte é HERDADA da apropriação** (monofonte, v2.1): primeira
  apropriação estampa; estornar tudo limpa. Nunca editada diretamente.
"""
from datetime import date

from sqlalchemy import Column, Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship

from .base import Base

#: Origem do pagamento.
ORIGEM_MANUAL = 'M'
ORIGEM_AUTOMATICA = 'A'  #: chega com o funil orçamentário (F8.x)


class Pagamento(Base):
    __tablename__ = 'flc_pagamento'

    seq_pagamento = Column(Integer, primary_key=True)
    dat_pagamento = Column(Date, nullable=False)
    cod_orgao = Column(Integer, ForeignKey('flc_orgao.cod_orgao'), nullable=False)
    seq_qualificador = Column(
        Integer, ForeignKey('flc_qualificador.seq_qualificador'), nullable=True)
    #: herdada da liberação apropriada (R8) — nunca editada diretamente
    seq_fonte_recurso = Column(
        Integer, ForeignKey('flc_fonte_recurso.seq_fonte_recurso'), nullable=True)
    val_pagamento = Column(Numeric(18, 2), nullable=False)
    dsc_pagamento = Column(String(255))
    # server_default espelha a migração 0020 (ALTER em tabela populada)
    cod_origem = Column(String(1), nullable=False, default=ORIGEM_MANUAL,
                        server_default='M')
    ind_status = Column(String(1), nullable=False, default='A', server_default='A')
    dat_inclusao = Column(Date, default=date.today, nullable=False)
    cod_pessoa_inclusao = Column(Integer)
    dat_alteracao = Column(Date)
    cod_pessoa_alteracao = Column(Integer)

    orgao = relationship('Orgao')
    qualificador = relationship('Qualificador')
    fonte_recurso = relationship('FonteRecurso')
