"""contador de falhas e bloqueio de login (controle-acesso R14)

Revision ID: 0031
Revises: 0030
"""
import sqlalchemy as sa
from alembic import op

revision = '0031'
down_revision = '0030'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('flc_usuario') as batch:
        batch.add_column(sa.Column(
            'qtd_falhas_login', sa.Integer(), nullable=False, server_default='0'))
        # DateTime, e não Date: o bloqueio é de MINUTOS. A convenção do projeto
        # é auditoria em Date, mas aqui a granularidade de dia tornaria o
        # bloqueio inútil (ou eterno).
        batch.add_column(sa.Column(
            'dat_bloqueio_login', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('flc_usuario') as batch:
        batch.drop_column('dat_bloqueio_login')
        batch.drop_column('qtd_falhas_login')
