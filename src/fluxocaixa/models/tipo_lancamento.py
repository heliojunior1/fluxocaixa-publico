from sqlalchemy import Column, String

from .base import Base


class TipoLancamento(Base):
    __tablename__ = 'flc_tipo_lancamento'
    # PK textual 'C' (crédito/receita) / 'D' (débito/despesa) — F6.1b.
    # A descrição segue "Entrada"/"Saída": convergiu o código, não o
    # vocabulário da tesouraria (12 pontos resolvem por descrição).
    cod_tipo_lancamento = Column(String(1), primary_key=True)
    dsc_tipo_lancamento = Column(String(50), nullable=False)
