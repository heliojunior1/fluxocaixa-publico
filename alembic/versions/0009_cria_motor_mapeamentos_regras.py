"""cria motor de mapeamentos e regras

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-15

F4.2 (change motor-mapeamentos-regras). O `flc_mapeamento` embrionário é
**recriado**, não alterado: as colunas novas são NOT NULL e as linhas existentes
são placeholder de seed (`txt_condicao='abc != CLASSIFICADOR(...)'`), sem valor
a preservar — nada lia essa tabela fora do próprio CRUD, que sai nesta feature.
O qualificador e a condição descem para `flc_item_mapeamento`.

`downgrade` recria a forma antiga (vazia): reversível em estrutura, não em dados.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0009'
down_revision: Union[str, None] = '0008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Cabeçalho recriado na forma nova (ano + tipo + sistema de origem)
    op.drop_table('flc_mapeamento')
    op.create_table(
        'flc_mapeamento',
        sa.Column('seq_mapeamento', sa.Integer(), nullable=False),
        sa.Column('num_ano_exercicio', sa.Integer(), nullable=False),
        sa.Column('ind_tipo', sa.String(length=1), nullable=False),
        sa.Column('seq_sistema_origem', sa.Integer(), nullable=False),
        sa.Column('dsc_mapeamento', sa.String(length=255), nullable=False),
        sa.Column('ind_status', sa.String(length=1), nullable=False),
        sa.Column('dat_inclusao', sa.Date(), nullable=False),
        sa.Column('cod_pessoa_inclusao', sa.Integer(), nullable=True),
        sa.Column('dat_alteracao', sa.Date(), nullable=True),
        sa.Column('cod_pessoa_alteracao', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ['seq_sistema_origem'], ['flc_sistema_origem.seq_sistema_origem'],
            name=op.f('fk_flc_mapeamento_seq_sistema_origem_flc_sistema_origem'),
        ),
        sa.PrimaryKeyConstraint('seq_mapeamento', name=op.f('pk_flc_mapeamento')),
    )
    op.create_index(
        'ix_flc_mapeamento_chave', 'flc_mapeamento',
        ['num_ano_exercicio', 'ind_tipo', 'seq_sistema_origem'],
    )

    op.create_table(
        'flc_item_mapeamento',
        sa.Column('seq_item_mapeamento', sa.Integer(), nullable=False),
        sa.Column('seq_mapeamento', sa.Integer(), nullable=False),
        sa.Column('seq_qualificador', sa.Integer(), nullable=False),
        sa.Column('txt_regra', sa.String(length=2000), nullable=True),
        sa.Column('ind_inversao_sinal', sa.String(length=1), nullable=False),
        sa.Column('dat_ultima_execucao', sa.Date(), nullable=True),
        sa.Column('ind_status', sa.String(length=1), nullable=False),
        sa.Column('dat_inclusao', sa.Date(), nullable=False),
        sa.Column('cod_pessoa_inclusao', sa.Integer(), nullable=True),
        sa.Column('dat_alteracao', sa.Date(), nullable=True),
        sa.Column('cod_pessoa_alteracao', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ['seq_mapeamento'], ['flc_mapeamento.seq_mapeamento'],
            name=op.f('fk_flc_item_mapeamento_seq_mapeamento_flc_mapeamento'),
        ),
        sa.ForeignKeyConstraint(
            ['seq_qualificador'], ['flc_qualificador.seq_qualificador'],
            name=op.f('fk_flc_item_mapeamento_seq_qualificador_flc_qualificador'),
        ),
        sa.PrimaryKeyConstraint(
            'seq_item_mapeamento', name=op.f('pk_flc_item_mapeamento')),
    )
    op.create_index(
        'ix_flc_item_mapeamento_mapeamento', 'flc_item_mapeamento',
        ['seq_mapeamento', 'ind_status'],
    )

    op.create_table(
        'flc_termo_regra',
        sa.Column('seq_termo_regra', sa.Integer(), nullable=False),
        sa.Column('nom_termo', sa.String(length=100), nullable=False),
        sa.Column('cod_origem_campo', sa.String(length=8), nullable=False),
        sa.Column('nom_campo', sa.String(length=100), nullable=False),
        sa.Column('cod_tipo', sa.String(length=7), nullable=False),
        sa.Column('ind_status', sa.String(length=1), nullable=False),
        sa.Column('dat_inclusao', sa.Date(), nullable=False),
        sa.Column('cod_pessoa_inclusao', sa.Integer(), nullable=True),
        sa.Column('dat_alteracao', sa.Date(), nullable=True),
        sa.Column('cod_pessoa_alteracao', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('seq_termo_regra', name=op.f('pk_flc_termo_regra')),
    )
    op.create_index('ix_flc_termo_regra_nom', 'flc_termo_regra', ['nom_termo'])


def downgrade() -> None:
    op.drop_index('ix_flc_termo_regra_nom', table_name='flc_termo_regra')
    op.drop_table('flc_termo_regra')
    op.drop_index('ix_flc_item_mapeamento_mapeamento', table_name='flc_item_mapeamento')
    op.drop_table('flc_item_mapeamento')

    op.drop_index('ix_flc_mapeamento_chave', table_name='flc_mapeamento')
    op.drop_table('flc_mapeamento')
    op.create_table(
        'flc_mapeamento',
        sa.Column('seq_mapeamento', sa.Integer(), nullable=False),
        sa.Column('seq_qualificador', sa.Integer(), nullable=False),
        sa.Column('dsc_mapeamento', sa.String(length=255), nullable=False),
        sa.Column('txt_condicao', sa.String(length=500), nullable=True),
        sa.Column('ind_status', sa.String(length=1), nullable=False),
        sa.Column('dat_inclusao', sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(
            ['seq_qualificador'], ['flc_qualificador.seq_qualificador'],
            name=op.f('fk_flc_mapeamento_seq_qualificador_flc_qualificador'),
        ),
        sa.PrimaryKeyConstraint('seq_mapeamento', name=op.f('pk_flc_mapeamento')),
    )
