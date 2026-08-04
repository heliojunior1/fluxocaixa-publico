"""qualificador por exercício e identidade estável (cadastros-nucleo R25–R27)

F10.1 (change qualificador-exercicio-identidade): `flc_qualificador` ganha
`num_ano_exercicio` (backfill = ano corrente do upgrade — o plano existente
vira o "plano base" do exercício em curso) e `cod_rubrica_raiz` (backfill =
o próprio seq: como o código era único global, todo o histórico nasce
costurado de graça — decisão D-B da concepção).

⚠️ SEM replicação da história e SEM repoint (decisão D1 do design): até a
F10.4 os relatórios e combos leem a árvore sem filtro de ano — espelhos
duplicariam cada nó em instalação migrada, e a suíte (banco novo) passaria
verde mesmo assim. A imutabilidade histórica começa no primeiro exercício
aberto pela F10.3.

A unique GLOBAL de `num_qualificador` cai; entra o índice único parcial
(ano, código) entre ativos — padrão da migração 0033 (LOA).

Downgrade: possível sem perda porque não há replicação — códigos continuam
únicos globalmente.

Revision ID: 0035
Revises: 0034
"""
from datetime import date

import sqlalchemy as sa
from alembic import op

revision = '0035'
down_revision = '0034'
branch_labels = None
depends_on = None


def upgrade():
    ano_corrente = date.today().year

    with op.batch_alter_table('flc_qualificador') as batch:
        batch.add_column(sa.Column('num_ano_exercicio', sa.Integer(),
                                   nullable=True))
        batch.add_column(sa.Column('cod_rubrica_raiz', sa.Integer(),
                                   nullable=True))

    conn = op.get_bind()
    conn.execute(sa.text(
        "UPDATE flc_qualificador SET num_ano_exercicio = :ano "
        "WHERE num_ano_exercicio IS NULL"
    ), {"ano": ano_corrente})
    conn.execute(sa.text(
        "UPDATE flc_qualificador SET cod_rubrica_raiz = seq_qualificador "
        "WHERE cod_rubrica_raiz IS NULL"
    ))

    with op.batch_alter_table('flc_qualificador') as batch:
        batch.alter_column('num_ano_exercicio', existing_type=sa.Integer(),
                           nullable=False)
        batch.drop_constraint('uq_flc_qualificador_num_qualificador',
                              type_='unique')

    op.create_index(
        'ux_flc_qualificador_ano_codigo_ativo', 'flc_qualificador',
        ['num_ano_exercicio', 'num_qualificador'],
        unique=True,
        sqlite_where=sa.text("ind_status = 'A'"),
        postgresql_where=sa.text("ind_status = 'A'"),
    )


def downgrade():
    op.drop_index('ux_flc_qualificador_ano_codigo_ativo',
                  table_name='flc_qualificador')
    with op.batch_alter_table('flc_qualificador') as batch:
        batch.create_unique_constraint('uq_flc_qualificador_num_qualificador',
                                       ['num_qualificador'])
        batch.drop_column('cod_rubrica_raiz')
        batch.drop_column('num_ano_exercicio')
