# language: pt
Funcionalidade: Conector de banco SQL externo
  Spec extracao-configuravel R21 (change conector-banco-sql)

  Contexto:
    Dado que estou autenticado como administrador
    E um sistema de origem "SIS_X" cadastrado
    E o conector "BANCO_SQL" registrado
    E as contas de SQL cadastradas

  Cenário: Query com bind params traz e mapeia as linhas
    Dado um banco externo com saldos em 10/07/2026
    E uma fonte "SQL Saldos" que consulta esse banco por período
    Quando executo a fonte "SQL Saldos" de "2026-07-10" a "2026-07-10"
    Então a execução de SQL registra status "SUCESSO" com 2 inseridas e 0 com erro
    E o saldo gravado da conta "001/0001/12345" e fundo "9101" vale "1850432.10"

  Cenário: Bind parameters filtram por data (não interpolação textual)
    Dado um banco externo com saldos em 10/07/2026 e em 20/07/2026
    E uma fonte "SQL Janela" que consulta esse banco por período
    Quando executo a fonte "SQL Janela" de "2026-07-10" a "2026-07-15"
    Então a execução de SQL registra status "SUCESSO" com 2 inseridas e 0 com erro

  Cenário: Query que não é SELECT é rejeitada
    Quando cadastro pela API uma fonte SQL com a query "DELETE FROM saldos_ext"
    Então o cadastro de SQL é rejeitado
    E a fonte "SQL Perigosa" não existe

  Cenário: Comentário antes do SELECT não engana a validação
    Dado um banco externo com saldos em 10/07/2026
    Quando cadastro pela API uma fonte SQL "SQL Comentada" com comentário antes do SELECT
    Então a fonte "SQL Comentada" existe

  Cenário: Lote grande é lido em streaming
    Dado um banco externo com 60 saldos em 10/07/2026
    E uma fonte "SQL Lote" que consulta esse banco por período com batch 25
    Quando executo a fonte "SQL Lote" de "2026-07-10" a "2026-07-10"
    Então a execução de SQL registra status "SUCESSO" com 60 inseridas e 0 com erro

  Cenário: Erro de mapeamento numa linha é pontual
    Dado um banco externo com um saldo válido e um saldo com valor inválido em 10/07/2026
    E uma fonte "SQL Parcial" que consulta esse banco por período
    Quando executo a fonte "SQL Parcial" de "2026-07-10" a "2026-07-10"
    Então a execução de SQL registra status "PARCIAL" com 1 inseridas e 1 com erro

  Cenário: Destino LANCAMENTO sem contrato de staging é rejeitado
    Quando cadastro pela API uma fonte SQL com destino "LANCAMENTO"
    Então o cadastro de SQL é rejeitado

  Cenário: Teste de conexão não executa a query nem registra execução
    Dado um banco externo com saldos em 10/07/2026
    E uma fonte "SQL Teste" que consulta esse banco por período
    Quando testo a conexão da fonte "SQL Teste"
    Então o teste de conexão de SQL retorna sucesso
    E nenhuma execução foi registrada para a fonte de SQL "SQL Teste"
