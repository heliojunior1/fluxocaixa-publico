"""unicidade da LOA entre ativos, com dedupe (cadastros-nucleo R24)

`flc_loa` não tinha constraint e o upsert era check-then-insert: duplo submit
ou requests concorrentes criavam duas linhas ativas por (ano, qualificador) —
e tudo que soma a LOA dobrava (teto do autorizado, metas fiscais, previsto).

Dedupe ANTES da constraint: entre ativos da mesma chave, fica o de maior
seq_loa (o upsert sempre atualizou o primeiro encontrado; o mais novo é o
valor vigente); os demais viram 'I' — histórico preservado, nunca DELETE.
O downgrade remove índice e colunas; as linhas inativadas NÃO voltam a
ativas (perda documentada, como no dedupe da 0004).

Também entram as colunas de auditoria da convenção (nullable: linha legada
não ganha autor fabricado).

Revision ID: 0033
Revises: 0032
"""
import sqlalchemy as sa
from alembic import op

revision = '0033'
down_revision = '0032'
branch_labels = None
depends_on = None


def _deduplicar() -> None:
    conn = op.get_bind()
    duplicatas = conn.execute(sa.text(
        """
        SELECT num_ano, seq_qualificador, MAX(seq_loa) AS manter
        FROM flc_loa
        WHERE ind_status = 'A'
        GROUP BY num_ano, seq_qualificador
        HAVING COUNT(*) > 1
        """
    )).fetchall()

    for num_ano, seq_qualificador, manter in duplicatas:
        conn.execute(sa.text(
            """
            UPDATE flc_loa SET ind_status = 'I'
            WHERE num_ano = :ano AND seq_qualificador = :q
              AND ind_status = 'A' AND seq_loa <> :manter
            """
        ), {"ano": num_ano, "q": seq_qualificador, "manter": manter})


def upgrade():
    _deduplicar()
    with op.batch_alter_table('flc_loa') as batch:
        batch.add_column(sa.Column('cod_pessoa_inclusao', sa.Integer(),
                                   nullable=True))
        batch.add_column(sa.Column('dat_alteracao', sa.Date(), nullable=True))
        batch.add_column(sa.Column('cod_pessoa_alteracao', sa.Integer(),
                                   nullable=True))
    op.create_index(
        'ux_flc_loa_ano_qualificador_ativo', 'flc_loa',
        ['num_ano', 'seq_qualificador'],
        unique=True,
        sqlite_where=sa.text("ind_status = 'A'"),
        postgresql_where=sa.text("ind_status = 'A'"),
    )


def downgrade():
    op.drop_index('ux_flc_loa_ano_qualificador_ativo', table_name='flc_loa')
    with op.batch_alter_table('flc_loa') as batch:
        batch.drop_column('cod_pessoa_alteracao')
        batch.drop_column('dat_alteracao')
        batch.drop_column('cod_pessoa_inclusao')
