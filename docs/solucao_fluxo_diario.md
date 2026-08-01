# Solução — Fluxo Diário / Fluxo Mensal (módulo de Desembolso)

## 1. A demanda

Dentro da opção **Previsão**, criar duas novas opções: **FLUXO DIÁRIO** e **FLUXO MENSAL**
— uma previsão diária simples, com categorias resumidas e valores registrados, para
responder perguntas como:

> "Se eu liberar X de pagamentos hoje, como fica o fluxo no final do dia?"

Hoje isso é feito numa planilha Excel com a estrutura:

```
SALDO EM CONTA E RECEITAS          OBRIGAÇÕES
  Saldo conta principal              Pagamentos do dia (pagar hoje)
  Arrecadação dia anterior           Órgão de controle
  Saldo conta de aplicação           Repasse a municípios (pagar dia 21)
  ...                                Fundo da educação (pagar dia 21)
  TOTAL (A)                          TOTAL (B)

SALDO DEPOIS DAS OBRIGAÇÕES = A − B
```

## 2. Referência: módulo de Desembolso

Implementações de referência costumam ter um **módulo de Desembolso** cujo conceito central é
a separação entre **Liberação** e **Pagamento**:

| Conceito | O que é |
|---|---|
| **Liberação** | Cota/autorização de gasto, por órgão ou tipo de saída (custeio, investimento, encargos...), com data e valor. Liberar **compromete** o caixa antes de pagar. |
| **Pagamento** | O desembolso executado, em grade diária por órgão → tipo, com origem marcada (carga automática ou inserção manual). |
| **Saldo comprometido** | `liberações − pagamentos` — autorizado e ainda não desembolsado. Métrica-chave do dashboard. |
| **Conferência** | Fechamento diário: `saldo anterior + liberações − pagamentos = saldo`, com colunas de valores *conferidos* contra o banco (bate/não bate). |
| **Disponibilidade de caixa** | Rotina diária: manhã, saldos iniciais das contas; início da tarde, liberações/pagamentos/receitas do dia; em seguida, disponibilidade atualizada. É exatamente a planilha da demanda. |

**Insight principal**: a demanda não é uma feature isolada — é a **visão de
disponibilidade de caixa** que emerge naturalmente quando o sistema tem liberações,
pagamentos e saldos integrados.

## 3. O que o sistema já tem

| Conceito da referência | No FluxoDeCaixa hoje | Situação |
|---|---|---|
| Pagamentos por órgão/data | `flc_pagamento` (data, órgão, qualificador, valor, descrição) | Existe, mas cru: só listar/incluir; sem status, sem editar/excluir, sem soft delete, sem auditoria |
| Conferência diária | `flc_conferencia` (mesmas colunas, coluna a coluna) | Existe, mas **só leitura** — alimentada por seed, sem caminho de escrita |
| Cargas automáticas | Framework de **Extração** (F3: FTP, API REST, banco SQL) + staging/regras (F4) | Existe e é mais genérico que o da referência |
| Órgão | `flc_orgao` | Existe |
| Saldos iniciais das contas | `vw_flc_saldo_conta_agregado` (F2) | Existe |
| Arrecadação do dia anterior | `flc_lancamento` (créditos de D-1, via `valor_com_sinal`) | Existe |
| **Liberação / saldo comprometido** | — | **Não existe. É a peça que falta.** |

## 4. Decisão de desenho

### O que NÃO fazer

- **Não encaixar no motor de simulação de cenários** (`flc_simulador_cenario`): ele opera
  por qualificador folha, com periodicidades mensal/quinzenal/semanal/anual, modelos
  econométricos e versões publicadas. A demanda é grão **diário**, categorias
  **resumidas** e valores digitados/compostos na hora. Forçar traria complexidade que o
  pedido ("mais simples") explicitamente dispensa.
- **Não criar uma planilha 100% manual**: o sistema já conhece saldos, pagamentos e
  arrecadação — digitar de novo seria duplicação e divergiria do dado oficial.

### O que fazer

O Fluxo Diário é uma **composição sobre dados existentes** + o conceito novo de Liberação
+ linhas manuais para o que o sistema não conhece. Totais e saldos **nunca persistidos**
— sempre derivados na leitura (mesmo princípio do saldo agregado da F2.1).

## 5. Solução em fases

### Fase 1 — Liberações (a peça que falta)

- Nova tabela **`flc_liberacao`**: espelho da `flc_pagamento` (data, órgão,
  qualificador/tipo de saída, valor, descrição) + status + soft delete (`ind_status`) +
  auditoria (`dat_inclusao`/`cod_pessoa_inclusao`/...).
- **Status** em liberação e pagamento (ex.: `P` pendente / `L` liberado / `E` efetuado)
  — é o que dá sentido ao verbo "liberar".
- **Upgrade da `flc_pagamento`** (necessário de qualquer forma): editar/excluir,
  soft delete, auditoria, status.
- **Saldo comprometido** = liberado − pago, valor derivado (service/repository, nunca
  persistido).
- CRUD no padrão da casa: migração Alembic, service com `RegraNegocioError`,
  permissões `FC_CONS_LIBERACAO`/`FC_MANT_LIBERACAO` no catálogo, BDD.

### Fase 2 — Fluxo Diário (a demanda)

Tela de disponibilidade do dia, sob o menu Previsão (o menu do Simulador vira hub:
**Cenários** | **Fluxo Diário** | **Fluxo Mensal**):

- **Bloco SALDOS/RECEITAS** (pré-preenchido, editável por cima):
  - Saldos por conta ← `vw_flc_saldo_conta_agregado`
  - Arrecadação D-1 ← lançamentos de crédito (via `valor_com_sinal`)
- **Bloco OBRIGAÇÕES** (alimentado automaticamente):
  - Pagamentos/liberações com data = hoje → "pagar hoje"
  - Data futura → etiqueta com a data (o "pagar dia 21" da planilha é o
    `dat_pagamento` que já existe no modelo)
- **Linhas manuais** para o que não estiver cadastrado: tabela leve
  `flc_fluxo_dia_item` (data, descrição, bloco `E`/`O`, valor, observação).
- **Simulação "e se"**: marcar/desmarcar liberações e pagamentos pendentes na tela e
  ver o "saldo depois das obrigações" recalcular **em JS, sem submit** — só grava ao
  salvar.
- **"Criar dia a partir de ontem"**: clona as linhas manuais do último dia registrado
  (replica o hábito do Excel e elimina a maior parte da digitação).
- Total do dia e saldo final: **sempre derivados**, nunca gravados.

### Fase 3 — Conferência viva

- `flc_conferencia` ganha caminho de escrita e passa a ser **derivada** de
  liberações + pagamentos do dia.
- Valores *conferidos* vêm da extração (saldo bancário via F3), com indicação visual
  de bate/não bate.
- Fecha o ciclo **previsto (Fluxo Diário) × realizado (Conferência)**.

### Fase 4 — Fluxo Mensal e visões em grade

- Grade semanal/mensal de liberações e pagamentos (colunas por dia + coluna PREVISTO).
- Sai quase de graça dos dados das fases 1–2 (mesmas tabelas, agregação por período —
  reusar `periodo_resolver` da F6.3 se precisar de quinzena/semana).
- Evolução futura: blocos de dashboard (liberações × tipo, pagamentos × órgão,
  variação do saldo comprometido) com Chart.js, que já está no projeto.

## 6. Reorganização do menu lateral

Hoje o menu (`base.html`) tem três seções — **Principal** (Dashboard, Relatórios),
**Gestão** (Lançamentos, Saldos Bancários, Fundos, Extração, Execuções, Simulador, LOA,
Pagamentos, Conferência) e **Configurações** — e a seção Gestão virou um "balaio": mistura
operação de caixa, desembolso e previsão. Com a entrada do módulo de Desembolso, o menu
passa a refletir os módulos do sistema:

| Seção | Itens | Observação |
|---|---|---|
| **Principal** | Dashboard | Mantido como está (nome e posição) |
| **Gestão** | Relatórios · Previsão (Cenários, Fluxo Diário, Fluxo Mensal) · LOA | Visões analíticas e de planejamento |
| **Fluxo de Caixa** | Lançamentos · Saldos Bancários · Fundos · Extração · Execuções | A operação do caixa: registro, saldos e cargas automáticas |
| **Módulo de Desembolso** | Pagamentos · Liberações · Conferência | O módulo novo desta solução (Fases 1 e 3) |
| **Configurações** | Fórmulas · Parâmetros · Mapeamentos · Termos de Regra · Qualificadores · Alertas | Sem mudança |

Notas de desenho:

- **Conferência migra de Gestão para Módulo de Desembolso**: na referência ela é uma
  tela do desembolso (é o fechamento de liberações × pagamentos), e a Fase 3 a torna
  derivada dessas entidades — o agrupamento acompanha a semântica.
- **Previsão fica em Gestão** com seus três subitens (Cenários = simulador atual,
  Fluxo Diário, Fluxo Mensal), honrando a demanda original ("criar na opção de
  Previsão"). O Fluxo Diário *lê* dados do Desembolso, mas é uma visão de previsão —
  quem procura "como fecha o dia" procura previsão, não cadastro.
- A mudança é só de **agrupamento e rótulo** no `base.html` — nenhuma rota ou permissão
  muda; os `tem_permissao(...)` existentes continuam decidindo a visibilidade de cada
  item, e uma seção sem nenhum item visível não deve exibir o título.

## 7. Integração com a extração (futuro)

O framework de extração cobre o papel das cargas automáticas da referência: uma fonte
`BANCO_SQL` ou `API_REST` pode alimentar pagamentos/liberações automaticamente, no
mesmo desenho que a F4 fez para lançamentos (novo `cod_destino`, staging, marcação de
origem automática × manual). Fora do escopo das fases 1–2, mas o desenho não fecha
essa porta.

## 8. Questões em aberto (confirmar com o solicitante)

1. **Fluxo Mensal**: é a mesma folha com grão mês, ou a **consolidação** dos dias do
   mês? (Assumido: grade agregada dos mesmos dados — Fase 4.)
2. **Os pagamentos da planilha serão cadastrados na tela de Pagamentos?** O desenho
   assume que sim (zero digitação duplicada). Se a tela de Pagamentos não for usada,
   as linhas manuais do Fluxo Diário cobrem tudo, e a integração vira opcional.
3. **Tipos de saída** (custeio, investimento, encargos...): modelar como
   qualificadores ou como domínio próprio? (Tendência: domínio próprio pequeno, como
   categoria fiscal.)
4. **Contas fixas do bloco de saldos**: quais contas do cadastro correspondem a cada
   linha da planilha? Precisa de marcação parametrizável (qual conta aparece no resumo
   diário), não de hardcode.

## 9. Convenções a seguir na implementação

- Prefixo `flc_`, PK `seq_*`, `NUMERIC(18,2)`, `ind_status` + auditoria.
- Schema via Alembic (nunca `create_all`); valores derivados nunca persistidos.
- Regras de negócio em services com `RegraNegocioError` (nunca 500).
- Toda rota com `dependencies=[requer('FC_...')]` + catálogo + teste de completude.
- Repositório é público: sem citar a organização de origem, sem valores/contas reais —
  fixtures e exemplos só com dados claramente fictícios.
