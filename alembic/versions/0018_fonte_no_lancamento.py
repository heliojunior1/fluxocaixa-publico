"""fonte de recursos no lancamento

Revision ID: 0018
Revises: 0017
Create Date: 2026-08-02 10:00:00.000000

Spec `fonte-recurso` R7 e `automacao-lancamentos` R17 (change
fonte-lancamento). FK **nullable** — o legado permanece nulo, deliberado:
não se inventa fonte retroativamente; o filtro "sem fonte" torna o não
classificado visível em vez de escondê-lo atrás de um chute.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0018'
down_revision: Union[str, None] = '0017'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('flc_lancamento') as batch:
        batch.add_column(sa.Column('seq_fonte_recurso', sa.Integer(), nullable=True))
        batch.create_foreign_key(
            'fk_flc_lancamento_seq_fonte_recurso_flc_fonte_recurso',
            'flc_fonte_recurso', ['seq_fonte_recurso'], ['seq_fonte_recurso'],
        )


def downgrade() -> None:
    with op.batch_alter_table('flc_lancamento') as batch:
        batch.drop_constraint(
            'fk_flc_lancamento_seq_fonte_recurso_flc_fonte_recurso',
            type_='foreignkey')
        batch.drop_column('seq_fonte_recurso')
