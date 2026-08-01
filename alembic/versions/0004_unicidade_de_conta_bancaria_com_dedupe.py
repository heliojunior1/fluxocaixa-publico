"""unicidade de conta bancaria com dedupe

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-12 09:33:36.322352

Instalações legadas podem ter contas duplicadas (banco, agência, conta)
criadas pela importação de lançamentos. Antes de criar a constraint:
mantém a conta de menor seq_conta de cada grupo, reaponta lançamentos e
saldos para ela e remove as demais. O dedupe não é reversível (o downgrade
remove apenas a constraint).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0004'
down_revision: Union[str, None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _deduplicar_contas() -> None:
    conn = op.get_bind()
    duplicatas = conn.execute(
        sa.text(
            """
            SELECT cod_banco, num_agencia, num_conta, MIN(seq_conta) AS manter
            FROM flc_conta_bancaria
            GROUP BY cod_banco, num_agencia, num_conta
            HAVING COUNT(*) > 1
            """
        )
    ).fetchall()

    for cod_banco, num_agencia, num_conta, manter in duplicatas:
        remover = [
            linha[0]
            for linha in conn.execute(
                sa.text(
                    """
                    SELECT seq_conta FROM flc_conta_bancaria
                    WHERE cod_banco = :b AND num_agencia = :a AND num_conta = :c
                      AND seq_conta <> :manter
                    """
                ),
                {"b": cod_banco, "a": num_agencia, "c": num_conta, "manter": manter},
            )
        ]
        for seq in remover:
            conn.execute(
                sa.text("UPDATE flc_lancamento SET seq_conta = :manter WHERE seq_conta = :seq"),
                {"manter": manter, "seq": seq},
            )
            # Saldos: reaponta, exceto quando a conta mantida já tem saldo na
            # mesma data (colisão) — nesse caso a linha da duplicada é removida.
            conn.execute(
                sa.text(
                    """
                    DELETE FROM flc_saldo_conta
                    WHERE seq_conta = :seq
                      AND dat_saldo IN (
                        SELECT dat_saldo FROM flc_saldo_conta WHERE seq_conta = :manter
                      )
                    """
                ),
                {"manter": manter, "seq": seq},
            )
            conn.execute(
                sa.text("UPDATE flc_saldo_conta SET seq_conta = :manter WHERE seq_conta = :seq"),
                {"manter": manter, "seq": seq},
            )
            conn.execute(
                sa.text("DELETE FROM flc_conta_bancaria WHERE seq_conta = :seq"),
                {"seq": seq},
            )


def upgrade() -> None:
    _deduplicar_contas()
    with op.batch_alter_table('flc_conta_bancaria', schema=None) as batch_op:
        batch_op.create_unique_constraint(batch_op.f('uq_flc_conta_bancaria_cod_banco'), ['cod_banco', 'num_agencia', 'num_conta'])


def downgrade() -> None:
    # O dedupe não é revertido — apenas a constraint é removida.
    with op.batch_alter_table('flc_conta_bancaria', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('uq_flc_conta_bancaria_cod_banco'), type_='unique')
