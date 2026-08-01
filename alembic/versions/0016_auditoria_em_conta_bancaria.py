"""auditoria completa em flc_conta_bancaria

Revision ID: 0016
Revises: 0015
Create Date: 2026-08-01

Spec `cadastros-nucleo` R20–R22 (change crud-conta-bancaria). A tabela é
anterior à convenção de auditoria e só tinha `dat_cadastro`; o CRUD precisa
registrar quem incluiu/alterou. Colunas nullable e sem backfill: linhas
pré-existentes ficam nulas — `dat_cadastro` já registra a origem delas.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0016'
down_revision: Union[str, None] = '0015'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('flc_conta_bancaria', sa.Column('dat_inclusao', sa.Date(), nullable=True))
    op.add_column('flc_conta_bancaria', sa.Column('cod_pessoa_inclusao', sa.Integer(), nullable=True))
    op.add_column('flc_conta_bancaria', sa.Column('dat_alteracao', sa.Date(), nullable=True))
    op.add_column('flc_conta_bancaria', sa.Column('cod_pessoa_alteracao', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('flc_conta_bancaria', 'cod_pessoa_alteracao')
    op.drop_column('flc_conta_bancaria', 'dat_alteracao')
    op.drop_column('flc_conta_bancaria', 'cod_pessoa_inclusao')
    op.drop_column('flc_conta_bancaria', 'dat_inclusao')
