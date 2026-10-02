"""exercício aberto/fechado, data de registro na staging, dias retroativos

Revision ID: 0041
Revises: 0040
Create Date: 2026-10-02 10:00:00.000000

Change `exercicio-aberto-fechado` (cadastros-nucleo R31–R32, automacao R19–R21,
extracao R24–R25):

- `flc_exercicio` (situação atual) + `flc_exercicio_evento` (livro imutável);
- `flc_etl_staging.dat_registro` (data de registro/contabilização na origem);
- `flc_fonte_extracao.num_dias_retroativos` (janela padrão).

⚠️ Neutra: ano sem linha em `flc_exercicio` é ABERTO; colunas nullable ou com
default 0 (= comportamento anterior, janela do dia).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0041'
down_revision: Union[str, None] = '0040'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'flc_exercicio',
        sa.Column('num_ano_exercicio', sa.Integer(), autoincrement=False, nullable=False),
        sa.Column('cod_situacao', sa.String(length=1), nullable=False),
        sa.Column('dat_inclusao', sa.Date(), nullable=False),
        sa.Column('cod_pessoa_inclusao', sa.Integer(), nullable=True),
        sa.Column('dat_alteracao', sa.Date(), nullable=True),
        sa.Column('cod_pessoa_alteracao', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('num_ano_exercicio', name=op.f('pk_flc_exercicio')),
    )
    op.create_table(
        'flc_exercicio_evento',
        sa.Column('seq_exercicio_evento', sa.Integer(), nullable=False),
        sa.Column('num_ano_exercicio', sa.Integer(), nullable=False),
        sa.Column('cod_tipo_evento', sa.String(length=1), nullable=False),
        sa.Column('dsc_motivo', sa.String(length=1000), nullable=True),
        sa.Column('dat_evento', sa.DateTime(), nullable=False),
        sa.Column('cod_pessoa_evento', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('seq_exercicio_evento', name=op.f('pk_flc_exercicio_evento')),
    )
    with op.batch_alter_table('flc_etl_staging') as batch:
        batch.add_column(sa.Column('dat_registro', sa.Date(), nullable=True))
    with op.batch_alter_table('flc_fonte_extracao') as batch:
        batch.add_column(sa.Column('num_dias_retroativos', sa.Integer(), nullable=False,
                                   server_default='0'))


def downgrade() -> None:
    # ⚠️ Perda declarada: situação e histórico dos exercícios, data de registro
    # das linhas da staging e a janela retroativa das fontes.
    with op.batch_alter_table('flc_fonte_extracao') as batch:
        batch.drop_column('num_dias_retroativos')
    with op.batch_alter_table('flc_etl_staging') as batch:
        batch.drop_column('dat_registro')
    op.drop_table('flc_exercicio_evento')
    op.drop_table('flc_exercicio')
