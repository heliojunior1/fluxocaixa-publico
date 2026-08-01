"""granularidade de periodo na projecao e rename de meses_projecao

Revision ID: 0013
Revises: 0012
Create Date: 2026-07-22 15:08:44.712905

Transformação de dados do usuário (spec previsao R10). A projeção passa a
registrar o PERÍODO da sua periodicidade — mês, quinzena ou semana ISO — no
lugar do mês:

    flc_projecao_valor.mes  ─→  flc_projecao_valor.num_periodo

⚠️ `mes` **sai** e não é substituído por uma coluna espelho: é função pura de
(periodicidade, ano, período) e passa a vir de `periodo_resolver.mes_do_periodo`
na leitura. Mesmo princípio da F2.1, onde o saldo agregado nunca é persistido.

⚠️ A conversão NÃO é um copiar de coluna:

    MENSAL → num_periodo = mes                 (1:1, exato)
    ANUAL  → num_periodo = 1, valor = SUM(mês) (os 12 registros COLAPSAM)

Um cenário ANUAL grava hoje 12 linhas mensais que são a **distribuição** de um
total anual; sob o modelo novo ANUAL tem UM período por ano. O colapso muda a
forma e **preserva o total** — a distribuição mensal deixa de estar gravada e
volta a ser recomposta na leitura pelo perfil histórico, que é onde a F5.2 já a
fazia. QUINZENAL e SEMANAL não têm dado a converter: nunca chegaram a ser
gravadas de verdade (o backend as tratava como MENSAL).

Também renomeia `flc_simulador_cenario.meses_projecao` → `num_periodos`: o
campo sempre guardou períodos, e a tela já gravava semanas nele.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0013'
down_revision: Union[str, None] = '0012'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    with op.batch_alter_table('flc_simulador_cenario') as batch:
        batch.alter_column('meses_projecao', new_column_name='num_periodos',
                           existing_type=sa.Integer(), existing_nullable=False)

    with op.batch_alter_table('flc_projecao_valor') as batch:
        batch.add_column(sa.Column('num_periodo', sa.Integer(), nullable=True))

    # MENSAL (e qualquer periodicidade de grão mensal): período = mês
    conn.execute(sa.text(
        "UPDATE flc_projecao_valor SET num_periodo = mes "
        "WHERE seq_projecao_versao IN ("
        "  SELECT v.seq_projecao_versao FROM flc_projecao_versao v "
        "  JOIN flc_simulador_cenario c "
        "    ON c.seq_simulador_cenario = v.seq_simulador_cenario "
        "  WHERE COALESCE(c.cod_periodicidade,'MENSAL') <> 'ANUAL')"
    ))

    # ANUAL: colapsa os registros do ano num período 1 com o total preservado
    conn.execute(sa.text(
        "INSERT INTO flc_projecao_valor "
        "(seq_projecao_versao, seq_qualificador, cod_tipo, ano, mes, "
        " num_periodo, val_projetado, val_realizado) "
        "SELECT pv.seq_projecao_versao, pv.seq_qualificador, pv.cod_tipo, pv.ano, "
        "       1, 1, SUM(pv.val_projetado), SUM(pv.val_realizado) "
        "FROM flc_projecao_valor pv "
        "JOIN flc_projecao_versao v ON v.seq_projecao_versao = pv.seq_projecao_versao "
        "JOIN flc_simulador_cenario c ON c.seq_simulador_cenario = v.seq_simulador_cenario "
        "WHERE c.cod_periodicidade = 'ANUAL' AND pv.num_periodo IS NULL "
        "GROUP BY pv.seq_projecao_versao, pv.seq_qualificador, pv.cod_tipo, pv.ano"
    ))
    conn.execute(sa.text(
        "DELETE FROM flc_projecao_valor WHERE num_periodo IS NULL"))

    # O índice tem o MESMO nome nas duas formas, mas indexa `mes` antes e
    # `num_periodo` depois. Ele precisa cair ANTES do drop da coluna: o batch
    # mode do SQLite recria a tabela reproduzindo os índices refletidos, e
    # recriaria este apontando para uma coluna que acabou de sumir.
    op.drop_index('ix_projecao_valor_versao_qual_periodo',
                  table_name='flc_projecao_valor')
    with op.batch_alter_table('flc_projecao_valor') as batch:
        batch.alter_column('num_periodo', existing_type=sa.Integer(), nullable=False)
        batch.drop_column('mes')
    op.create_index('ix_projecao_valor_versao_qual_periodo', 'flc_projecao_valor',
                    ['seq_projecao_versao', 'seq_qualificador', 'ano', 'num_periodo'])


def downgrade() -> None:
    conn = op.get_bind()

    with op.batch_alter_table('flc_projecao_valor') as batch:
        batch.add_column(sa.Column('mes', sa.Integer(), nullable=True))

    # Grão mensal volta 1:1; ANUAL reexpande o total em 12 meses iguais — a
    # distribuição original por perfil histórico não é recuperável (perda
    # documentada; o total do ano é preservado).
    conn.execute(sa.text(
        "UPDATE flc_projecao_valor SET mes = num_periodo "
        "WHERE seq_projecao_versao IN ("
        "  SELECT v.seq_projecao_versao FROM flc_projecao_versao v "
        "  JOIN flc_simulador_cenario c "
        "    ON c.seq_simulador_cenario = v.seq_simulador_cenario "
        "  WHERE COALESCE(c.cod_periodicidade,'MENSAL') = 'MENSAL')"
    ))
    for mes in range(1, 13):
        conn.execute(sa.text(
            "INSERT INTO flc_projecao_valor "
            "(seq_projecao_versao, seq_qualificador, cod_tipo, ano, mes, "
            " num_periodo, val_projetado, val_realizado) "
            "SELECT pv.seq_projecao_versao, pv.seq_qualificador, pv.cod_tipo, pv.ano, "
            f"      {mes}, pv.num_periodo, pv.val_projetado / 12.0, "
            "       pv.val_realizado / 12.0 "
            "FROM flc_projecao_valor pv "
            "JOIN flc_projecao_versao v ON v.seq_projecao_versao = pv.seq_projecao_versao "
            "JOIN flc_simulador_cenario c ON c.seq_simulador_cenario = v.seq_simulador_cenario "
            "WHERE c.cod_periodicidade = 'ANUAL' AND pv.mes IS NULL"
        ))
    conn.execute(sa.text("DELETE FROM flc_projecao_valor WHERE mes IS NULL"))

    op.drop_index('ix_projecao_valor_versao_qual_periodo',
                  table_name='flc_projecao_valor')
    with op.batch_alter_table('flc_projecao_valor') as batch:
        batch.alter_column('mes', existing_type=sa.Integer(), nullable=False)
        batch.drop_column('num_periodo')
    op.create_index('ix_projecao_valor_versao_qual_periodo', 'flc_projecao_valor',
                    ['seq_projecao_versao', 'seq_qualificador', 'ano', 'mes'])

    with op.batch_alter_table('flc_simulador_cenario') as batch:
        batch.alter_column('num_periodos', new_column_name='meses_projecao',
                           existing_type=sa.Integer(), existing_nullable=False)
