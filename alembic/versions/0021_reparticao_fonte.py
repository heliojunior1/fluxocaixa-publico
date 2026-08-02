"""reparticao de qualificador de receita por fonte

Revision ID: 0021
Revises: 0020
Create Date: 2026-08-02 16:00:00.000000

Spec `fonte-recurso` R8–R9 (change reparticao-fonte-projecao). Sem seed —
a repartição nasce vazia e tudo fica no grupo 'N' (não classificado, fora do
veredicto da simulação) até decisão humana, deliberadamente: repartir por
chute entraria no veredicto autorizativo com cara de dado.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0021'
down_revision: Union[str, None] = '0020'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'flc_qualificador_fonte',
        sa.Column('seq_qualificador_fonte', sa.Integer(), nullable=False),
        sa.Column('seq_qualificador', sa.Integer(), nullable=False),
        sa.Column('seq_fonte_recurso', sa.Integer(), nullable=False),
        sa.Column('pct_reparticao', sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column('num_ano_vigencia', sa.Integer(), nullable=False),
        sa.Column('ind_status', sa.String(length=1), nullable=False),
        sa.Column('dat_inclusao', sa.Date(), nullable=False),
        sa.Column('cod_pessoa_inclusao', sa.Integer(), nullable=True),
        sa.Column('dat_alteracao', sa.Date(), nullable=True),
        sa.Column('cod_pessoa_alteracao', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['seq_qualificador'], ['flc_qualificador.seq_qualificador'],
                                name=op.f('fk_flc_qualificador_fonte_seq_qualificador_flc_qualificador')),
        sa.ForeignKeyConstraint(['seq_fonte_recurso'], ['flc_fonte_recurso.seq_fonte_recurso'],
                                name=op.f('fk_flc_qualificador_fonte_seq_fonte_recurso_flc_fonte_recurso')),
        sa.PrimaryKeyConstraint('seq_qualificador_fonte', name=op.f('pk_flc_qualificador_fonte')),
    )


def downgrade() -> None:
    op.drop_table('flc_qualificador_fonte')
