"""parametros do desembolso e snapshot da simulacao

Revision ID: 0022
Revises: 0021
Create Date: 2026-08-02 18:00:00.000000

Spec `desembolso` R11–R12 (change simulacao-disponibilidade). O colchão nasce
com default global 0.00 (seed) — 0 significa "só bloqueia curva negativa";
cada instalação define o seu. O snapshot é imutável (rastro da decisão).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0022'
down_revision: Union[str, None] = '0021'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'flc_parametro_desembolso',
        sa.Column('seq_parametro_desembolso', sa.Integer(), nullable=False),
        sa.Column('cod_parametro', sa.String(length=30), nullable=False),
        sa.Column('cod_grupo', sa.String(length=1), nullable=True),
        sa.Column('val_parametro', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('ind_status', sa.String(length=1), nullable=False),
        sa.Column('dat_inclusao', sa.Date(), nullable=False),
        sa.Column('cod_pessoa_inclusao', sa.Integer(), nullable=True),
        sa.Column('dat_alteracao', sa.Date(), nullable=True),
        sa.Column('cod_pessoa_alteracao', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('seq_parametro_desembolso',
                                name=op.f('pk_flc_parametro_desembolso')),
    )

    op.create_table(
        'flc_simulacao_desembolso',
        sa.Column('seq_simulacao_desembolso', sa.Integer(), nullable=False),
        sa.Column('dat_simulacao', sa.Date(), nullable=False),
        sa.Column('cod_grupo', sa.String(length=1), nullable=False),
        sa.Column('cod_veredicto', sa.String(length=10), nullable=False),
        sa.Column('json_snapshot', sa.JSON(), nullable=False),
        sa.Column('cod_pessoa_inclusao', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('seq_simulacao_desembolso',
                                name=op.f('pk_flc_simulacao_desembolso')),
    )


def downgrade() -> None:
    op.drop_table('flc_simulacao_desembolso')
    op.drop_table('flc_parametro_desembolso')
