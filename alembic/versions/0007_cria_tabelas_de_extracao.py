"""cria tabelas de extracao

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-13 08:56:33.313326

Infraestrutura da extração embutida (spec extracao-configuravel R1/R3):
`flc_fonte_extracao` (cadastro parametrizável de fontes) e
`flc_execucao_extracao` (log imutável de execuções). Tabelas novas, sem
dados a migrar; o downgrade remove as duas (execuções são descartáveis
por definição — log operacional).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0007'
down_revision: Union[str, None] = '0006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('flc_fonte_extracao',
    sa.Column('seq_fonte_extracao', sa.Integer(), nullable=False),
    sa.Column('nom_fonte', sa.String(length=120), nullable=False),
    sa.Column('cod_tipo_conector', sa.String(length=30), nullable=False),
    sa.Column('cod_destino', sa.String(length=20), nullable=False),
    sa.Column('seq_sistema_origem', sa.Integer(), nullable=False),
    sa.Column('txt_cron', sa.String(length=60), nullable=True),
    sa.Column('json_config', sa.JSON(), nullable=False),
    sa.Column('json_layout', sa.JSON(), nullable=True),
    sa.Column('ind_status', sa.String(length=1), nullable=False),
    sa.Column('dat_inclusao', sa.Date(), nullable=False),
    sa.Column('cod_pessoa_inclusao', sa.Integer(), nullable=True),
    sa.Column('dat_alteracao', sa.Date(), nullable=True),
    sa.Column('cod_pessoa_alteracao', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['seq_sistema_origem'], ['flc_sistema_origem.seq_sistema_origem'], name=op.f('fk_flc_fonte_extracao_seq_sistema_origem_flc_sistema_origem')),
    sa.PrimaryKeyConstraint('seq_fonte_extracao', name=op.f('pk_flc_fonte_extracao'))
    )
    op.create_table('flc_execucao_extracao',
    sa.Column('seq_execucao_extracao', sa.Integer(), nullable=False),
    sa.Column('seq_fonte_extracao', sa.Integer(), nullable=False),
    sa.Column('dat_inicio_execucao', sa.DateTime(), nullable=False),
    sa.Column('num_duracao_segundos', sa.Numeric(precision=12, scale=3), nullable=True),
    sa.Column('cod_disparo', sa.String(length=10), nullable=False),
    sa.Column('cod_status', sa.String(length=10), nullable=False),
    sa.Column('dat_janela_inicio', sa.Date(), nullable=False),
    sa.Column('dat_janela_fim', sa.Date(), nullable=False),
    sa.Column('qtd_linhas_inseridas', sa.Integer(), nullable=False),
    sa.Column('qtd_linhas_erro', sa.Integer(), nullable=False),
    sa.Column('qtd_fundos_auto_cadastrados', sa.Integer(), nullable=False),
    sa.Column('txt_detalhe_erros', sa.Text(), nullable=True),
    sa.Column('dat_inclusao', sa.Date(), nullable=False),
    sa.Column('cod_pessoa_inclusao', sa.Integer(), nullable=True),
    sa.Column('dat_alteracao', sa.Date(), nullable=True),
    sa.Column('cod_pessoa_alteracao', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['seq_fonte_extracao'], ['flc_fonte_extracao.seq_fonte_extracao'], name=op.f('fk_flc_execucao_extracao_seq_fonte_extracao_flc_fonte_extracao')),
    sa.PrimaryKeyConstraint('seq_execucao_extracao', name=op.f('pk_flc_execucao_extracao'))
    )


def downgrade() -> None:
    op.drop_table('flc_execucao_extracao')
    op.drop_table('flc_fonte_extracao')
