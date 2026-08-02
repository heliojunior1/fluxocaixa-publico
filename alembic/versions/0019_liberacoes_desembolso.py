"""liberacoes do desembolso, eventos e apropriacao; status em orgao

Revision ID: 0019
Revises: 0018
Create Date: 2026-08-02 12:00:00.000000

Spec `desembolso` R1–R5 (change liberacoes-desembolso). Cria a liberação
financeira com livro de eventos imutável e a tabela de apropriação
pagamento↔liberação (linhas-evento A/E — a UI chega na F7.1b, o modelo nasce
aqui para não forçar migração). `flc_orgao` ganha status + auditoria
(backfill 'A' — os órgãos existentes vêm do seed e estão em uso).

⚠️ Não existe coluna `val_utilizado`: o saldo liberado pendente é SEMPRE
derivado (Σ confirmadas − Σ apropriações + Σ estornos).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0019'
down_revision: Union[str, None] = '0018'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Padrão da 0016: auditoria nullable, sem backfill (linhas do seed antigo
    # ficam nulas). ind_status NOT NULL exige server_default no ALTER — o
    # model espelha o server_default para o anti-deriva não acusar.
    with op.batch_alter_table('flc_orgao') as batch:
        batch.add_column(sa.Column('ind_status', sa.String(length=1),
                                   nullable=False, server_default='A'))
        batch.add_column(sa.Column('dat_inclusao', sa.Date(), nullable=True))
        batch.add_column(sa.Column('cod_pessoa_inclusao', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('dat_alteracao', sa.Date(), nullable=True))
        batch.add_column(sa.Column('cod_pessoa_alteracao', sa.Integer(), nullable=True))

    op.create_table(
        'flc_liberacao',
        sa.Column('seq_liberacao', sa.Integer(), nullable=False),
        sa.Column('dat_liberacao', sa.Date(), nullable=False),
        sa.Column('dat_prevista_desembolso', sa.Date(), nullable=False),
        sa.Column('cod_orgao', sa.Integer(), nullable=False),
        sa.Column('seq_qualificador', sa.Integer(), nullable=False),
        sa.Column('seq_fonte_recurso', sa.Integer(), nullable=False),
        sa.Column('val_liberacao', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('dsc_liberacao', sa.String(length=255), nullable=True),
        sa.Column('dsc_justificativa', sa.String(length=500), nullable=True),
        # 'D' discricionária | 'O' constitucional-legal | 'J' judicial |
        # 'F' folha | 'V' dívida — não-D = curva-base da simulação (F7.2)
        sa.Column('cod_natureza_obrigacao', sa.String(length=1), nullable=False),
        sa.Column('dsc_base_legal', sa.String(length=200), nullable=True),
        # 'R' rascunho | 'C' confirmada | 'X' cancelada
        sa.Column('cod_situacao', sa.String(length=1), nullable=False),
        sa.Column('ind_status', sa.String(length=1), nullable=False),
        sa.Column('dat_inclusao', sa.Date(), nullable=False),
        sa.Column('cod_pessoa_inclusao', sa.Integer(), nullable=True),
        sa.Column('dat_alteracao', sa.Date(), nullable=True),
        sa.Column('cod_pessoa_alteracao', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['cod_orgao'], ['flc_orgao.cod_orgao'],
                                name=op.f('fk_flc_liberacao_cod_orgao_flc_orgao')),
        sa.ForeignKeyConstraint(['seq_qualificador'], ['flc_qualificador.seq_qualificador'],
                                name=op.f('fk_flc_liberacao_seq_qualificador_flc_qualificador')),
        sa.ForeignKeyConstraint(['seq_fonte_recurso'], ['flc_fonte_recurso.seq_fonte_recurso'],
                                name=op.f('fk_flc_liberacao_seq_fonte_recurso_flc_fonte_recurso')),
        sa.PrimaryKeyConstraint('seq_liberacao', name=op.f('pk_flc_liberacao')),
    )

    op.create_table(
        'flc_liberacao_evento',
        sa.Column('seq_liberacao_evento', sa.Integer(), nullable=False),
        sa.Column('seq_liberacao', sa.Integer(), nullable=False),
        # CRIACAO | CONFIRMACAO | CANCELAMENTO — linhas imutáveis
        sa.Column('cod_tipo_evento', sa.String(length=15), nullable=False),
        sa.Column('dsc_justificativa', sa.String(length=500), nullable=True),
        sa.Column('dsc_referencia_snapshot', sa.String(length=120), nullable=True),
        sa.Column('dat_evento', sa.Date(), nullable=False),
        sa.Column('cod_pessoa_evento', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['seq_liberacao'], ['flc_liberacao.seq_liberacao'],
                                name=op.f('fk_flc_liberacao_evento_seq_liberacao_flc_liberacao')),
        sa.PrimaryKeyConstraint('seq_liberacao_evento', name=op.f('pk_flc_liberacao_evento')),
    )

    op.create_table(
        'flc_pagamento_liberacao',
        sa.Column('seq_pagamento_liberacao', sa.Integer(), nullable=False),
        sa.Column('seq_pagamento', sa.Integer(), nullable=False),
        sa.Column('seq_liberacao', sa.Integer(), nullable=False),
        # 'A' apropriação | 'E' estorno — consumo = Σ(A) − Σ(E)
        sa.Column('cod_tipo_evento', sa.String(length=1), nullable=False),
        sa.Column('val_apropriado', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('dat_evento', sa.Date(), nullable=False),
        sa.Column('cod_pessoa_evento', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['seq_pagamento'], ['flc_pagamento.seq_pagamento'],
                                name=op.f('fk_flc_pagamento_liberacao_seq_pagamento_flc_pagamento')),
        sa.ForeignKeyConstraint(['seq_liberacao'], ['flc_liberacao.seq_liberacao'],
                                name=op.f('fk_flc_pagamento_liberacao_seq_liberacao_flc_liberacao')),
        sa.PrimaryKeyConstraint('seq_pagamento_liberacao', name=op.f('pk_flc_pagamento_liberacao')),
    )


def downgrade() -> None:
    # ⚠️ Perda declarada: liberações, eventos e apropriações somem.
    op.drop_table('flc_pagamento_liberacao')
    op.drop_table('flc_liberacao_evento')
    op.drop_table('flc_liberacao')

    with op.batch_alter_table('flc_orgao') as batch:
        batch.drop_column('cod_pessoa_alteracao')
        batch.drop_column('dat_alteracao')
        batch.drop_column('cod_pessoa_inclusao')
        batch.drop_column('dat_inclusao')
        batch.drop_column('ind_status')
