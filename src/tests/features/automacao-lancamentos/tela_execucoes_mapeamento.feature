# language: pt
Funcionalidade: Tela de execuções de mapeamento
  Spec automacao-lancamentos R16 (change automacao-lancamentos-processamento)

  Contexto:
    Dado que estou autenticado como administrador
    E um sistema de origem "SIS_T" cadastrado
    E os termos de regra padrão cadastrados
    E um qualificador folha "1.1.1"
    E linhas na staging de "SIS_T" no ano 2026
    E o mapeamento 2026 de "SIS_T" com o item "1.1.1" e regra "Natureza começa com '1112'"

  Cenário: A tela lista as execuções com seus contadores
    Dado que já processei o mapeamento
    Quando abro a tela de execuções de mapeamento
    Então vejo a execução com situação "SUCESSO" e 2 lançamentos gerados

  Cenário: Processar manualmente pela tela
    Quando disparo o processamento pela tela
    Então a execução de mapeamento tem disparo "MANUAL"
    E foram criados 2 lançamentos no qualificador "1.1.1"

  Cenário: Sem permissão de execução não vejo a ação de processar
    Dado que estou autenticado como usuário só de consulta
    Quando abro a tela de execuções de mapeamento
    Então não vejo a ação de processar
