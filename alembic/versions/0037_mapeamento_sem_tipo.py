"""aposenta a dimensão receita/despesa do mapeamento (automacao R6)

O `ind_tipo` (1=Receita/2=Despesa) era resquício do layout antigo da origem
e não governava mais nada: a classificação vem do QUALIFICADOR do item e a
direção do movimento vem do SINAL do valor (F4.3). A unicidade passa a
(ano, sistema de origem); os pares legados são FUNDIDOS preservando as PKs
dos itens e seus `dat_ultima_execucao` (recriar itens marcaria tudo sujo →
recarga total, proibida pela F4.2b).

⚠️ COLISÃO ABORTA: se o MESMO qualificador tiver item ativo nos dois lados
de um par, esta migração para com relatório — regra de classificação é
configuração de negócio, e fusão que escolhe sozinha é o erro silencioso
que este projeto remove. Ajuste os cadastros e rode de novo.

Downgrade PARCIAL documentado: a coluna volta (default '1'); a fusão não se
desfaz (mesma classe de perda das migrações 0006/0013/0033).

Revision ID: 0037
Revises: 0036
"""
import sqlalchemy as sa
from alembic import op

revision = '0037'
down_revision = '0036'
branch_labels = None
depends_on = None


def colisoes_da_fusao(itens_por_mapeamento: dict) -> list:
    """FUNÇÃO PURA (unit-testada): detecta qualificadores presentes em mais
    de um mapeamento do mesmo par.

    `itens_por_mapeamento`: {seq_mapeamento: {seq_qualificador, ...}} dos
    mapeamentos ATIVOS de um mesmo (ano, sistema). Devolve a lista ordenada
    de seq_qualificador que aparecem em 2+ mapeamentos.
    """
    vistos: dict = {}
    colididos = set()
    for seq_mapeamento, qualificadores in itens_por_mapeamento.items():
        for seq_q in qualificadores:
            if seq_q in vistos and vistos[seq_q] != seq_mapeamento:
                colididos.add(seq_q)
            vistos.setdefault(seq_q, seq_mapeamento)
    return sorted(colididos)


def _fundir_pares(conn) -> None:
    pares = conn.execute(sa.text(
        """
        SELECT num_ano_exercicio, seq_sistema_origem
        FROM flc_mapeamento WHERE ind_status = 'A'
        GROUP BY num_ano_exercicio, seq_sistema_origem
        HAVING COUNT(*) > 1
        """
    )).fetchall()

    problemas = []
    fusoes = []
    for ano, sistema in pares:
        mapeamentos = conn.execute(sa.text(
            """
            SELECT seq_mapeamento FROM flc_mapeamento
            WHERE ind_status = 'A' AND num_ano_exercicio = :ano
              AND seq_sistema_origem = :sistema
            ORDER BY seq_mapeamento
            """
        ), {"ano": ano, "sistema": sistema}).fetchall()

        itens_por_mapeamento = {}
        for (seq_mapeamento,) in mapeamentos:
            itens = conn.execute(sa.text(
                """
                SELECT seq_qualificador FROM flc_item_mapeamento
                WHERE seq_mapeamento = :m AND ind_status = 'A'
                """
            ), {"m": seq_mapeamento}).fetchall()
            itens_por_mapeamento[seq_mapeamento] = {q for (q,) in itens}

        colididos = colisoes_da_fusao(itens_por_mapeamento)
        if colididos:
            problemas.append(
                f"(ano={ano}, sistema={sistema}): qualificadores "
                f"{colididos} têm item ativo em mais de um mapeamento")
            continue
        fusoes.append((ano, sistema, [m for (m,) in mapeamentos]))

    if problemas:
        raise RuntimeError(
            "Fusão de mapeamentos ABORTADA — o mesmo qualificador tem item "
            "ativo nos dois mapeamentos do par. Unifique ou ajuste os itens "
            "antes de migrar:\n  " + "\n  ".join(problemas))

    for ano, sistema, seqs in fusoes:
        destino, excedentes = seqs[0], seqs[1:]
        for origem in excedentes:
            # reaponta os itens PRESERVANDO PKs e dat_ultima_execucao
            conn.execute(sa.text(
                "UPDATE flc_item_mapeamento SET seq_mapeamento = :destino "
                "WHERE seq_mapeamento = :origem"
            ), {"destino": destino, "origem": origem})
            conn.execute(sa.text(
                "UPDATE flc_mapeamento SET ind_status = 'I' "
                "WHERE seq_mapeamento = :origem"
            ), {"origem": origem})


def upgrade():
    _fundir_pares(op.get_bind())
    op.drop_index('ix_flc_mapeamento_chave', table_name='flc_mapeamento')
    with op.batch_alter_table('flc_mapeamento') as batch:
        batch.drop_column('ind_tipo')
    op.create_index('ix_flc_mapeamento_chave', 'flc_mapeamento',
                    ['num_ano_exercicio', 'seq_sistema_origem'])


def downgrade():
    op.drop_index('ix_flc_mapeamento_chave', table_name='flc_mapeamento')
    with op.batch_alter_table('flc_mapeamento') as batch:
        batch.add_column(sa.Column('ind_tipo', sa.String(1), nullable=False,
                                   server_default='1'))
    op.create_index('ix_flc_mapeamento_chave', 'flc_mapeamento',
                    ['num_ano_exercicio', 'ind_tipo', 'seq_sistema_origem'])
    # a fusão NÃO se desfaz: itens reapontados permanecem no destino
