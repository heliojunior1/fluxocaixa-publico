"""reservas financeiras e bloqueios judiciais (cabecalho + eventos)

Revision ID: 0025
Revises: 0024
Create Date: 2026-08-02 22:00:00.000000

Spec `desembolso` R19–R20 (change reservas-financeiras). O valor corrente é
SEMPRE derivado dos eventos — não existe coluna de valor no cabeçalho.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0025'
down_revision: Union[str, None] = '0024'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'flc_reserva_financeira',
        sa.Column('seq_reserva', sa.Integer(), nullable=False),
        sa.Column('cod_tipo_reserva', sa.String(length=1), nullable=False),
        sa.Column('seq_fonte_recurso', sa.Integer(), nullable=False),
        sa.Column('seq_conta', sa.Integer(), nullable=True),
        sa.Column('dsc_motivo', sa.String(length=255), nullable=False),
        sa.Column('dsc_referencia_processo', sa.String(length=120), nullable=True),
        sa.Column('dat_inicio_vigencia', sa.Date(), nullable=False),
        sa.Column('dat_fim_vigencia', sa.Date(), nullable=True),
        sa.Column('ind_status', sa.String(length=1), nullable=False),
        sa.Column('dat_inclusao', sa.Date(), nullable=False),
        sa.Column('cod_pessoa_inclusao', sa.Integer(), nullable=True),
        sa.Column('dat_alteracao', sa.Date(), nullable=True),
        sa.Column('cod_pessoa_alteracao', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['seq_fonte_recurso'], ['flc_fonte_recurso.seq_fonte_recurso'],
                                name=op.f('fk_flc_reserva_financeira_seq_fonte_recurso_flc_fonte_recurso')),
        sa.ForeignKeyConstraint(['seq_conta'], ['flc_conta_bancaria.seq_conta'],
                                name=op.f('fk_flc_reserva_financeira_seq_conta_flc_conta_bancaria')),
        sa.PrimaryKeyConstraint('seq_reserva', name=op.f('pk_flc_reserva_financeira')),
    )

    op.create_table(
        'flc_reserva_evento',
        sa.Column('seq_reserva_evento', sa.Integer(), nullable=False),
        sa.Column('seq_reserva', sa.Integer(), nullable=False),
        # CONSTITUICAO | REFORCO | REDUCAO | LIBERACAO — linhas imutáveis
        sa.Column('cod_tipo_evento', sa.String(length=15), nullable=False),
        sa.Column('val_evento', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('dsc_referencia_documental', sa.String(length=120), nullable=True),
        sa.Column('dat_evento', sa.Date(), nullable=False),
        sa.Column('cod_pessoa_evento', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['seq_reserva'], ['flc_reserva_financeira.seq_reserva'],
                                name=op.f('fk_flc_reserva_evento_seq_reserva_flc_reserva_financeira')),
        sa.PrimaryKeyConstraint('seq_reserva_evento', name=op.f('pk_flc_reserva_evento')),
    )


def downgrade() -> None:
    op.drop_table('flc_reserva_evento')
    op.drop_table('flc_reserva_financeira')
