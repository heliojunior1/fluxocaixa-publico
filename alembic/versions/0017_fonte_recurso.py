"""catalogo de fontes de recurso e classificacao dos fundos

Revision ID: 0017
Revises: 0016
Create Date: 2026-08-02 08:30:00.000000

Spec `fonte-recurso` R1–R6 e `saldo-por-fundo` R21 (change
fonte-recurso-catalogo). Cria o catálogo STN decomposto/versionado, a ponte
fundo→fonte e a view de saldo por grupo de disponibilidade.

⚠️ **Sem backfill, e isso é deliberado**: todos os fundos nascem sem fonte
(pendentes de classificação) e ficam FORA do grupo livre até que alguém os
classifique. Errar para baixo na disponibilidade é prudência; adivinhar a
fonte de um fundo seria fabricar disponibilidade livre.

A unicidade composta do catálogo (vigência, identificador, fonte,
detalhamento) vale ENTRE ATIVOS e é validada no serviço — uma constraint de
banco impediria a convivência com inativas (mesmo padrão da unicidade de
mapeamentos).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0017'
down_revision: Union[str, None] = '0016'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Saldo ativo por (conta, fundo, dia) com o GRUPO de disponibilidade da fonte
# do fundo: 'L' livre, 'V' vinculado, 'P' pendente (fundo sem fonte — fora do
# livre, conservador). num_ordem_recente = 1 marca a linha mais recente de
# cada (conta, fundo) — é ela que compõe o saldo bruto atual do grupo.
# ⚠️ A view entrega o saldo BRUTO: reservas/bloqueios (F7.4) NÃO são
# embutidos aqui — a subtração deles acontece uma única vez, na leitura da
# disponibilidade operacional (doc do módulo, seção 4.4).
VIEW_FUNDO_FONTE = """
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


def upgrade() -> None:
    op.create_table(
        'flc_fonte_recurso',
        sa.Column('seq_fonte_recurso', sa.Integer(), nullable=False),
        # '1' corrente | '2' exercícios anteriores | '9' condicionados
        sa.Column('cod_identificador_exercicio', sa.String(length=1), nullable=False),
        sa.Column('cod_fonte_stn', sa.String(length=3), nullable=False),
        sa.Column('cod_detalhamento', sa.String(length=10), nullable=True),
        sa.Column('num_exercicio_vigencia', sa.Integer(), nullable=False),
        sa.Column('dsc_fonte_recurso', sa.String(length=200), nullable=False),
        # 'L' livre | 'V' vinculada — explícita, nunca derivada do código
        sa.Column('ind_vinculada', sa.String(length=1), nullable=False),
        # 'STN' tabela oficial | 'LOCAL' criada pelo ente
        sa.Column('cod_origem_classificacao', sa.String(length=5), nullable=False),
        sa.Column('dsc_grupo_destinacao', sa.String(length=60), nullable=True),
        sa.Column('ind_pendente_revisao', sa.String(length=1), nullable=False),
        sa.Column('ind_status', sa.String(length=1), nullable=False),
        sa.Column('dat_inclusao', sa.Date(), nullable=False),
        sa.Column('cod_pessoa_inclusao', sa.Integer(), nullable=True),
        sa.Column('dat_alteracao', sa.Date(), nullable=True),
        sa.Column('cod_pessoa_alteracao', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('seq_fonte_recurso', name=op.f('pk_flc_fonte_recurso')),
    )

    # A FK nasce NULA em todos os fundos — ver o aviso no cabeçalho.
    with op.batch_alter_table('flc_fundo') as batch:
        batch.add_column(sa.Column('seq_fonte_recurso', sa.Integer(), nullable=True))
        batch.create_foreign_key(
            'fk_flc_fundo_seq_fonte_recurso_flc_fonte_recurso',
            'flc_fonte_recurso', ['seq_fonte_recurso'], ['seq_fonte_recurso'],
        )

    op.execute(VIEW_FUNDO_FONTE)


def downgrade() -> None:
    # ⚠️ Perda declarada: as classificações fundo→fonte feitas pelo usuário
    # somem, e toda leitura de disponibilidade volta ao agregado bruto.
    op.execute("DROP VIEW vw_flc_saldo_fundo_fonte")

    with op.batch_alter_table('flc_fundo') as batch:
        batch.drop_constraint(
            'fk_flc_fundo_seq_fonte_recurso_flc_fonte_recurso', type_='foreignkey')
        batch.drop_column('seq_fonte_recurso')

    op.drop_table('flc_fonte_recurso')
