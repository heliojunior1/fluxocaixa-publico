# Scripts legados (referência histórica — não executar)

O schema agora é gerenciado por **Alembic** (`alembic/` na raiz; ver README do projeto).

- `migrate_projecao_historico.sql` — absorvido pela revisão baseline `0001` do Alembic.
- `migrate_formulas_loa.sql` — dados, não schema: os parâmetros globais foram absorvidos
  pelo seed de domínio (`src/fluxocaixa/services/seed_dominio.py`) e as fórmulas pelo
  seed de demonstração (`src/fluxocaixa/services/seed.py`).
