"""execucao orcamentaria E/L/P com eventos (funil F8.2)

Revision ID: 0028
Revises: 0027
Create Date: 2026-08-02 23:50:00.000000

Spec `execucao-orcamentaria` R4–R7 (change execucao-orcamentaria-carga).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0028'
down_revision: Union[str, None] = '0027'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'flc_execucao_orcamentaria',
        sa.Column('seq_execucao', sa.Integer(), nullable=False),
        sa.Column('cod_estagio', sa.String(length=1), nullable=False),
        sa.Column('num_documento', sa.String(length=30), nullable=False),
        sa.Column('num_ano', sa.Integer(), nullable=False),
        sa.Column('cod_orgao', sa.Integer(), nullable=False),
        sa.Column('seq_qualificador', sa.Integer(), nullable=False),
        sa.Column('seq_fonte_recurso', sa.Integer(), nullable=True),
        sa.Column('seq_documento_pai', sa.Integer(), nullable=True),
        sa.Column('dat_documento', sa.Date(), nullable=False),
        sa.Column('ind_status', sa.String(length=1), nullable=False),
        sa.Column('dat_inclusao', sa.Date(), nullable=False),
        sa.Column('cod_pessoa_inclusao', sa.Integer(), nullable=True),
        sa.Column('dat_alteracao', sa.Date(), nullable=True),
        sa.Column('cod_pessoa_alteracao', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['cod_orgao'], ['flc_orgao.cod_orgao'],
                                name=op.f('fk_flc_execucao_orcamentaria_cod_orgao_flc_orgao')),
        sa.ForeignKeyConstraint(['seq_qualificador'], ['flc_qualificador.seq_qualificador'],
                                name=op.f('fk_flc_execucao_orcamentaria_seq_qualificador_flc_qualificador')),
        sa.ForeignKeyConstraint(['seq_fonte_recurso'], ['flc_fonte_recurso.seq_fonte_recurso'],
                                name=op.f('fk_flc_execucao_orcamentaria_seq_fonte_recurso_flc_fonte_recurso')),
        sa.ForeignKeyConstraint(['seq_documento_pai'], ['flc_execucao_orcamentaria.seq_execucao'],
                                name=op.f('fk_flc_execucao_orcamentaria_seq_documento_pai_flc_execucao_orcamentaria')),
        sa.PrimaryKeyConstraint('seq_execucao', name=op.f('pk_flc_execucao_orcamentaria')),
    )
    op.create_table(
        'flc_execucao_evento',
        sa.Column('seq_evento', sa.Integer(), nullable=False),
        sa.Column('seq_execucao', sa.Integer(), nullable=False),
        sa.Column('cod_tipo_evento', sa.String(length=1), nullable=False),
        sa.Column('val_evento', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('dat_evento', sa.Date(), nullable=False),
        sa.Column('dsc_referencia', sa.String(length=120), nullable=True),
        sa.Column('ind_status', sa.String(length=1), nullable=False),
        sa.Column('dat_inclusao', sa.Date(), nullable=False),
        sa.Column('cod_pessoa_inclusao', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['seq_execucao'], ['flc_execucao_orcamentaria.seq_execucao'],
                                name=op.f('fk_flc_execucao_evento_seq_execucao_flc_execucao_orcamentaria')),
        sa.PrimaryKeyConstraint('seq_evento', name=op.f('pk_flc_execucao_evento')),
    )


def downgrade() -> None:
    op.drop_table('flc_execucao_evento')
    op.drop_table('flc_execucao_orcamentaria')
