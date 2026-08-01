# language: pt
Funcionalidade: DFC com estratégia Projetado
  Estratégia REALIZADO|PROJETADO no DFC (spec relatorios R9–R13): mês fechado
  sempre realizado; mês aberto recebe a projeção do cenário — da última versão
  publicada quando existir, senão cálculo ao vivo sinalizado. Cenário ANUAL é
  redistribuído pelo perfil mensal histórico do ano-base (sem histórico, 1/12)
  excluindo qualificadores inativos da base. Projeção agregada vira linha
  sintética sob a raiz do tipo.

  # Isolamento: anos 2034+ para projeção (ilhas 2031–2033 são dos KPIs e o
  # seed demo vive em 2022–2026); cada cenário usa qualificadores próprios.
  # Ataque na camada de serviço (get_dfc_data / get_dfc_eventos); a página é
  # coberta pelo E2E.

  # ------------------------------------------------------------------ R9

  Cenário: Estratégia default é realizado, sem células projetadas
    Dado um qualificador folha de receita "1.93.1" com lançamento de "150.00" em "2034-05-10"
    Quando consulto o DFC de "2034" na visão anual com estratégia "realizado"
    Então nenhuma célula do DFC está marcada como projetada
    E o DFC não informa origem de projeção

  Cenário: Projetado sem cenário é rejeitado
    Quando consulto o DFC projetado de "2034" sem cenário
    Então recebo erro de negócio do DFC mencionando "cenário"

  Cenário: Mês fechado ignora a projeção
    # Mês fechado = passado de verdade (2025); as asserções são na linha do
    # nosso qualificador, imunes ao seed demo de 2022–2026.
    Dado um qualificador folha de receita "1.93.2" com lançamento de "150.00" em "2025-03-10"
    E um cenário "CEN_FECHADO" com versão publicada projetando "900.00" por mês para "1.93.2" em "2025"
    Quando consulto o DFC projetado do mês "2025-03" com o cenário "CEN_FECHADO"
    Então a folha "1.93.2" soma "150.00" nas colunas do mês
    E nenhuma célula do DFC está marcada como projetada

  # ------------------------------------------------------------------ R10

  Cenário: Versão publicada alimenta o relatório sem aviso
    Dado um qualificador folha de receita "1.93.3" ativo
    E um cenário "CEN_PUB" com versão publicada projetando "200.00" por mês para "1.93.3" em "2034"
    Quando consulto o DFC projetado de "2034" na visão anual com o cenário "CEN_PUB"
    Então a folha "1.93.3" exibe "200.00" na coluna do mês "1" marcada como projetada
    E a origem da projeção é a versão publicada, sem cálculo ao vivo

  Cenário: Rascunho não alimenta e cai no cálculo ao vivo
    Dado um cenário manual "CEN_RASCUNHO" com ano-base "2033" e apenas versão rascunho
    Quando consulto o DFC projetado de "2034" na visão anual com o cenário "CEN_RASCUNHO"
    Então a origem da projeção é cálculo ao vivo

  Cenário: Publicada mais recente vence
    Dado um qualificador folha de receita "1.93.4" ativo
    E um cenário "CEN_DUAS" com versão publicada projetando "100.00" por mês para "1.93.4" em "2034"
    E o cenário "CEN_DUAS" ganha nova versão publicada projetando "300.00" por mês para "1.93.4" em "2034"
    Quando consulto o DFC projetado de "2034" na visão anual com o cenário "CEN_DUAS"
    Então a folha "1.93.4" exibe "300.00" na coluna do mês "1" marcada como projetada

  # ------------------------------------------------------------------ R11

  Cenário: Mês aberto na visão mensal é previsão pura
    Dado um qualificador folha de receita "1.93.5" com lançamento de "111.00" em "2034-05-10"
    E um cenário "CEN_MES" com versão publicada projetando "900.00" por mês para "1.93.5" em "2034"
    Quando consulto o DFC projetado do mês "2034-05" com o cenário "CEN_MES"
    Então as colunas de dia da folha "1.93.5" estão zeradas
    E a coluna TOTAIS da folha "1.93.5" exibe "900.00" marcada como projetada

  Cenário: Visão anual mistura mês fechado e aberto
    Dado um qualificador folha de receita "1.93.6" com lançamento de "50.00" no mês anterior ao corrente
    E um cenário "CEN_MISTO" com versão publicada projetando "200.00" por mês para "1.93.6" no ano corrente
    Quando consulto o DFC projetado do ano corrente na visão anual com o cenário "CEN_MISTO"
    Então a folha "1.93.6" exibe "50.00" na coluna do mês anterior sem marcação
    E a folha "1.93.6" exibe "200.00" na coluna do mês corrente marcada como projetada

  Cenário: Pais, totais e saldos recompostos
    Dado um qualificador folha de receita "1.94.1" ativo
    E um qualificador folha de receita "1.94.2" ativo
    E um cenário "CEN_PAIS" com versão publicada projetando "100.00" por mês para "1.94.1" em "2034"
    E a versão publicada do cenário "CEN_PAIS" também projeta "200.00" por mês para "1.94.2" em "2034"
    Quando consulto o DFC projetado de "2034" na visão anual com o cenário "CEN_PAIS"
    Então o nó pai "1.94" exibe "300.00" na coluna do mês "1"
    E o total do DFC na coluna do mês "1" é "300.00"
    E o saldo final do DFC na coluna do mês "1" reflete o projetado

  Cenário: Drill-down de célula projetada informa a origem
    Dado um qualificador folha de receita "1.93.7" ativo
    E um cenário "CEN_DRILL" com versão publicada projetando "400.00" por mês para "1.93.7" em "2034"
    Quando abro os eventos projetados da folha "1.93.7" no mês "1" de "2034" com o cenário "CEN_DRILL"
    Então os eventos informam a origem da projeção citando a versão publicada
    E nenhum lançamento é listado

  # ------------------------------------------------------------------ R12

  Cenário: Cenário ANUAL redistribui pelo perfil do ano-base
    Dado um qualificador folha de receita "1.95.1" com lançamento de "900.00" em "2033-01-10"
    E o qualificador "1.95.1" com lançamento de "300.00" em "2033-02-10"
    E um cenário ANUAL "CEN_PERFIL" com ano-base "2033" e versão publicada projetando o total anual "1200.00" para "1.95.1" em "2034"
    Quando consulto o DFC projetado de "2034" na visão anual com o cenário "CEN_PERFIL"
    Então a folha "1.95.1" exibe "900.00" na coluna do mês "1" marcada como projetada
    E a folha "1.95.1" exibe "300.00" na coluna do mês "2" marcada como projetada

  Cenário: Sem histórico no ano-base distribui um doze avos
    Dado um qualificador folha de receita "1.95.2" ativo
    E um cenário ANUAL "CEN_UNIFORME" com ano-base "2033" e versão publicada projetando o total anual "1200.00" para "1.95.2" em "2034"
    Quando consulto o DFC projetado de "2034" na visão anual com o cenário "CEN_UNIFORME"
    Então a folha "1.95.2" exibe "100.00" na coluna do mês "1" marcada como projetada
    E a folha "1.95.2" exibe "100.00" na coluna do mês "12" marcada como projetada

  Cenário: Qualificador inativo fica fora da base histórica do perfil
    Dado um qualificador folha de receita "1.96.1" com lançamento de "500.00" em "2035-01-10"
    E um qualificador folha de receita "1.96.2" inativado com lançamento de "500.00" em "2035-02-10"
    E um cenário ANUAL "CEN_INATIVO" com ano-base "2035" e versão publicada projetando o total anual agregado "1200.00" de receita em "2036"
    Quando consulto o DFC projetado de "2036" na visão anual com o cenário "CEN_INATIVO"
    Então a linha sintética de receita exibe "1200.00" na coluna do mês "1" marcada como projetada
    E a linha sintética de receita exibe "0.00" na coluna do mês "2"

  # ------------------------------------------------------------------ R13

  Cenário: Projeção agregada vira linha sintética
    Dado um cenário "CEN_AGREGADO" com versão publicada projetando "500.00" por mês agregado de receita em "2034"
    Quando consulto o DFC projetado de "2034" na visão anual com o cenário "CEN_AGREGADO"
    Então a raiz Receita tem a linha sintética "Projeção do cenário (não detalhada)"
    E a linha sintética de receita exibe "500.00" na coluna do mês "1" marcada como projetada
    E o total do DFC na coluna do mês "1" inclui os "500.00"

  Cenário: Detalhe parcial convive com agregado
    Dado um qualificador folha de receita "1.97.1" ativo
    E um cenário "CEN_PARCIAL" com versão publicada projetando "250.00" por mês para "1.97.1" em "2034"
    E a versão publicada do cenário "CEN_PARCIAL" também projeta "500.00" por mês agregado de despesa em "2034"
    Quando consulto o DFC projetado de "2034" na visão anual com o cenário "CEN_PARCIAL"
    Então a folha "1.97.1" exibe "250.00" na coluna do mês "1" marcada como projetada
    E a raiz Despesa tem a linha sintética "Projeção do cenário (não detalhada)"
    E a linha sintética de despesa exibe "-500.00" na coluna do mês "1" marcada como projetada
