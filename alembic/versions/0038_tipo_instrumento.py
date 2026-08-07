"""tipo de instrumento financeiro e liquidez do fundo

Revision ID: 0038
Revises: 0037
Create Date: 2026-08-07 09:00:00.000000

Change `tipo-instrumento-financeiro` (specs saldo-por-fundo R22,
fonte-recurso R5, desembolso R9). Generaliza o "fundo" para instrumento
financeiro: domínio `flc_tipo_instrumento` (FUNDO, CONTA_MOVIMENTO, CDB,
POUPANCA, TESOURO — cadastrável) + tipo e atributos de liquidez em
`flc_fundo`. A tabela NÃO é renomeada — o tipo carrega a semântica.

⚠️ **Backfill comportamentalmente neutro**: todo fundo existente vira FUNDO
com liquidez 'S' — a migração não inventa classificação (todo registro
existente era fundo) e não muda número algum. Exceção única: o fundo GERAL,
criado pela MÁQUINA (migração 0006 / garantir_fundo_geral) com semântica
conhecida por construção ("saldo geral da conta"), vira CONTA_MOVIMENTO —
não é decisão humana fabricada.

⚠️ Os tipos são seedados AQUI (banco existente) e no `seed_dominio` (banco
novo) — idempotentes nos dois caminhos, nunca alterando existentes.

A view `vw_flc_saldo_fundo_fonte` é recriada expondo `ind_liquidez_imediata`:
o corte líquido × carência acontece no REPOSITÓRIO (uma view filtrada seria
uma segunda verdade para o mesmo saldo — a conciliação F9.4 precisa do
patrimônio cheio).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0038'
down_revision: Union[str, None] = '0037'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TIPOS_INSTRUMENTO = [
    ('FUNDO', 'Fundo de investimento'),
    ('CONTA_MOVIMENTO', 'Conta movimento'),
    ('CDB', 'Certificado de Depósito Bancário'),
    ('POUPANCA', 'Caderneta de poupança'),
    ('TESOURO', 'Título do Tesouro'),
]

VIEW_ANTIGA = """
CREATE VIEW vw_flc_saldo_fundo_fonte AS
SELECT s.seq_conta,
       s.seq_fundo,
       s.dat_saldo,
       s.val_saldo,
       f.seq_fonte_recurso,
       CASE WHEN f.seq_fonte_recurso IS NULL THEN 'P'
            WHEN fr.ind_vinculada = 'L' THEN 'L'
            ELSE 'V' END AS cod_grupo,
       ROW_NUMBER() OVER (
           PARTITION BY s.seq_conta, s.seq_fundo ORDER BY s.dat_saldo DESC
       ) AS num_ordem_recente
FROM flc_saldo_conta_fundo s
JOIN flc_fundo f ON f.seq_fundo = s.seq_fundo
LEFT JOIN flc_fonte_recurso fr ON fr.seq_fonte_recurso = f.seq_fonte_recurso
WHERE s.ind_status = 'A'
"""

# Igual à antiga + ind_liquidez_imediata do fundo (SQL portável
# SQLite/PostgreSQL — sem função específica de dialeto).
VIEW_NOVA = """
CREATE VIEW vw_flc_saldo_fundo_fonte AS
SELECT s.seq_conta,
       s.seq_fundo,
       s.dat_saldo,
       s.val_saldo,
       f.seq_fonte_recurso,
       f.ind_liquidez_imediata,
       CASE WHEN f.seq_fonte_recurso IS NULL THEN 'P'
            WHEN fr.ind_vinculada = 'L' THEN 'L'
            ELSE 'V' END AS cod_grupo,
       ROW_NUMBER() OVER (
           PARTITION BY s.seq_conta, s.seq_fundo ORDER BY s.dat_saldo DESC
       ) AS num_ordem_recente
FROM flc_saldo_conta_fundo s
JOIN flc_fundo f ON f.seq_fundo = s.seq_fundo
LEFT JOIN flc_fonte_recurso fr ON fr.seq_fonte_recurso = f.seq_fonte_recurso
WHERE s.ind_status = 'A'
"""


def upgrade() -> None:
    # A view referencia flc_fundo e impediria o rebuild em batch do SQLite
    # ("error in view ... no such table") — cai ANTES de mexer na tabela e
    # volta, já na forma nova, no fim.
    op.execute("DROP VIEW vw_flc_saldo_fundo_fonte")

    op.create_table(
        'flc_tipo_instrumento',
        sa.Column('seq_tipo_instrumento', sa.Integer(), nullable=False),
        sa.Column('txt_sigla', sa.String(length=20), nullable=False),
        sa.Column('dsc_tipo_instrumento', sa.String(length=120), nullable=True),
        sa.Column('ind_status', sa.String(length=1), nullable=False),
        sa.Column('dat_inclusao', sa.Date(), nullable=False),
        sa.Column('cod_pessoa_inclusao', sa.Integer(), nullable=True),
        sa.Column('dat_alteracao', sa.Date(), nullable=True),
        sa.Column('cod_pessoa_alteracao', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint(
            'seq_tipo_instrumento', name=op.f('pk_flc_tipo_instrumento')),
        sa.UniqueConstraint(
            'txt_sigla', name=op.f('uq_flc_tipo_instrumento_txt_sigla')),
    )

    # Seed dos tipos NA migração: banco existente os ganha aqui; banco novo,
    # pelo seed_dominio (os dois idempotentes). CURRENT_DATE como na 0006.
    for sigla, dsc in TIPOS_INSTRUMENTO:
        op.execute(sa.text(
            "INSERT INTO flc_tipo_instrumento "
            "(txt_sigla, dsc_tipo_instrumento, ind_status, dat_inclusao) "
            "VALUES (:sigla, :dsc, 'A', CURRENT_DATE)"
        ).bindparams(sigla=sigla, dsc=dsc))

    with op.batch_alter_table('flc_fundo') as batch:
        batch.add_column(sa.Column('seq_tipo_instrumento', sa.Integer(),
                                   nullable=True))
        batch.add_column(sa.Column('ind_liquidez_imediata', sa.String(length=1),
                                   nullable=False, server_default='S'))
        batch.add_column(sa.Column('dat_vencimento', sa.Date(), nullable=True))

    # Backfill: tudo era fundo; só o GERAL (criado pela máquina) é conta
    # movimento. Liquidez 'S' em todos (server_default) — nenhum número muda.
    op.execute("""
        UPDATE flc_fundo SET seq_tipo_instrumento = (
            SELECT seq_tipo_instrumento FROM flc_tipo_instrumento
             WHERE txt_sigla = CASE WHEN flc_fundo.cod_fundo = 'GERAL'
                                    THEN 'CONTA_MOVIMENTO' ELSE 'FUNDO' END
        )
    """)

    with op.batch_alter_table('flc_fundo') as batch:
        batch.alter_column('seq_tipo_instrumento',
                           existing_type=sa.Integer(), nullable=False)
        batch.create_foreign_key(
            'fk_flc_fundo_seq_tipo_instrumento_flc_tipo_instrumento',
            'flc_tipo_instrumento',
            ['seq_tipo_instrumento'], ['seq_tipo_instrumento'],
        )

    op.execute(VIEW_NOVA)


def downgrade() -> None:
    # ⚠️ Perda declarada: classificações de tipo, liquidez e vencimentos
    # somem; a disponibilidade volta a somar tudo como líquido.
    op.execute("DROP VIEW vw_flc_saldo_fundo_fonte")

    with op.batch_alter_table('flc_fundo') as batch:
        batch.drop_constraint(
            'fk_flc_fundo_seq_tipo_instrumento_flc_tipo_instrumento',
            type_='foreignkey')
        batch.drop_column('dat_vencimento')
        batch.drop_column('ind_liquidez_imediata')
        batch.drop_column('seq_tipo_instrumento')

    op.drop_table('flc_tipo_instrumento')
    op.execute(VIEW_ANTIGA)
