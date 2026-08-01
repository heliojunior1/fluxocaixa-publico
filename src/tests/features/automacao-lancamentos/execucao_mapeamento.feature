# language: pt
Funcionalidade: Registro e disparo do processamento
  Spec automacao-lancamentos R15 (change automacao-lancamentos-processamento)

  O grão do processamento é o mapeamento, não a fonte — e o resync não tem execução
  de extração onde se pendurar. Daí o log próprio.

  Contexto:
    Dado que estou autenticado como administrador
    E um sistema de origem "SIS_E" cadastrado
    E os termos de regra padrão cadastrados
    E um qualificador folha "1.1.1"
    E um qualificador folha "1.1.2"

  Cenário: Execução registra os contadores
    Dado linhas na staging de "SIS_E" no ano 2026
    E o mapeamento 2026 de "SIS_E" com dois itens que casam com a mesma linha
    Quando processo o mapeamento
    Então a execução de mapeamento registra 1 lançamento gerado e 1 linha com erro
    E a situação da execução de mapeamento é "PARCIAL"

  Cenário: Sem linha candidata registra SEM_DADOS
    Dado o mapeamento 2026 de "SIS_E" com o item "1.1.1" e regra "Natureza começa com '1112'"
    Quando processo o mapeamento
    Então a situação da execução de mapeamento é "SEM_DADOS"

  Cenário: Resync registra os lançamentos removidos
    Dado linhas na staging de "SIS_E" no ano 2026
    E o mapeamento 2026 de "SIS_E" com o item "1.1.1" e regra "Natureza começa com '1112'"
    E que já processei o mapeamento
    Quando altero a regra do item "1.1.1" para "Natureza começa com '11120001'" e processo
    Então a execução de mapeamento registra 2 lançamentos removidos

  Cenário: Processamento manual registra o disparo
    Dado linhas na staging de "SIS_E" no ano 2026
    E o mapeamento 2026 de "SIS_E" com o item "1.1.1" e regra "Natureza começa com '1112'"
    Quando processo o mapeamento manualmente
    Então a execução de mapeamento tem disparo "MANUAL"

  # --- disparo automático pela carga ---

  Cenário: Carga de lançamento dispara o processamento
    Dado o mapeamento 2026 de "SIS_E" com o item "1.1.1" e regra "Natureza começa com '1112'"
    E uma fonte de lançamento de "SIS_E" que traz linhas que casam
    Quando executo a fonte de lançamento
    Então a execução de mapeamento tem disparo "AUTOMATICO"
    E foram criados 2 lançamentos no qualificador "1.1.1"

  Cenário: Falha no processamento não reclassifica a extração
    Dado o mapeamento 2026 de "SIS_E" com o item "1.1.1" e regra "Natureza começa com '1112'"
    E uma fonte de lançamento de "SIS_E" que traz linhas que casam
    E que o processamento vai falhar
    Quando executo a fonte de lançamento
    Então a execução da extração mantém a situação "SUCESSO"
    E a situação da execução de mapeamento é "ERRO"
