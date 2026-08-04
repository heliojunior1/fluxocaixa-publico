# language: pt
Funcionalidade: Classificação da staging em lançamentos
  Spec automacao-lancamentos R12/R13 (change automacao-lancamentos-processamento)

  Fecha o circuito: linha PENDENTE → lançamento com origem Automático.
  Sem bookmark: a linha pendente é o marco.

  Contexto:
    Dado que estou autenticado como administrador
    E um sistema de origem "SIS_P" cadastrado
    E os termos de regra padrão cadastrados
    E um qualificador folha "1.1.1"
    E um qualificador folha "1.1.2"
    E linhas na staging de "SIS_P" no ano 2026

  # --- R13: a classificação ---

  Cenário: Linha que casa com um item vira lançamento
    Dado o mapeamento 2026 de "SIS_P" com o item "1.1.1" e regra "Natureza começa com '1112'"
    Quando processo o mapeamento
    Então foram criados 2 lançamentos no qualificador "1.1.1"
    E os lançamentos têm origem "Automático" e tipo "Entrada"
    E os valores dos lançamentos são Decimal com 2 casas

  Cenário: Tipo é derivado do sinal do valor efetivo
    # Desde a F6.1b o tipo NÃO vem do ind_tipo do mapeamento: vem do sinal do
    # valor efetivo (spec cadastros-nucleo R10). Linha de despesa chega
    # negativa da fonte e vira Saída com valor positivo.
    Dado o mapeamento 2026 de "SIS_P" com o item "1.1.1" e regra "Natureza começa com '2222'"
    Quando processo o mapeamento
    Então os lançamentos têm origem "Automático" e tipo "Saída"

  Cenário: Inversão de sinal é aplicada
    Dado o mapeamento 2026 de "SIS_P" com o item "1.1.1" e regra "Natureza começa com '1112'" com inversão
    Quando processo o mapeamento
    Então os lançamentos do qualificador "1.1.1" têm valores negativos

  Cenário: Inversão de sinal vale também para despesa
    Dado o mapeamento 2026 de "SIS_P" com o item "1.1.1" e regra "Natureza começa com '1112'" com inversão
    Quando processo o mapeamento
    Então os lançamentos do qualificador "1.1.1" têm valores negativos

  Cenário: Linha que casa com dois itens vira erro explícito
    Dado o mapeamento 2026 de "SIS_P" com dois itens que casam com a mesma linha
    Quando processo o mapeamento
    Então nenhum lançamento foi criado para a linha em conflito
    E a linha em conflito fica com erro citando os qualificadores

  Cenário: Linha que não casa com item algum segue pendente
    Dado o mapeamento 2026 de "SIS_P" com o item "1.1.1" e regra "Natureza começa com '1112'"
    Quando processo o mapeamento
    Então a linha de natureza "22220000" continua pendente e sem erro

  # --- R12: rastro e idempotência ---

  Cenário: Lançamento gerado aponta para a linha de origem
    Dado o mapeamento 2026 de "SIS_P" com o item "1.1.1" e regra "Natureza começa com '1112'"
    Quando processo o mapeamento
    Então cada lançamento criado referencia a linha de staging que o originou
    E as linhas que geraram lançamento ficam processadas

  Cenário: Reprocessar não duplica
    Dado o mapeamento 2026 de "SIS_P" com o item "1.1.1" e regra "Natureza começa com '1112'"
    E que já processei o mapeamento
    Quando processo o mapeamento
    Então continuam existindo 2 lançamentos no qualificador "1.1.1"

  Cenário: Linha com valor zero não gera lançamento
    Dado uma linha pendente de valor zero que casa com a regra
    E o mapeamento 2026 de "SIS_P" com o item "1.1.1" e regra "Natureza começa com '1112'"
    Quando processo o mapeamento
    Então nenhum lançamento foi criado para a linha de valor zero

  Cenário: Lançamento manual não é tocado
    Dado um lançamento manual no qualificador "1.1.1"
    E o mapeamento 2026 de "SIS_P" com o item "1.1.1" e regra "Natureza começa com '1112'"
    Quando processo o mapeamento
    Então o lançamento manual permanece inalterado
