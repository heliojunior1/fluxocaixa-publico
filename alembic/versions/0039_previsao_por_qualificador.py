"""previsão por qualificador: método por rubrica, cópia de cenário e setores

Revision ID: 0039
Revises: 0038
Create Date: 2026-09-22 10:00:00.000000

Change `previsao-por-qualificador` (docs/previsao-metodo-por-qualificador.md):

- `flc_setor_previsao` — setores que respondem por um recorte da previsão
  (opcional: sem setor o sistema se comporta como antes);
- `flc_cenario_metodo` — marcação de método por qualificador, com herança
  pela árvore resolvida na leitura;
- `flc_cenario_formula` — fórmula PRÓPRIA do cenário (a biblioteca
  `flc_rubrica_formula` segue por referência);
- `flc_simulador_cenario` + `seq_cenario_origem` (cópia) e
  `seq_setor_previsao` (cenário setorial);
- `flc_qualificador` + `seq_setor_previsao` (marcação própria do recorte);
- `flc_projecao_versao` + situação da proposta setorial e avaliação;
- `flc_projecao_valor` + `cod_metodo` e `seq_qualificador_calculo` (rastro
  do número).

⚠️ Comportamentalmente neutra: tudo nullable ou tabela nova — nenhum número
muda, nenhum dado é convertido. Versão antiga fica com o rastro nulo (não se
fabrica o método que a gerou).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0039'
down_revision: Union[str, None] = '0038'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'flc_setor_previsao',
        sa.Column('seq_setor_previsao', sa.Integer(), nullable=False),
        sa.Column('nom_setor', sa.String(length=100), nullable=False),
        sa.Column('sgl_setor', sa.String(length=20), nullable=False),
        sa.Column('dsc_setor', sa.String(length=255), nullable=True),
        sa.Column('ind_status', sa.String(length=1), nullable=False),
        sa.Column('dat_inclusao', sa.Date(), nullable=False),
        sa.Column('cod_pessoa_inclusao', sa.Integer(), nullable=True),
        sa.Column('dat_alteracao', sa.Date(), nullable=True),
        sa.Column('cod_pessoa_alteracao', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint(
            'seq_setor_previsao', name=op.f('pk_flc_setor_previsao')),
    )

    with op.batch_alter_table('flc_simulador_cenario') as batch:
        batch.add_column(sa.Column('seq_cenario_origem', sa.Integer(),
                                   nullable=True))
        batch.add_column(sa.Column('seq_setor_previsao', sa.Integer(),
                                   nullable=True))
        batch.create_foreign_key(
            'fk_flc_simulador_cenario_seq_cenario_origem_flc_simulador_cenario',
            'flc_simulador_cenario',
            ['seq_cenario_origem'], ['seq_simulador_cenario'])
        batch.create_foreign_key(
            'fk_flc_simulador_cenario_seq_setor_previsao_flc_setor_previsao',
            'flc_setor_previsao',
            ['seq_setor_previsao'], ['seq_setor_previsao'])

    with op.batch_alter_table('flc_qualificador') as batch:
        batch.add_column(sa.Column('seq_setor_previsao', sa.Integer(),
                                   nullable=True))
        batch.create_foreign_key(
            'fk_flc_qualificador_seq_setor_previsao_flc_setor_previsao',
            'flc_setor_previsao',
            ['seq_setor_previsao'], ['seq_setor_previsao'])

    op.create_table(
        'flc_cenario_metodo',
        sa.Column('seq_cenario_metodo', sa.Integer(), nullable=False),
        sa.Column('seq_simulador_cenario', sa.Integer(), nullable=False),
        sa.Column('seq_qualificador', sa.Integer(), nullable=False),
        sa.Column('cod_metodo', sa.String(length=30), nullable=False),
        sa.Column('json_configuracao', sa.Text(), nullable=True),
        sa.Column('dat_inclusao', sa.Date(), nullable=False),
        sa.Column('cod_pessoa_inclusao', sa.Integer(), nullable=False),
        sa.Column('dat_alteracao', sa.Date(), nullable=True),
        sa.Column('cod_pessoa_alteracao', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ['seq_simulador_cenario'], ['flc_simulador_cenario.seq_simulador_cenario'],
            name=op.f('fk_flc_cenario_metodo_seq_simulador_cenario_flc_simulador_cenario')),
        sa.ForeignKeyConstraint(
            ['seq_qualificador'], ['flc_qualificador.seq_qualificador'],
            name=op.f('fk_flc_cenario_metodo_seq_qualificador_flc_qualificador')),
        sa.PrimaryKeyConstraint(
            'seq_cenario_metodo', name=op.f('pk_flc_cenario_metodo')),
        sa.UniqueConstraint('seq_simulador_cenario', 'seq_qualificador',
                            name='uix_cenario_metodo_qualificador'),
    )

    op.create_table(
        'flc_cenario_formula',
        sa.Column('seq_cenario_formula', sa.Integer(), nullable=False),
        sa.Column('seq_simulador_cenario', sa.Integer(), nullable=False),
        sa.Column('seq_qualificador', sa.Integer(), nullable=False),
        sa.Column('dsc_formula_expressao', sa.Text(), nullable=False),
        sa.Column('dat_inclusao', sa.Date(), nullable=False),
        sa.Column('cod_pessoa_inclusao', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ['seq_simulador_cenario'], ['flc_simulador_cenario.seq_simulador_cenario'],
            name=op.f('fk_flc_cenario_formula_seq_simulador_cenario_flc_simulador_cenario')),
        sa.ForeignKeyConstraint(
            ['seq_qualificador'], ['flc_qualificador.seq_qualificador'],
            name=op.f('fk_flc_cenario_formula_seq_qualificador_flc_qualificador')),
        sa.PrimaryKeyConstraint(
            'seq_cenario_formula', name=op.f('pk_flc_cenario_formula')),
        sa.UniqueConstraint('seq_simulador_cenario', 'seq_qualificador',
                            name='uix_cenario_formula_qualificador'),
    )

    with op.batch_alter_table('flc_projecao_versao') as batch:
        batch.add_column(sa.Column('cod_situacao_proposta', sa.String(length=1),
                                   nullable=True))
        batch.add_column(sa.Column('dsc_motivo_devolucao', sa.String(length=255),
                                   nullable=True))
        batch.add_column(sa.Column('dat_avaliacao', sa.DateTime(), nullable=True))
        batch.add_column(sa.Column('cod_pessoa_avaliacao', sa.Integer(),
                                   nullable=True))

    with op.batch_alter_table('flc_projecao_valor') as batch:
        batch.add_column(sa.Column('cod_metodo', sa.String(length=40),
                                   nullable=True))
        batch.add_column(sa.Column('seq_qualificador_calculo', sa.Integer(),
                                   nullable=True))
        batch.create_foreign_key(
            'fk_flc_projecao_valor_seq_qualificador_calculo_flc_qualificador',
            'flc_qualificador',
            ['seq_qualificador_calculo'], ['seq_qualificador'])


def downgrade() -> None:
    # ⚠️ Perda declarada: marcações de método, fórmulas próprias, setores,
    # situação das propostas e o rastro dos valores projetados.
    with op.batch_alter_table('flc_projecao_valor') as batch:
        batch.drop_constraint(
            'fk_flc_projecao_valor_seq_qualificador_calculo_flc_qualificador',
            type_='foreignkey')
        batch.drop_column('seq_qualificador_calculo')
        batch.drop_column('cod_metodo')

    with op.batch_alter_table('flc_projecao_versao') as batch:
        batch.drop_column('cod_pessoa_avaliacao')
        batch.drop_column('dat_avaliacao')
        batch.drop_column('dsc_motivo_devolucao')
        batch.drop_column('cod_situacao_proposta')

    op.drop_table('flc_cenario_formula')
    op.drop_table('flc_cenario_metodo')

    with op.batch_alter_table('flc_qualificador') as batch:
        batch.drop_constraint(
            'fk_flc_qualificador_seq_setor_previsao_flc_setor_previsao',
            type_='foreignkey')
        batch.drop_column('seq_setor_previsao')

    with op.batch_alter_table('flc_simulador_cenario') as batch:
        batch.drop_constraint(
            'fk_flc_simulador_cenario_seq_setor_previsao_flc_setor_previsao',
            type_='foreignkey')
        batch.drop_constraint(
            'fk_flc_simulador_cenario_seq_cenario_origem_flc_simulador_cenario',
            type_='foreignkey')
        batch.drop_column('seq_setor_previsao')
        batch.drop_column('seq_cenario_origem')

    op.drop_table('flc_setor_previsao')
