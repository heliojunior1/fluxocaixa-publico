"""cria flc_etl_staging

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-14 13:01:14.705586

Staging genérica da automação de lançamentos (spec automacao-lancamentos R1):
linha crua de fonte com destino LANCAMENTO + controle de processamento. Tabela
nova, sem dados a migrar; downgrade remove (staging é área de trabalho).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0008'
down_revision: Union[str, None] = '0007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    
    op.create_table('flc_etl_staging',
    sa.Column('seq_etl_staging', sa.Integer(), nullable=False),
    sa.Column('seq_fonte_extracao', sa.Integer(), nullable=False),
    sa.Column('seq_execucao_extracao', sa.Integer(), nullable=False),
    sa.Column('num_ano_exercicio', sa.Integer(), nullable=True),
    sa.Column('dat_referencia', sa.Date(), nullable=True),
    sa.Column('val_referencia', sa.Numeric(precision=18, scale=2), nullable=True),
    sa.Column('json_atributos', sa.JSON(), nullable=True),
    sa.Column('ind_status_processamento', sa.String(length=1), nullable=False),
    sa.Column('dsc_erro', sa.String(length=500), nullable=True),
    sa.Column('dat_inclusao', sa.Date(), nullable=False),
    sa.Column('cod_pessoa_inclusao', sa.Integer(), nullable=True),
    sa.Column('dat_alteracao', sa.Date(), nullable=True),
    sa.Column('cod_pessoa_alteracao', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['seq_execucao_extracao'], ['flc_execucao_extracao.seq_execucao_extracao'], name=op.f('fk_flc_etl_staging_seq_execucao_extracao_flc_execucao_extracao')),
    sa.ForeignKeyConstraint(['seq_fonte_extracao'], ['flc_fonte_extracao.seq_fonte_extracao'], name=op.f('fk_flc_etl_staging_seq_fonte_extracao_flc_fonte_extracao')),
    sa.PrimaryKeyConstraint('seq_etl_staging', name=op.f('pk_flc_etl_staging'))
    )
    with op.batch_alter_table('flc_etl_staging', schema=None) as batch_op:
        batch_op.create_index('ix_flc_etl_staging_exec_status', ['seq_execucao_extracao', 'ind_status_processamento'], unique=False)
        batch_op.create_index('ix_flc_etl_staging_fonte_data', ['seq_fonte_extracao', 'dat_referencia'], unique=False)

    


def downgrade() -> None:
    
    with op.batch_alter_table('flc_etl_staging', schema=None) as batch_op:
        batch_op.drop_index('ix_flc_etl_staging_fonte_data')
        batch_op.drop_index('ix_flc_etl_staging_exec_status')

    op.drop_table('flc_etl_staging')
    
