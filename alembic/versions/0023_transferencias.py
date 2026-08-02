"""registro de transferencias internas

Revision ID: 0023
Revises: 0022
Create Date: 2026-08-02 20:00:00.000000

Spec `desembolso` R13 (change transferencias-desembolso). Registro de
CONTROLE para a conciliação — sem efeito em lançamentos/saldos e sem fonte.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0023'
down_revision: Union[str, None] = '0022'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'flc_transferencia',
        sa.Column('seq_transferencia', sa.Integer(), nullable=False),
        sa.Column('dat_transferencia', sa.Date(), nullable=False),
        sa.Column('seq_conta_origem', sa.Integer(), nullable=False),
        sa.Column('seq_conta_destino', sa.Integer(), nullable=False),
        sa.Column('val_transferencia', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('dsc_transferencia', sa.String(length=255), nullable=True),
        sa.Column('ind_status', sa.String(length=1), nullable=False),
        sa.Column('dat_inclusao', sa.Date(), nullable=False),
        sa.Column('cod_pessoa_inclusao', sa.Integer(), nullable=True),
        sa.Column('dat_alteracao', sa.Date(), nullable=True),
        sa.Column('cod_pessoa_alteracao', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['seq_conta_origem'], ['flc_conta_bancaria.seq_conta'],
                                name=op.f('fk_flc_transferencia_seq_conta_origem_flc_conta_bancaria')),
        sa.ForeignKeyConstraint(['seq_conta_destino'], ['flc_conta_bancaria.seq_conta'],
                                name=op.f('fk_flc_transferencia_seq_conta_destino_flc_conta_bancaria')),
        sa.PrimaryKeyConstraint('seq_transferencia', name=op.f('pk_flc_transferencia')),
    )


def downgrade() -> None:
    op.drop_table('flc_transferencia')
