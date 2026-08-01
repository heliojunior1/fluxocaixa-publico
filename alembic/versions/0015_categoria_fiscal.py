"""categoria fiscal explicita no qualificador e metas por ano

Revision ID: 0015
Revises: 0014
Create Date: 2026-07-28 11:02:37.884219

Spec `relatorios` R17–R19 e `cadastros-nucleo` R15. Substitui o casamento por
substring na descrição do qualificador por marcação explícita, herdada pela
árvore.

⚠️ **Nada de dado é convertido, e isso é deliberado.** Seria tentador "migrar"
a heurística — varrer as descrições atrás de "pessoal/saúde/educação" e marcar
o que casasse. Não se faz isso aqui: importar os acertos da heurística importa
junto os erros dela ("Material de consumo — saúde" no piso da saúde), e os
erros passariam a ter aparência de decisão humana registrada. A marcação nasce
vazia; cada instalação marca a sua árvore, uma vez, no bloco.

Consequência declarada: até que se marque, as metas de pessoal, saúde e
educação apuram zero. Preferível a apurar um número errado com cara de certo —
que é exatamente o que a heurística fazia.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0015'
down_revision: Union[str, None] = '0014'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'flc_categoria_fiscal',
        sa.Column('seq_categoria_fiscal', sa.Integer(), nullable=False),
        sa.Column('txt_sigla', sa.String(length=30), nullable=False),
        sa.Column('dsc_categoria', sa.String(length=120), nullable=False),
        # 'R' receita corrente líquida | 'D' despesa total
        sa.Column('cod_base_calculo', sa.String(length=1), nullable=False),
        # 'P' piso (≥) | 'T' teto (≤)
        sa.Column('cod_sentido', sa.String(length=1), nullable=False),
        sa.Column('val_limite', sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column('val_limite_atencao', sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column('ind_status', sa.String(length=1), nullable=False),
        sa.Column('dat_inclusao', sa.Date(), nullable=False),
        sa.Column('cod_pessoa_inclusao', sa.Integer(), nullable=True),
        sa.Column('dat_alteracao', sa.Date(), nullable=True),
        sa.Column('cod_pessoa_alteracao', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('seq_categoria_fiscal'),
        sa.UniqueConstraint('txt_sigla'),
    )

    op.create_table(
        'flc_meta_fiscal_ano',
        sa.Column('seq_meta_fiscal_ano', sa.Integer(), nullable=False),
        sa.Column('num_ano', sa.Integer(), nullable=False),
        sa.Column('val_superavit_primario', sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column('ind_status', sa.String(length=1), nullable=False),
        sa.Column('dat_inclusao', sa.Date(), nullable=False),
        sa.Column('cod_pessoa_inclusao', sa.Integer(), nullable=True),
        sa.Column('dat_alteracao', sa.Date(), nullable=True),
        sa.Column('cod_pessoa_alteracao', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('seq_meta_fiscal_ano'),
        sa.UniqueConstraint('num_ano'),
    )

    # A marcação nasce NULA em toda a árvore — ver o aviso no cabeçalho.
    with op.batch_alter_table('flc_qualificador') as batch:
        batch.add_column(sa.Column('cod_categoria_fiscal', sa.Integer(), nullable=True))
        batch.create_foreign_key(
            'fk_flc_qualificador_cod_categoria_fiscal_flc_categoria_fiscal',
            'flc_categoria_fiscal', ['cod_categoria_fiscal'], ['seq_categoria_fiscal'],
        )


def downgrade() -> None:
    # ⚠️ Perda declarada: as marcações feitas pelo usuário somem, e o relatório
    # volta a casar substring na descrição. Não há para onde levá-las — a
    # heurística não tem lugar onde guardar "este bloco é educação".
    with op.batch_alter_table('flc_qualificador') as batch:
        batch.drop_constraint(
            'fk_flc_qualificador_cod_categoria_fiscal_flc_categoria_fiscal',
            type_='foreignkey')
        batch.drop_column('cod_categoria_fiscal')

    op.drop_table('flc_meta_fiscal_ano')
    op.drop_table('flc_categoria_fiscal')
