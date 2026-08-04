from datetime import date

from sqlalchemy import (
    Column,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    case,
)
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship

from .base import Base

# Códigos do tipo de lançamento (F6.1b). Ficam aqui, e não em
# `dominio_lancamento`, para o model não depender da camada de serviço.
TIPO_CREDITO = 'C'   # receita — valor positivo na leitura
TIPO_DEBITO = 'D'    # despesa — valor negado na leitura

class Lancamento(Base):
    __tablename__ = 'flc_lancamento'
    # Índices da tabela de fatos (infraestrutura-banco R12, migração 0032):
    # casam com os padrões de acesso do lancamento_repository. Os filtros de
    # período são FAIXAS de data (sargáveis) — extract() no WHERE impediria o
    # planejador de usá-los. O de seq_etl_staging sustenta o resync/idempotência
    # da F4.3. Declarados aqui E na migração — anti-deriva.
    __table_args__ = (
        Index('ix_flc_lancamento_status_data', 'ind_status', 'dat_lancamento'),
        Index('ix_flc_lancamento_qualificador_data',
              'seq_qualificador', 'dat_lancamento'),
        Index('ix_flc_lancamento_conta_data', 'seq_conta', 'dat_lancamento'),
        Index('ix_flc_lancamento_etl_staging', 'seq_etl_staging'),
    )
    seq_lancamento = Column(Integer, primary_key=True)
    dat_lancamento = Column(Date, nullable=False)
    seq_qualificador = Column(Integer, ForeignKey('flc_qualificador.seq_qualificador'), nullable=False)
    val_lancamento = Column(Numeric(18,2), nullable=False)
    # Linha da staging que originou este lançamento (F4.3). NULL para lançamento
    # manual/importado, que não vem da staging. É a âncora que dá idempotência
    # ("esta linha já gerou?"), rastro (até o json_atributos cru da origem) e o
    # resync cirúrgico (dos lançamentos do qualificador saem exatamente as
    # linhas a resetar).
    seq_etl_staging = Column(
        Integer, ForeignKey('flc_etl_staging.seq_etl_staging'), nullable=True
    )
    cod_tipo_lancamento = Column(String(1), ForeignKey('flc_tipo_lancamento.cod_tipo_lancamento'), nullable=False)
    cod_origem_lancamento = Column(Integer, ForeignKey('flc_origem_lancamento.cod_origem_lancamento'), nullable=False)
    dat_inclusao = Column(Date, default=date.today, nullable=False)
    cod_pessoa_inclusao = Column(Integer, nullable=False)
    dat_alteracao = Column(Date)
    cod_pessoa_alteracao = Column(Integer)
    ind_status = Column(String(1), default='A', nullable=False)

    # Conta bancária vinculada (opcional)
    seq_conta = Column(Integer, ForeignKey('flc_conta_bancaria.seq_conta'), nullable=True)
    # Fonte de recursos (F9.2) — dimensão OPCIONAL: automático estampa do
    # json_atributos da staging; manual escolhe sem default; legado fica nulo
    # (não se inventa fonte retroativamente).
    seq_fonte_recurso = Column(
        Integer, ForeignKey('flc_fonte_recurso.seq_fonte_recurso'), nullable=True
    )

    tipo = relationship('TipoLancamento')
    origem = relationship('OrigemLancamento')
    qualificador = relationship('Qualificador')
    conta = relationship('ContaBancaria')
    fonte_recurso = relationship('FonteRecurso')

    # -----------------------------------------------------------------------
    # A COSTURA (F6.1a, spec cadastros-nucleo R6)
    # -----------------------------------------------------------------------
    @hybrid_property
    def valor_com_sinal(self):
        """Valor do lançamento com o sinal do fluxo de caixa.

        **Origem única do sinal no sistema.** Toda agregação, comparação de
        sinal e derivação de valor DEVE passar por aqui; `val_lancamento` cru
        só na gravação e na exibição de UMA linha. Um teste estrutural
        (`test_costura_valor_com_sinal.py`) derruba a suíte se um módulo de
        agregação ler a coluna direto.

        `val_lancamento` é sempre POSITIVO (F6.1b) e o sinal vem do tipo:
        'D' (débito/despesa) nega, 'C' (crédito/receita) preserva. Foi o único
        ponto que mudou de semântica no flip — os ~30 pontos de leitura
        seguiram corretos sem edição, e a rede de caracterização provou que
        nenhum número se moveu.

        É por isso que `get_sum_by_account_on_date_positive`/`_negative`
        testam `valor_com_sinal > 0`/`< 0` em vez do tipo: hoje isso é
        equivalente a `tipo == 'C'`/`'D'` por construção.
        """
        return (
            -self.val_lancamento
            if self.cod_tipo_lancamento == TIPO_DEBITO
            else self.val_lancamento
        )

    @valor_com_sinal.expression
    def valor_com_sinal(cls):
        return case(
            (cls.cod_tipo_lancamento == TIPO_DEBITO, -cls.val_lancamento),
            else_=cls.val_lancamento,
        )
