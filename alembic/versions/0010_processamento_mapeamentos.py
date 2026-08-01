"""processamento de mapeamentos

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-15 15:17:45.400978

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0010'
down_revision: Union[str, None] = '0009'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('flc_execucao_mapeamento',
    sa.Column('seq_execucao_mapeamento', sa.Integer(), nullable=False),
    sa.Column('seq_mapeamento', sa.Integer(), nullable=False),
    sa.Column('dat_inicio_execucao', sa.DateTime(), nullable=False),
    sa.Column('num_duracao_segundos', sa.Numeric(precision=10, scale=3), nullable=True),
    sa.Column('cod_disparo', sa.String(length=10), nullable=False),
    sa.Column('cod_status', sa.String(length=10), nullable=False),
    sa.Column('qtd_lancamentos_gerados', sa.Integer(), nullable=False),
    sa.Column('qtd_linhas_erro', sa.Integer(), nullable=False),
    sa.Column('qtd_lancamentos_removidos', sa.Integer(), nullable=False),
    sa.Column('txt_detalhe_erros', sa.String(length=4000), nullable=True),
    sa.Column('dat_inclusao', sa.Date(), nullable=False),
    sa.Column('cod_pessoa_inclusao', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['seq_mapeamento'], ['flc_mapeamento.seq_mapeamento'], name=op.f('fk_flc_execucao_mapeamento_seq_mapeamento_flc_mapeamento')),
    sa.PrimaryKeyConstraint('seq_execucao_mapeamento', name=op.f('pk_flc_execucao_mapeamento'))
    )
    with op.batch_alter_table('flc_execucao_mapeamento', schema=None) as batch_op:
        batch_op.create_index('ix_flc_execucao_mapeamento_map_data', ['seq_mapeamento', 'dat_inicio_execucao'], unique=False)

    with op.batch_alter_table('flc_etl_staging', schema=None) as batch_op:
        batch_op.create_index('ix_flc_etl_staging_fonte_status', ['seq_fonte_extracao', 'ind_status_processamento'], unique=False)

    with op.batch_alter_table('flc_lancamento', schema=None) as batch_op:
        batch_op.add_column(sa.Column('seq_etl_staging', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(batch_op.f('fk_flc_lancamento_seq_etl_staging_flc_etl_staging'), 'flc_etl_staging', ['seq_etl_staging'], ['seq_etl_staging'])



def downgrade() -> None:
    with op.batch_alter_table('flc_lancamento', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_flc_lancamento_seq_etl_staging_flc_etl_staging'), type_='foreignkey')
        batch_op.drop_column('seq_etl_staging')

    with op.batch_alter_table('flc_etl_staging', schema=None) as batch_op:
        batch_op.drop_index('ix_flc_etl_staging_fonte_status')

    with op.batch_alter_table('flc_execucao_mapeamento', schema=None) as batch_op:
        batch_op.drop_index('ix_flc_execucao_mapeamento_map_data')

    op.drop_table('flc_execucao_mapeamento')
