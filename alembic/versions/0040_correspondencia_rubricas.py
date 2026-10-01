"""correspondência de rubricas entre exercícios (De/Para)

Revision ID: 0040
Revises: 0039
Create Date: 2026-10-01 10:00:00.000000

Change `correspondencia-rubricas-entre-exercicios` (previsao R30–R33):

- `flc_correspondencia_rubrica` (+ origem, destino) — fusão N→1 e
  desdobramento 1→N por identidade de rubrica (raiz), com vigência, ato e
  fundamento;
- `flc_correspondencia_evento` — livro IMUTÁVEL; o seq é a versão do De/Para;
- `flc_correspondencia_rateio` — percentuais do rateio, presos ao evento que
  os definiu;
- `flc_projecao_valor` + `seq_correspondencia_rubrica` (valor do grupo com
  distribuição pendente).

⚠️ Comportamentalmente neutra: tabelas novas e coluna nullable — sem
correspondência cadastrada a série é exatamente a da raiz.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0040'
down_revision: Union[str, None] = '0039'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'flc_correspondencia_rubrica',
        sa.Column('seq_correspondencia_rubrica', sa.Integer(), nullable=False),
        sa.Column('cod_tipo', sa.String(length=1), nullable=False),
        sa.Column('num_ano_vigencia', sa.Integer(), nullable=False),
        sa.Column('dsc_referencia_ato', sa.String(length=255), nullable=False),
        sa.Column('dsc_fundamento', sa.String(length=500), nullable=False),
        sa.Column('ind_status', sa.String(length=1), nullable=False),
        sa.Column('dat_inclusao', sa.Date(), nullable=False),
        sa.Column('cod_pessoa_inclusao', sa.Integer(), nullable=True),
        sa.Column('dat_alteracao', sa.Date(), nullable=True),
        sa.Column('cod_pessoa_alteracao', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('seq_correspondencia_rubrica',
                                name=op.f('pk_flc_correspondencia_rubrica')),
    )
    for tabela, pk, extra in (
        ('flc_correspondencia_origem', 'seq_correspondencia_origem', []),
        ('flc_correspondencia_destino', 'seq_correspondencia_destino',
         [sa.Column('txt_regra_reconstrucao', sa.String(length=1000), nullable=True)]),
    ):
        op.create_table(
            tabela,
            sa.Column(pk, sa.Integer(), nullable=False),
            sa.Column('seq_correspondencia_rubrica', sa.Integer(), nullable=False),
            sa.Column('cod_rubrica_raiz', sa.Integer(), nullable=False),
            *extra,
            sa.ForeignKeyConstraint(
                ['seq_correspondencia_rubrica'],
                ['flc_correspondencia_rubrica.seq_correspondencia_rubrica'],
                name=op.f(f'fk_{tabela}_seq_correspondencia_rubrica_flc_correspondencia_rubrica')),
            sa.PrimaryKeyConstraint(pk, name=op.f(f'pk_{tabela}')),
        )
    op.create_table(
        'flc_correspondencia_evento',
        sa.Column('seq_correspondencia_evento', sa.Integer(), nullable=False),
        sa.Column('seq_correspondencia_rubrica', sa.Integer(), nullable=False),
        sa.Column('cod_tipo_evento', sa.String(length=1), nullable=False),
        sa.Column('dsc_justificativa', sa.String(length=500), nullable=True),
        sa.Column('dat_evento', sa.DateTime(), nullable=False),
        sa.Column('cod_pessoa_evento', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ['seq_correspondencia_rubrica'],
            ['flc_correspondencia_rubrica.seq_correspondencia_rubrica'],
            name=op.f('fk_flc_correspondencia_evento_seq_correspondencia_rubrica_flc_correspondencia_rubrica')),
        sa.PrimaryKeyConstraint('seq_correspondencia_evento',
                                name=op.f('pk_flc_correspondencia_evento')),
    )
    op.create_table(
        'flc_correspondencia_rateio',
        sa.Column('seq_correspondencia_rateio', sa.Integer(), nullable=False),
        sa.Column('seq_correspondencia_evento', sa.Integer(), nullable=False),
        sa.Column('cod_rubrica_raiz', sa.Integer(), nullable=False),
        sa.Column('val_percentual', sa.Numeric(precision=7, scale=4), nullable=False),
        sa.ForeignKeyConstraint(
            ['seq_correspondencia_evento'],
            ['flc_correspondencia_evento.seq_correspondencia_evento'],
            name=op.f('fk_flc_correspondencia_rateio_seq_correspondencia_evento_flc_correspondencia_evento')),
        sa.PrimaryKeyConstraint('seq_correspondencia_rateio',
                                name=op.f('pk_flc_correspondencia_rateio')),
    )
    with op.batch_alter_table('flc_projecao_valor') as batch:
        batch.add_column(sa.Column('seq_correspondencia_rubrica', sa.Integer(),
                                   nullable=True))
        batch.create_foreign_key(
            'fk_flc_projecao_valor_seq_correspondencia_rubrica_flc_correspondencia_rubrica',
            'flc_correspondencia_rubrica',
            ['seq_correspondencia_rubrica'], ['seq_correspondencia_rubrica'])


def downgrade() -> None:
    # ⚠️ Perda declarada: o De/Para inteiro e o valor dos grupos pendentes
    # nas versões publicadas (as linhas ficam, sem a identificação do grupo).
    with op.batch_alter_table('flc_projecao_valor') as batch:
        batch.drop_constraint(
            'fk_flc_projecao_valor_seq_correspondencia_rubrica_flc_correspondencia_rubrica',
            type_='foreignkey')
        batch.drop_column('seq_correspondencia_rubrica')
    op.drop_table('flc_correspondencia_rateio')
    op.drop_table('flc_correspondencia_evento')
    op.drop_table('flc_correspondencia_destino')
    op.drop_table('flc_correspondencia_origem')
    op.drop_table('flc_correspondencia_rubrica')
