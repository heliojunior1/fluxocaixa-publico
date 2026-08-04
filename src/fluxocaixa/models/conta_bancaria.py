from datetime import date

from sqlalchemy import Column, Date, Integer, String, UniqueConstraint

from .base import Base


class ContaBancaria(Base):
    __tablename__ = "flc_conta_bancaria"
    __table_args__ = (
        # Unicidade garantida por constraint (não só validação): importações
        # concorrentes não duplicam conta (spec cadastros-nucleo R5)
        UniqueConstraint("cod_banco", "num_agencia", "num_conta"),
    )

    seq_conta = Column(Integer, primary_key=True)
    cod_banco = Column(String(10), nullable=False)
    num_agencia = Column(String(20), nullable=False)
    num_conta = Column(String(30), nullable=False)
    dsc_conta = Column(String(100))
    ind_status = Column(String(1), default="A", nullable=False)
    dat_cadastro = Column(Date, default=date.today)
    # Auditoria (migração 0016): nullable — a tabela é anterior à convenção e
    # as linhas antigas não têm autor registrado (dat_cadastro cobre a época)
    dat_inclusao = Column(Date, default=date.today)
    cod_pessoa_inclusao = Column(Integer)
    dat_alteracao = Column(Date)
    cod_pessoa_alteracao = Column(Integer)

    def display(self) -> str:
        desc = f" - {self.dsc_conta}" if self.dsc_conta else ""
        return f"{self.cod_banco} / {self.num_agencia} / {self.num_conta}{desc}"
