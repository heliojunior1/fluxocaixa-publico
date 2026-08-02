"""dotacao + creditos adicionais (funil orcamentario F8.1)

Revision ID: 0027
Revises: 0026
Create Date: 2026-08-02 23:30:00.000000

Spec `execucao-orcamentaria` R1–R2 (change dotacao-creditos).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0027'
down_revision: Union[str, None] = '0026'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'flc_dotacao',
        sa.Column('seq_dotacao', sa.Integer(), nullable=False),
        sa.Column('num_ano', sa.Integer(), nullable=False),
        sa.Column('seq_qualificador', sa.Integer(), nullable=False),
        sa.Column('val_dotacao_inicial', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('ind_status', sa.String(length=1), nullable=False),
        sa.Column('dat_inclusao', sa.Date(), nullable=False),
        sa.Column('cod_pessoa_inclusao', sa.Integer(), nullable=True),
        sa.Column('dat_alteracao', sa.Date(), nullable=True),
        sa.Column('cod_pessoa_alteracao', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['seq_qualificador'], ['flc_qualificador.seq_qualificador'],
                                name=op.f('fk_flc_dotacao_seq_qualificador_flc_qualificador')),
        sa.PrimaryKeyConstraint('seq_dotacao', name=op.f('pk_flc_dotacao')),
    )
    op.create_table(
        'flc_credito_adicional',
        sa.Column('seq_credito', sa.Integer(), nullable=False),
        sa.Column('seq_dotacao', sa.Integer(), nullable=False),
        sa.Column('cod_tipo_credito', sa.String(length=1), nullable=False),
        sa.Column('val_credito', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('dat_credito', sa.Date(), nullable=False),
        sa.Column('dsc_referencia_ato', sa.String(length=120), nullable=False),
        sa.Column('ind_status', sa.String(length=1), nullable=False),
        sa.Column('dat_inclusao', sa.Date(), nullable=False),
        sa.Column('cod_pessoa_inclusao', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['seq_dotacao'], ['flc_dotacao.seq_dotacao'],
                                name=op.f('fk_flc_credito_adicional_seq_dotacao_flc_dotacao')),
        sa.PrimaryKeyConstraint('seq_credito', name=op.f('pk_flc_credito_adicional')),
    )


def downgrade() -> None:
    op.drop_table('flc_credito_adicional')
    op.drop_table('flc_dotacao')
