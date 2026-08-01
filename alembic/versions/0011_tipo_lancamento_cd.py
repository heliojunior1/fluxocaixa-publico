"""converge tipo de lancamento para C/D com valor sempre positivo

Revision ID: 0011
Revises: 0010
Create Date: 2026-07-21 10:12:03.551204

Transformação de dados do usuário (spec cadastros-nucleo R9): `flc_lancamento`
passa a guardar o valor SEMPRE POSITIVO e o sinal do fluxo de caixa vai para o
tipo, que vira `CHAR(1)` — 'C' (crédito/receita) e 'D' (débito/despesa). A
tabela de domínio e a FK são preservadas; as descrições continuam "Entrada" e
"Saída" (convergiu o código, não o vocabulário da tesouraria).

⚠️ O tipo novo é derivado do **SINAL do valor**, não do rótulo do tipo antigo:

    cod_tipo = CASE WHEN val_lancamento < 0 THEN 'D' ELSE 'C' END
    val_lancamento = ABS(val_lancamento)

É isso que torna a migração provadamente número-preservante para QUALQUER dado.
Nada impedia, no modelo antigo, uma receita negativa (estorno) ou uma despesa
positiva (origem mal configurada) — a validação só exigia valor != 0. Nessas
linhas o RÓTULO do tipo é corrigido e o VALOR é preservado; um estorno de
receita vira 'D', que é a semântica correta de partida dobrada (reversão de
crédito é débito). A auditoria `services/auditoria_sinal_service.py` mede
quantas linhas são essas antes de migrar.

O downgrade reconstrói pelo mesmo critério (tipo 'D' volta a valor negativo).
Linhas cujo rótulo original divergia do sinal NÃO recuperam o rótulo antigo —
o que sobrevive é o sinal, que é a informação numérica. Perda documentada.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0011'
down_revision: Union[str, None] = '0010'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_FK_TIPO = 'fk_flc_lancamento_cod_tipo_lancamento_flc_tipo_lancamento'


def upgrade() -> None:
    conn = op.get_bind()

    # 1) Coluna temporária + derivação do tipo a partir do SINAL. Precisa vir
    #    ANTES do ABS — depois dele o sinal não existe mais.
    with op.batch_alter_table('flc_lancamento') as batch:
        batch.add_column(sa.Column('cod_tipo_novo', sa.String(length=1), nullable=True))

    conn.execute(sa.text(
        "UPDATE flc_lancamento "
        "SET cod_tipo_novo = CASE WHEN val_lancamento < 0 THEN 'D' ELSE 'C' END"
    ))
    conn.execute(sa.text(
        "UPDATE flc_lancamento SET val_lancamento = ABS(val_lancamento)"
    ))

    # 2) Troca a coluna do tipo (derruba a FK antiga junto).
    with op.batch_alter_table('flc_lancamento') as batch:
        batch.drop_constraint(_FK_TIPO, type_='foreignkey')
        batch.drop_column('cod_tipo_lancamento')
        batch.alter_column('cod_tipo_novo', new_column_name='cod_tipo_lancamento',
                           existing_type=sa.String(length=1), nullable=False)

    # 3) Recria o domínio com PK textual e semeia os dois códigos.
    op.drop_table('flc_tipo_lancamento')
    op.create_table(
        'flc_tipo_lancamento',
        sa.Column('cod_tipo_lancamento', sa.String(length=1), nullable=False),
        sa.Column('dsc_tipo_lancamento', sa.String(length=50), nullable=False),
        sa.PrimaryKeyConstraint('cod_tipo_lancamento', name='pk_flc_tipo_lancamento'),
    )
    conn.execute(sa.text(
        "INSERT INTO flc_tipo_lancamento (cod_tipo_lancamento, dsc_tipo_lancamento) "
        "VALUES ('C', 'Entrada'), ('D', 'Saída')"
    ))

    # 4) Restaura a integridade referencial.
    with op.batch_alter_table('flc_lancamento') as batch:
        batch.create_foreign_key(_FK_TIPO, 'flc_tipo_lancamento',
                                 ['cod_tipo_lancamento'], ['cod_tipo_lancamento'])


def downgrade() -> None:
    conn = op.get_bind()

    with op.batch_alter_table('flc_lancamento') as batch:
        batch.add_column(sa.Column('cod_tipo_antigo', sa.Integer(), nullable=True))

    # Sinal de volta ao valor; rótulo reconstruído pelo tipo (1=Entrada, 2=Saída)
    conn.execute(sa.text(
        "UPDATE flc_lancamento SET val_lancamento = -val_lancamento "
        "WHERE cod_tipo_lancamento = 'D'"
    ))
    conn.execute(sa.text(
        "UPDATE flc_lancamento "
        "SET cod_tipo_antigo = CASE WHEN cod_tipo_lancamento = 'D' THEN 2 ELSE 1 END"
    ))

    with op.batch_alter_table('flc_lancamento') as batch:
        batch.drop_constraint(_FK_TIPO, type_='foreignkey')
        batch.drop_column('cod_tipo_lancamento')
        batch.alter_column('cod_tipo_antigo', new_column_name='cod_tipo_lancamento',
                           existing_type=sa.Integer(), nullable=False)

    op.drop_table('flc_tipo_lancamento')
    op.create_table(
        'flc_tipo_lancamento',
        sa.Column('cod_tipo_lancamento', sa.Integer(), nullable=False),
        sa.Column('dsc_tipo_lancamento', sa.String(length=50), nullable=False),
        sa.PrimaryKeyConstraint('cod_tipo_lancamento', name='pk_flc_tipo_lancamento'),
    )
    conn.execute(sa.text(
        "INSERT INTO flc_tipo_lancamento (cod_tipo_lancamento, dsc_tipo_lancamento) "
        "VALUES (1, 'Entrada'), (2, 'Saída')"
    ))

    with op.batch_alter_table('flc_lancamento') as batch:
        batch.create_foreign_key(_FK_TIPO, 'flc_tipo_lancamento',
                                 ['cod_tipo_lancamento'], ['cod_tipo_lancamento'])
