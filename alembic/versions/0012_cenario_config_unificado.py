"""unifica config do cenario por perna C/D e converge o tipo da projecao

Revision ID: 0012
Revises: 0011
Create Date: 2026-07-22 09:41:18.223907

Transformação de dados do usuário (spec previsao R4/R5). Quatro tabelas
espelhadas viram duas, discriminadas pela perna — `cod_tipo_lancamento` 'C'/'D',
o MESMO código do lançamento, com FK para o domínio:

    flc_cenario_receita  ─┐
    flc_cenario_despesa  ─┴─→ flc_cenario_config   (perna + modelo + config)
    flc_cenario_receita_ajuste ─┐
    flc_cenario_despesa_ajuste ─┴─→ flc_cenario_ajuste

⚠️ Uma QUINTA tabela entra na conta (D8, achado no apply):
`flc_modelo_economico_parametro` tinha FK para `flc_cenario_receita`, que esta
revisão dropa — reponta para a config unificada.

Também converge `flc_projecao_valor.cod_tipo` de 'R'/'D' para 'C'/'D' (R5),
fechando o non-goal que a F6.1b registrou: sem isso o sistema ficaria com duas
representações vivas de crédito.

O `downgrade` reconstrói as tabelas separadas a partir da config unificada.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0012'
down_revision: Union[str, None] = '0011'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_FK_PARAM = 'fk_flc_modelo_economico_parametro_seq_cenario_receita_flc_cenario_receita'


def upgrade() -> None:
    conn = op.get_bind()

    op.create_table(
        'flc_cenario_config',
        sa.Column('seq_cenario_config', sa.Integer(), nullable=False),
        sa.Column('seq_simulador_cenario', sa.Integer(), nullable=False),
        sa.Column('cod_tipo_lancamento', sa.String(length=1), nullable=False),
        sa.Column('cod_tipo_modelo', sa.String(length=20), nullable=False),
        sa.Column('json_configuracao', sa.Text(), nullable=True),
        sa.Column('dat_inclusao', sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(
            ['seq_simulador_cenario'], ['flc_simulador_cenario.seq_simulador_cenario'],
            name='fk_flc_cenario_config_seq_simulador_cenario_flc_simulador_cenario'),
        sa.ForeignKeyConstraint(
            ['cod_tipo_lancamento'], ['flc_tipo_lancamento.cod_tipo_lancamento'],
            name='fk_flc_cenario_config_cod_tipo_lancamento_flc_tipo_lancamento'),
        sa.PrimaryKeyConstraint('seq_cenario_config', name='pk_flc_cenario_config'),
        sa.UniqueConstraint('seq_simulador_cenario', 'cod_tipo_lancamento',
                            name='uix_cenario_config_perna'),
    )
    op.create_table(
        'flc_cenario_ajuste',
        sa.Column('seq_cenario_ajuste', sa.Integer(), nullable=False),
        sa.Column('seq_cenario_config', sa.Integer(), nullable=False),
        sa.Column('seq_qualificador', sa.Integer(), nullable=False),
        sa.Column('ano', sa.Integer(), nullable=False),
        sa.Column('mes', sa.Integer(), nullable=False),
        sa.Column('cod_tipo_ajuste', sa.String(length=1), nullable=False),
        sa.Column('val_ajuste', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('dsc_ajuste', sa.String(length=100), nullable=True),
        sa.Column('dat_inclusao', sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(
            ['seq_cenario_config'], ['flc_cenario_config.seq_cenario_config'],
            name='fk_flc_cenario_ajuste_seq_cenario_config_flc_cenario_config'),
        sa.ForeignKeyConstraint(
            ['seq_qualificador'], ['flc_qualificador.seq_qualificador'],
            name='fk_flc_cenario_ajuste_seq_qualificador_flc_qualificador'),
        sa.PrimaryKeyConstraint('seq_cenario_ajuste', name='pk_flc_cenario_ajuste'),
        sa.UniqueConstraint('seq_cenario_config', 'seq_qualificador', 'ano', 'mes',
                            name='uix_cenario_ajuste'),
    )

    # --- dados: receita → 'C', despesa → 'D' --------------------------------
    for tabela, perna, pk in (('flc_cenario_receita', 'C', 'seq_cenario_receita'),
                              ('flc_cenario_despesa', 'D', 'seq_cenario_despesa')):
        conn.execute(sa.text(
            f"INSERT INTO flc_cenario_config "
            f"(seq_simulador_cenario, cod_tipo_lancamento, cod_tipo_modelo, "
            f" json_configuracao, dat_inclusao) "
            f"SELECT seq_simulador_cenario, '{perna}', cod_tipo_cenario, "
            f"       json_configuracao, dat_inclusao FROM {tabela}"
        ))
        conn.execute(sa.text(
            f"INSERT INTO flc_cenario_ajuste "
            f"(seq_cenario_config, seq_qualificador, ano, mes, cod_tipo_ajuste, "
            f" val_ajuste, dsc_ajuste, dat_inclusao) "
            f"SELECT cfg.seq_cenario_config, a.seq_qualificador, a.ano, a.mes, "
            f"       a.cod_tipo_ajuste, a.val_ajuste, a.dsc_ajuste, a.dat_inclusao "
            f"FROM {tabela}_ajuste a "
            f"JOIN {tabela} o ON o.{pk} = a.{pk} "
            f"JOIN flc_cenario_config cfg "
            f"  ON cfg.seq_simulador_cenario = o.seq_simulador_cenario "
            f" AND cfg.cod_tipo_lancamento = '{perna}'"
        ))

    # --- D8: parâmetros econômicos repontam para a config -------------------
    with op.batch_alter_table('flc_modelo_economico_parametro') as batch:
        batch.add_column(sa.Column('seq_cenario_config', sa.Integer(), nullable=True))
    conn.execute(sa.text(
        "UPDATE flc_modelo_economico_parametro SET seq_cenario_config = ("
        "  SELECT cfg.seq_cenario_config FROM flc_cenario_receita r "
        "  JOIN flc_cenario_config cfg "
        "    ON cfg.seq_simulador_cenario = r.seq_simulador_cenario "
        "   AND cfg.cod_tipo_lancamento = 'C' "
        "  WHERE r.seq_cenario_receita = flc_modelo_economico_parametro.seq_cenario_receita)"
    ))
    with op.batch_alter_table('flc_modelo_economico_parametro') as batch:
        batch.drop_constraint(_FK_PARAM, type_='foreignkey')
        batch.drop_column('seq_cenario_receita')
        # nasceu nullable só para o UPDATE acima; o model a declara obrigatória
        batch.alter_column('seq_cenario_config', existing_type=sa.Integer(),
                           nullable=False)
        batch.create_foreign_key(
            'fk_flc_modelo_economico_parametro_seq_cenario_config_flc_cenario_config',
            'flc_cenario_config', ['seq_cenario_config'], ['seq_cenario_config'])

    # --- R5: 'R' → 'C' na projeção persistida -------------------------------
    conn.execute(sa.text(
        "UPDATE flc_projecao_valor SET cod_tipo = 'C' WHERE cod_tipo = 'R'"))

    op.drop_table('flc_cenario_receita_ajuste')
    op.drop_table('flc_cenario_despesa_ajuste')
    op.drop_table('flc_cenario_receita')
    op.drop_table('flc_cenario_despesa')


def downgrade() -> None:
    conn = op.get_bind()

    for tabela, pk, fk_nome in (
        ('flc_cenario_receita', 'seq_cenario_receita', 'fk_flc_cenario_receita_seq_simulador_cenario_flc_simulador_cenario'),
        ('flc_cenario_despesa', 'seq_cenario_despesa', 'fk_flc_cenario_despesa_seq_simulador_cenario_flc_simulador_cenario'),
    ):
        op.create_table(
            tabela,
            sa.Column(pk, sa.Integer(), nullable=False),
            sa.Column('seq_simulador_cenario', sa.Integer(), nullable=False),
            sa.Column('cod_tipo_cenario', sa.String(length=20), nullable=False),
            sa.Column('json_configuracao', sa.Text(), nullable=True),
            sa.Column('dat_inclusao', sa.Date(), nullable=False),
            sa.ForeignKeyConstraint(['seq_simulador_cenario'],
                                    ['flc_simulador_cenario.seq_simulador_cenario'],
                                    name=fk_nome),
            sa.PrimaryKeyConstraint(pk, name=f'pk_{tabela}'),
            sa.UniqueConstraint('seq_simulador_cenario', name=f'uq_{tabela}_simulador'),
        )
        op.create_table(
            f'{tabela}_ajuste',
            sa.Column(f'{pk}_ajuste', sa.Integer(), nullable=False),
            sa.Column(pk, sa.Integer(), nullable=False),
            sa.Column('seq_qualificador', sa.Integer(), nullable=False),
            sa.Column('ano', sa.Integer(), nullable=False),
            sa.Column('mes', sa.Integer(), nullable=False),
            sa.Column('cod_tipo_ajuste', sa.String(length=1), nullable=False),
            sa.Column('val_ajuste', sa.Numeric(precision=18, scale=2), nullable=False),
            sa.Column('dsc_ajuste', sa.String(length=100), nullable=True),
            sa.Column('dat_inclusao', sa.Date(), nullable=False),
            sa.ForeignKeyConstraint([pk], [f'{tabela}.{pk}'],
                                    name=f'fk_{tabela}_ajuste_{pk}_{tabela}'),
            sa.ForeignKeyConstraint(['seq_qualificador'],
                                    ['flc_qualificador.seq_qualificador'],
                                    name=f'fk_{tabela}_ajuste_seq_qualificador_flc_qualificador'),
            sa.PrimaryKeyConstraint(f'{pk}_ajuste', name=f'pk_{tabela}_ajuste'),
        )

    for tabela, perna, pk in (('flc_cenario_receita', 'C', 'seq_cenario_receita'),
                              ('flc_cenario_despesa', 'D', 'seq_cenario_despesa')):
        conn.execute(sa.text(
            f"INSERT INTO {tabela} (seq_simulador_cenario, cod_tipo_cenario, "
            f" json_configuracao, dat_inclusao) "
            f"SELECT seq_simulador_cenario, cod_tipo_modelo, json_configuracao, "
            f"       dat_inclusao FROM flc_cenario_config "
            f"WHERE cod_tipo_lancamento = '{perna}'"
        ))
        conn.execute(sa.text(
            f"INSERT INTO {tabela}_ajuste ({pk}, seq_qualificador, ano, mes, "
            f" cod_tipo_ajuste, val_ajuste, dsc_ajuste, dat_inclusao) "
            f"SELECT o.{pk}, a.seq_qualificador, a.ano, a.mes, a.cod_tipo_ajuste, "
            f"       a.val_ajuste, a.dsc_ajuste, a.dat_inclusao "
            f"FROM flc_cenario_ajuste a "
            f"JOIN flc_cenario_config cfg ON cfg.seq_cenario_config = a.seq_cenario_config "
            f"JOIN {tabela} o ON o.seq_simulador_cenario = cfg.seq_simulador_cenario "
            f"WHERE cfg.cod_tipo_lancamento = '{perna}'"
        ))

    with op.batch_alter_table('flc_modelo_economico_parametro') as batch:
        batch.add_column(sa.Column('seq_cenario_receita', sa.Integer(), nullable=True))
    conn.execute(sa.text(
        "UPDATE flc_modelo_economico_parametro SET seq_cenario_receita = ("
        "  SELECT r.seq_cenario_receita FROM flc_cenario_config cfg "
        "  JOIN flc_cenario_receita r "
        "    ON r.seq_simulador_cenario = cfg.seq_simulador_cenario "
        "  WHERE cfg.seq_cenario_config = flc_modelo_economico_parametro.seq_cenario_config)"
    ))
    with op.batch_alter_table('flc_modelo_economico_parametro') as batch:
        batch.drop_constraint(
            'fk_flc_modelo_economico_parametro_seq_cenario_config_flc_cenario_config',
            type_='foreignkey')
        batch.drop_column('seq_cenario_config')
        batch.alter_column('seq_cenario_receita', existing_type=sa.Integer(),
                           nullable=False)
        batch.create_foreign_key(_FK_PARAM, 'flc_cenario_receita',
                                 ['seq_cenario_receita'], ['seq_cenario_receita'])

    conn.execute(sa.text(
        "UPDATE flc_projecao_valor SET cod_tipo = 'R' WHERE cod_tipo = 'C'"))

    op.drop_table('flc_cenario_ajuste')
    op.drop_table('flc_cenario_config')
