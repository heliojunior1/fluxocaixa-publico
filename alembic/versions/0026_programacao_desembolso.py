"""programacao de desembolso (cotas do decreto)

Revision ID: 0026
Revises: 0025
Create Date: 2026-08-02 23:00:00.000000

Spec `desembolso` R21–R22 (change programacao-desembolso).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0026'
down_revision: Union[str, None] = '0025'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'flc_programacao_desembolso',
        sa.Column('seq_programacao', sa.Integer(), nullable=False),
        sa.Column('num_ano', sa.Integer(), nullable=False),
        sa.Column('num_mes', sa.Integer(), nullable=False),
        sa.Column('cod_orgao', sa.Integer(), nullable=False),
        sa.Column('seq_qualificador', sa.Integer(), nullable=True),
        sa.Column('seq_fonte_recurso', sa.Integer(), nullable=True),
        sa.Column('val_cota', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('dsc_referencia_ato', sa.String(length=120), nullable=False),
        sa.Column('ind_status', sa.String(length=1), nullable=False),
        sa.Column('dat_inclusao', sa.Date(), nullable=False),
        sa.Column('cod_pessoa_inclusao', sa.Integer(), nullable=True),
        sa.Column('dat_alteracao', sa.Date(), nullable=True),
        sa.Column('cod_pessoa_alteracao', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['cod_orgao'], ['flc_orgao.cod_orgao'],
                                name=op.f('fk_flc_programacao_desembolso_cod_orgao_flc_orgao')),
        sa.ForeignKeyConstraint(['seq_qualificador'], ['flc_qualificador.seq_qualificador'],
                                name=op.f('fk_flc_programacao_desembolso_seq_qualificador_flc_qualificador')),
        sa.ForeignKeyConstraint(['seq_fonte_recurso'], ['flc_fonte_recurso.seq_fonte_recurso'],
                                name=op.f('fk_flc_programacao_desembolso_seq_fonte_recurso_flc_fonte_recurso')),
        sa.PrimaryKeyConstraint('seq_programacao', name=op.f('pk_flc_programacao_desembolso')),
    )


def downgrade() -> None:
    op.drop_table('flc_programacao_desembolso')
