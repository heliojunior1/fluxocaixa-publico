# language: pt
Funcionalidade: Preview da regra sobre a staging
  Spec automacao-lancamentos R8 (recorte evoluído no change tela-mapeamentos-builder)

  O recorte é o mesmo do mapeamento — (sistema de origem, ano) — e não uma fonte
  isolada: um sistema de origem pode ter várias fontes.

  Contexto:
    Dado que estou autenticado como administrador
    E os termos de regra padrão cadastrados
    E o sistema de origem "SIS_PREV" com uma fonte de lançamento com linhas na staging

  Cenário: Preview conta e amostra as linhas que casam
    Quando peço o preview da regra "Natureza começa com '1112'" para "SIS_PREV"
    Então o preview retorna 2 linhas
    E a amostra do preview traz valores Decimal com 2 casas
    E nenhuma linha da staging teve o status alterado

  Cenário: Preview de regra com em casa múltiplos valores
    Quando peço o preview da regra "Unidade Gestora em ('999001','999002')" para "SIS_PREV"
    Então o preview retorna 3 linhas

  Cenário: Preview sobre coluna da staging casa por valor
    Quando peço o preview da regra "Valor > 150" para "SIS_PREV"
    Então o preview retorna 2 linhas

  Cenário: Atributo ausente não casa e não quebra
    Quando peço o preview da regra "Fonte Detalhada = '999'" para "SIS_PREV"
    Então o preview retorna 0 linhas

  Cenário: Preview não grava nada
    Quando peço o preview da regra "Natureza começa com '1112'" para "SIS_PREV"
    Então nenhum lançamento foi criado

  # --- o recorte por sistema de origem (não por fonte) ---

  Cenário: Preview cobre as várias fontes do sistema de origem
    Dado uma segunda fonte de lançamento de "SIS_PREV" com 1 linha que casa
    Quando peço o preview da regra "Natureza começa com '1112'" para "SIS_PREV"
    Então o preview retorna 3 linhas

  Cenário: Preview de outro sistema de origem não é contado
    Dado uma fonte de lançamento do sistema "SIS_OUTRO" com 1 linha que casa
    Quando peço o preview da regra "Natureza começa com '1112'" para "SIS_PREV"
    Então o preview retorna 2 linhas

  Cenário: Preview filtra pelo ano de exercício quando informado
    Dado uma fonte de lançamento de "SIS_PREV" com 1 linha que casa no ano 2025
    Quando peço o preview da regra "Natureza começa com '1112'" para "SIS_PREV" no ano 2026
    Então o preview retorna 2 linhas
