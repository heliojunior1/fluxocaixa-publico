"""versao de credencial em flc_usuario (controle-acesso R13)

Permite revogar TODAS as sessões de um usuário ao trocar a senha: a sessão
carrega a versão vista no login e é recusada quando diverge da atual.

Alternativa descartada: tabela de sessões — revogação granular que ninguém
pediu, ao custo de escrita por requisição e estado compartilhado novo (com
`--workers 1` + SQLite, gargalo).

Revision ID: 0030
Revises: 0029
"""
import sqlalchemy as sa
from alembic import op

revision = '0030'
down_revision = '0029'
branch_labels = None
depends_on = None


def upgrade():
    # server_default espelhado no model (o teste anti-deriva exige) e necessário
    # para as linhas existentes: usuário já cadastrado nasce na versão 1.
    with op.batch_alter_table('flc_usuario') as batch:
        batch.add_column(sa.Column(
            'num_versao_credencial', sa.Integer(),
            nullable=False, server_default='1',
        ))


def downgrade():
    with op.batch_alter_table('flc_usuario') as batch:
        batch.drop_column('num_versao_credencial')
