"""disponibilidade contabil por fonte (conciliacao F9.4)

Revision ID: 0029
Revises: 0028
Create Date: 2026-08-03 00:20:00.000000

Spec `fonte-recurso` R10–R12 (change conciliacao-disponibilidade-fonte).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0029'
down_revision: Union[str, None] = '0028'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'flc_disponibilidade_contabil',
        sa.Column('seq_disponibilidade', sa.Integer(), nullable=False),
        sa.Column('dat_referencia', sa.Date(), nullable=False),
        sa.Column('seq_fonte_recurso', sa.Integer(), nullable=False),
        sa.Column('val_disponibilidade', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('ind_status', sa.String(length=1), nullable=False),
        sa.Column('dat_inclusao', sa.Date(), nullable=False),
        sa.Column('cod_pessoa_inclusao', sa.Integer(), nullable=True),
        sa.Column('dat_alteracao', sa.Date(), nullable=True),
        sa.Column('cod_pessoa_alteracao', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['seq_fonte_recurso'], ['flc_fonte_recurso.seq_fonte_recurso'],
                                name=op.f('fk_flc_disponibilidade_contabil_seq_fonte_recurso_flc_fonte_recurso')),
        sa.PrimaryKeyConstraint('seq_disponibilidade', name=op.f('pk_flc_disponibilidade_contabil')),
    )


def downgrade() -> None:
    op.drop_table('flc_disponibilidade_contabil')
