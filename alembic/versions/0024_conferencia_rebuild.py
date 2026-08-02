"""rebuild da conferencia: so o apurado externo sobrevive

Revision ID: 0024
Revises: 0023
Create Date: 2026-08-02 21:00:00.000000

Spec `desembolso` R14–R16 (change conferencia-desembolso). As colunas
deriváveis somem — eram persistência de valores copiados de imagem de
demonstração; converter fabricaria apurados com cara de conferência feita.
⚠️ Perda declarada: as linhas antigas são descartadas.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0024'
down_revision: Union[str, None] = '0023'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # legado descartado (D4 do change) — a tabela renasce só com o apurado
    op.drop_table('flc_conferencia')
    op.create_table(
        'flc_conferencia',
        sa.Column('dat_conferencia', sa.Date(), nullable=False),
        sa.Column('val_apurado_liberacoes', sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column('val_apurado_pagamentos', sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column('ind_status', sa.String(length=1), nullable=False, server_default='A'),
        sa.Column('dat_inclusao', sa.Date(), nullable=True),
        sa.Column('cod_pessoa_inclusao', sa.Integer(), nullable=True),
        sa.Column('dat_alteracao', sa.Date(), nullable=True),
        sa.Column('cod_pessoa_alteracao', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('dat_conferencia', name=op.f('pk_flc_conferencia')),
    )


def downgrade() -> None:
    # volta o shape antigo, ZERADO — os dados antigos não são recuperáveis
    op.drop_table('flc_conferencia')
    op.create_table(
        'flc_conferencia',
        sa.Column('dat_conferencia', sa.Date(), nullable=False),
        sa.Column('val_saldo_anterior', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('val_liberacoes', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('val_conf_liberacoes', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('val_soma_anter_liberacoes', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('val_pagamentos', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('val_conf_pagamentos', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('val_saldo_final', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.PrimaryKeyConstraint('dat_conferencia', name=op.f('pk_flc_conferencia')),
    )
