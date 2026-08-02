"""alinhamento de flc_pagamento as convencoes (status, origem, fonte)

Revision ID: 0020
Revises: 0019
Create Date: 2026-08-02 14:00:00.000000

Spec `desembolso` R6 (change vinculo-pagamento-liberacao). A tabela era
anterior às convenções: sem soft-delete, auditoria incompleta, sem origem e
sem fonte. ⚠️ `seq_qualificador` permanece NULLABLE — o serviço exige em
escrita nova; backfill fabricaria classificação com cara de decisão humana.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0020'
down_revision: Union[str, None] = '0019'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('flc_pagamento') as batch:
        # 'M' manual | 'A' automático (funil F8.x) — NOT NULL exige default no ALTER
        batch.add_column(sa.Column('cod_origem', sa.String(length=1),
                                   nullable=False, server_default='M'))
        batch.add_column(sa.Column('ind_status', sa.String(length=1),
                                   nullable=False, server_default='A'))
        batch.add_column(sa.Column('cod_pessoa_inclusao', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('dat_alteracao', sa.Date(), nullable=True))
        batch.add_column(sa.Column('cod_pessoa_alteracao', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('seq_fonte_recurso', sa.Integer(), nullable=True))
        batch.create_foreign_key(
            'fk_flc_pagamento_seq_fonte_recurso_flc_fonte_recurso',
            'flc_fonte_recurso', ['seq_fonte_recurso'], ['seq_fonte_recurso'],
        )


def downgrade() -> None:
    with op.batch_alter_table('flc_pagamento') as batch:
        batch.drop_constraint(
            'fk_flc_pagamento_seq_fonte_recurso_flc_fonte_recurso', type_='foreignkey')
        batch.drop_column('seq_fonte_recurso')
        batch.drop_column('cod_pessoa_alteracao')
        batch.drop_column('dat_alteracao')
        batch.drop_column('cod_pessoa_inclusao')
        batch.drop_column('ind_status')
        batch.drop_column('cod_origem')
