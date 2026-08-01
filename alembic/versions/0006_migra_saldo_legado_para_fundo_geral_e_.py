"""migra saldo legado para fundo GERAL e remove tabela

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-12 16:22:13.834537

Transformação de dados do usuário (spec saldo-por-fundo R17): cada linha de
`flc_saldo_conta` (conta × dia) vira um saldo em `flc_saldo_conta_fundo` sob o
fundo padrão `GERAL` (tipo MANUAL, aprovado — criado apenas se houver dados a
migrar), com aplicações/resgates zerados; a tabela legada é removida.

O downgrade recria a tabela legada e a repovoa a partir das linhas ativas do
fundo GERAL. Linhas de OUTROS fundos (criadas após o upgrade) não existem no
modelo antigo e são perdidas no downgrade — perda documentada.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0006'
down_revision: Union[str, None] = '0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    tem_dados = conn.execute(sa.text("SELECT COUNT(*) FROM flc_saldo_conta")).scalar()

    if tem_dados:
        # A migração roda no boot ANTES do seed de domínio; garante o tipo de
        # origem MANUAL que a própria transformação consome (idempotente — o
        # seed de domínio depois encontra a linha e não duplica).
        seq_tipo_manual = conn.execute(
            sa.text("SELECT seq_tipo_origem_saldo FROM flc_tipo_origem_saldo WHERE txt_sigla='MANUAL'")
        ).scalar()
        if seq_tipo_manual is None:
            conn.execute(
                sa.text(
                    "INSERT INTO flc_tipo_origem_saldo (txt_sigla, dsc_tipo_origem, "
                    "ind_status, dat_inclusao) VALUES ('MANUAL', "
                    "'Lançado manualmente pela tesouraria', 'A', CURRENT_DATE)"
                )
            )
            seq_tipo_manual = conn.execute(
                sa.text("SELECT seq_tipo_origem_saldo FROM flc_tipo_origem_saldo WHERE txt_sigla='MANUAL'")
            ).scalar()
        seq_geral = conn.execute(
            sa.text("SELECT seq_fundo FROM flc_fundo WHERE cod_fundo='GERAL'")
        ).scalar()
        if seq_geral is None:
            conn.execute(
                sa.text(
                    "INSERT INTO flc_fundo (cod_fundo, dsc_fundo, seq_tipo_origem, "
                    "ind_pendente_revisao, ind_status, dat_inclusao) "
                    "VALUES ('GERAL', 'Saldo geral da conta', :t, 'N', 'A', CURRENT_DATE)"
                ),
                {"t": seq_tipo_manual},
            )
            seq_geral = conn.execute(
                sa.text("SELECT seq_fundo FROM flc_fundo WHERE cod_fundo='GERAL'")
            ).scalar()

        # Migra cada saldo legado para o modelo novo sob o GERAL
        conn.execute(
            sa.text(
                "INSERT INTO flc_saldo_conta_fundo "
                "(seq_conta, seq_fundo, dat_saldo, val_saldo, val_aplicacoes, "
                " val_resgates, seq_tipo_origem, ind_status, dat_inclusao, cod_pessoa_inclusao) "
                "SELECT seq_conta, :geral, dat_saldo, val_saldo, 0, 0, :t, 'A', "
                "       dat_inclusao, cod_pessoa_inclusao "
                "FROM flc_saldo_conta"
            ),
            {"geral": seq_geral, "t": seq_tipo_manual},
        )

    op.drop_table('flc_saldo_conta')


def downgrade() -> None:
    op.create_table('flc_saldo_conta',
    sa.Column('seq_saldo_conta', sa.INTEGER(), nullable=False),
    sa.Column('seq_conta', sa.INTEGER(), nullable=False),
    sa.Column('dat_saldo', sa.DATE(), nullable=False),
    sa.Column('val_saldo', sa.NUMERIC(precision=18, scale=2), nullable=False),
    sa.Column('dat_inclusao', sa.DATE(), nullable=False),
    sa.Column('cod_pessoa_inclusao', sa.INTEGER(), nullable=False),
    sa.Column('dat_alteracao', sa.DATE(), nullable=True),
    sa.Column('cod_pessoa_alteracao', sa.INTEGER(), nullable=True),
    sa.ForeignKeyConstraint(['seq_conta'], ['flc_conta_bancaria.seq_conta'], name=op.f('fk_flc_saldo_conta_seq_conta_flc_conta_bancaria')),
    sa.PrimaryKeyConstraint('seq_saldo_conta', name=op.f('pk_flc_saldo_conta')),
    sa.UniqueConstraint('seq_conta', 'dat_saldo', name=op.f('uk_saldo_conta_data'))
    )
    # Repovoa a partir das linhas ativas do fundo GERAL (perda de outros fundos)
    conn = op.get_bind()
    seq_geral = conn.execute(
        sa.text("SELECT seq_fundo FROM flc_fundo WHERE cod_fundo='GERAL'")
    ).scalar()
    if seq_geral is not None:
        conn.execute(
            sa.text(
                "INSERT INTO flc_saldo_conta "
                "(seq_conta, dat_saldo, val_saldo, dat_inclusao, cod_pessoa_inclusao) "
                "SELECT seq_conta, dat_saldo, val_saldo, dat_inclusao, cod_pessoa_inclusao "
                "FROM flc_saldo_conta_fundo WHERE seq_fundo = :geral AND ind_status='A'"
            ),
            {"geral": seq_geral},
        )
