"""tabela de recomendações do backtest (previsao R13)

`flc_backtest_recomendacao` era consumida por SQL cru em `backtest_service`
SEM model nem migração: não existia em banco novo — "salvar recomendações"
quebrava com `no such table` em qualquer instalação limpa. `IF NOT EXISTS`
via inspeção: bancos legados podem tê-la de scripts históricos.

Revision ID: 0034
Revises: 0033
"""
import sqlalchemy as sa
from alembic import op

revision = '0034'
down_revision = '0033'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if sa.inspect(bind).has_table('flc_backtest_recomendacao'):
        return
    op.create_table(
        'flc_backtest_recomendacao',
        sa.Column('seq_backtest_recomendacao', sa.Integer(), primary_key=True),
        sa.Column('seq_qualificador', sa.Integer(),
                  sa.ForeignKey('flc_qualificador.seq_qualificador'),
                  nullable=False),
        sa.Column('cod_modelo', sa.String(30), nullable=False),
        sa.Column('val_mape', sa.Numeric(18, 6)),
        sa.Column('val_wmape', sa.Numeric(18, 6)),
        sa.Column('val_bias', sa.Numeric(18, 6)),
        sa.Column('anos_teste', sa.Text()),
        sa.Column('dat_execucao', sa.Date(), nullable=False),
    )


def downgrade():
    op.drop_table('flc_backtest_recomendacao')
