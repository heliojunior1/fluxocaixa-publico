# language: pt
Funcionalidade: Processamento atômico e resync no escopo do mapeamento
  Spec automacao-lancamentos R12/R14/R15 (change processamento-idempotente-resync-cirurgico)

  A gravação do lançamento e a marcação da linha de staging são UMA transação:
  interrupção em qualquer ponto deixa o banco com ambos ou com nenhum. O resync
  de item sujo é restrito ao escopo do mapeamento dono (qualificador + ano de
  exercício + sistema de origem) — um mapeamento nunca remove o que não é capaz
  de regerar. Ilha de datas: 2061/2062 (seed demo vive em 2022–2026).

  Contexto:
    Dado que estou autenticado como administrador
    E um sistema de origem "SIS_Q1A" cadastrado
    E os termos de regra padrão cadastrados
    E um qualificador folha "61.1"
    E linhas na staging de "SIS_Q1A" no ano 2061

  Cenário: Falha ao marcar a linha desfaz o lançamento
    Dado o mapeamento 2061 de "SIS_Q1A" com o item "61.1" e regra "Natureza começa com '1112'"
    E que a marcação de status das linhas falhará nesta execução
    Quando processo o mapeamento
    Então nenhum lançamento existe no qualificador "61.1"
    E a linha de natureza "11120000" continua pendente

  Cenário: Contadores da execução descrevem o que foi efetivado
    Dado o mapeamento 2061 de "SIS_Q1A" com o item "61.1" e regra "Natureza começa com '1112'"
    E que a marcação de status das linhas falhará nesta execução
    Quando processo o mapeamento
    Então a execução registra 0 lançamentos gerados e status "ERRO"
    E de fato não há lançamento automático no banco para o exercício 2061

  Cenário: Linha devolvida a pendente com lançamento existente não duplica
    Dado o mapeamento 2061 de "SIS_Q1A" com o item "61.1" e regra "Natureza começa com '1112'"
    E que já processei o mapeamento
    E a linha de natureza "11120000" foi devolvida a pendente por fora
    Quando processo o mapeamento
    Então o qualificador "61.1" tem 2 lançamentos

  Cenário: Resync não alcança outro exercício
    Dado linhas na staging de "SIS_Q1A" no ano 2062
    E o mapeamento 2061 de "SIS_Q1A" com o item "61.1" e regra "Natureza começa com '1112'"
    E o mapeamento 2062 de "SIS_Q1A" com o item "61.1" e regra "Natureza começa com '1112'"
    E que já processei os dois mapeamentos
    E o item do mapeamento 2061 ficou sujo
    Quando processo o mapeamento 2061
    Então os lançamentos do exercício 2062 permanecem intactos
    E o qualificador "61.1" tem 4 lançamentos

  Cenário: Resync não alcança outro sistema de origem
    Dado um sistema de origem "SIS_Q1B" cadastrado
    E linhas na staging de "SIS_Q1B" no ano 2061
    E o mapeamento 2061 de "SIS_Q1A" com o item "61.1" e regra "Natureza começa com '1112'"
    E o mapeamento 2061 de "SIS_Q1B" com o item "61.1" e regra "Natureza começa com '1112'"
    E que já processei os dois mapeamentos
    E o item do mapeamento de "SIS_Q1A" ficou sujo
    Quando processo o mapeamento de "SIS_Q1A"
    Então os lançamentos originados de "SIS_Q1B" permanecem intactos
    E o qualificador "61.1" tem 4 lançamentos
