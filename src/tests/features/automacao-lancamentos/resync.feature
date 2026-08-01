# language: pt
Funcionalidade: Detecção de item sujo e resync cirúrgico
  Spec automacao-lancamentos R14 (change automacao-lancamentos-processamento)

  A FK seq_etl_staging torna o resync cirúrgico de verdade: dos lançamentos do
  qualificador saem exatamente as linhas a resetar. A referência, sem essa âncora,
  reseta o ano inteiro do item sujo.

  Contexto:
    Dado que estou autenticado como administrador
    E um sistema de origem "SIS_R" cadastrado
    E os termos de regra padrão cadastrados
    E um qualificador folha "1.1.1"
    E um qualificador folha "1.1.2"
    E linhas na staging de "SIS_R" no ano 2026

  Cenário: Alterar a regra de um item ressincroniza só aquele qualificador
    Dado um mapeamento com os itens "1.1.1" em "Natureza começa com '1112'" e "1.1.2" em "Natureza começa com '2222'"
    E que já processei o mapeamento
    Quando altero a regra do item "1.1.1" para "Natureza começa com '11120001'" e processo
    Então o qualificador "1.1.1" tem 1 lançamento
    E os lançamentos do qualificador "1.1.2" permanecem intactos

  Cenário: Processar carimba a última execução do item
    Dado um mapeamento com o item "1.1.1" em "Natureza começa com '1112'"
    E que o item "1.1.1" nunca foi processado
    Quando processo o mapeamento
    Então o item "1.1.1" tem data de última execução
    E processar de novo não remove nenhum lançamento

  Cenário: Salvar o mapeamento sem mudar o item não dispara resync
    Dado um mapeamento com o item "1.1.1" em "Natureza começa com '1112'"
    E que já processei o mapeamento
    Quando salvo o mapeamento reenviando o item igual e processo
    Então nenhum lançamento foi removido

  Cenário: Linha em erro volta a ser processada após corrigir a regra
    Dado um mapeamento com dois itens que casam com a mesma linha
    E que já processei o mapeamento
    Quando corrijo a regra do item "1.1.2" para "Natureza começa com '9999'" e processo
    Então a linha que estava em erro vira lançamento no qualificador "1.1.1"

  # --- MODIFIED R6: o marco é descartado quando o conteúdo muda ---

  Cenário: Alterar o conteúdo do item descarta o marco de execução
    Dado um mapeamento com o item "1.1.1" em "Natureza começa com '1112'"
    E que já processei o mapeamento
    Quando altero a regra do item "1.1.1" para "Natureza começa com '11120001'"
    Então o item "1.1.1" fica sem data de última execução

  Cenário: Alterar e processar no mesmo dia ressincroniza
    Dado um mapeamento com o item "1.1.1" em "Natureza começa com '1112'"
    E que já processei o mapeamento hoje
    Quando altero a regra do item "1.1.1" para "Natureza começa com '11120001'" e processo
    Então o qualificador "1.1.1" tem 1 lançamento
