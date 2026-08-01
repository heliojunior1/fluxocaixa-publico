"""alarga num_qualificador para comportar 6 niveis

Revision ID: 0014
Revises: 0013
Create Date: 2026-07-28 09:14:02.551180

Spec `cadastros-nucleo` R12: a hierarquia deve suportar 6 níveis, e o código
dotted precisa caber:

    1.1.1.1.1.1              11  ✓ cabia
    1.12.34.56.78.90         16  ✓ cabia
    1.100.200.300.400.500    21  ✗ NÃO cabia em String(20)

⚠️ Por que isto passou despercebido até agora: **SQLite não impõe tamanho de
VARCHAR** — grava a string inteira e não reclama. PostgreSQL impõe. O bug passa
em dev e aparece só em produção, e o projeto suporta os dois bancos. É o mesmo
motivo pelo qual o teste de BDD afere a CAPACIDADE DECLARADA da coluna em vez
do round-trip do valor: o round-trip passa em SQLite mesmo com a coluna curta.

`String(60)` dá folga para 6 níveis com segmentos de até 4 dígitos sem
transformar o campo em texto livre.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0014'
down_revision: Union[str, None] = '0013'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('flc_qualificador') as batch:
        batch.alter_column('num_qualificador',
                           existing_type=sa.String(20), type_=sa.String(60),
                           existing_nullable=False)


def downgrade() -> None:
    # ⚠️ Estreitar TRUNCA códigos já gravados com mais de 20 caracteres —
    # exatamente os de 6 níveis que a 0014 veio permitir. Em PostgreSQL o
    # ALTER falha com dado longo presente (e essa recusa é preferível a uma
    # truncagem silenciosa); em SQLite o valor sobrevive ao round-trip porque
    # o tamanho nunca foi imposto.
    with op.batch_alter_table('flc_qualificador') as batch:
        batch.alter_column('num_qualificador',
                           existing_type=sa.String(60), type_=sa.String(20),
                           existing_nullable=False)
