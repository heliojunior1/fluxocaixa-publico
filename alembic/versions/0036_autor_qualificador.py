"""autor na criação de qualificador (cadastros-nucleo R29, F10.3)

`flc_qualificador` era anterior à convenção de auditoria e não registrava
QUEM criou a linha. A abertura de exercício é justamente o ato que precisa
dessa trilha ("quem abriu 2027?"), então a coluna entra agora — nullable:
linha legada não ganha autor fabricado (mesmo racional da migração 0033).

Revision ID: 0036
Revises: 0035
"""
import sqlalchemy as sa
from alembic import op

revision = '0036'
down_revision = '0035'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('flc_qualificador') as batch:
        batch.add_column(sa.Column('cod_pessoa_inclusao', sa.Integer(),
                                   nullable=True))


def downgrade():
    with op.batch_alter_table('flc_qualificador') as batch:
        batch.drop_column('cod_pessoa_inclusao')
