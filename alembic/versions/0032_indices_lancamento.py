"""índices secundários da tabela de fatos (infraestrutura-banco R12)

`flc_lancamento` foi criada na baseline só com PK e FKs — e SQLite/PostgreSQL
NÃO indexam FK automaticamente. Todo relatório filtrava por data/qualificador/
conta/status em full scan, e o filtro de idempotência do processamento
(`NOT EXISTS` sobre seq_etl_staging) idem. Os índices casam com os padrões de
acesso do lancamento_repository; os filtros de período viraram faixas de datas
(sargáveis) no mesmo change — índice sem filtro sargável não é usado.

Revision ID: 0032
Revises: 0031
"""
from alembic import op

revision = '0032'
down_revision = '0031'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index('ix_flc_lancamento_status_data', 'flc_lancamento',
                    ['ind_status', 'dat_lancamento'])
    op.create_index('ix_flc_lancamento_qualificador_data', 'flc_lancamento',
                    ['seq_qualificador', 'dat_lancamento'])
    op.create_index('ix_flc_lancamento_conta_data', 'flc_lancamento',
                    ['seq_conta', 'dat_lancamento'])
    # sustenta o resync cirúrgico e a idempotência da F4.3/Q01
    op.create_index('ix_flc_lancamento_etl_staging', 'flc_lancamento',
                    ['seq_etl_staging'])


def downgrade():
    op.drop_index('ix_flc_lancamento_etl_staging', table_name='flc_lancamento')
    op.drop_index('ix_flc_lancamento_conta_data', table_name='flc_lancamento')
    op.drop_index('ix_flc_lancamento_qualificador_data',
                  table_name='flc_lancamento')
    op.drop_index('ix_flc_lancamento_status_data', table_name='flc_lancamento')
