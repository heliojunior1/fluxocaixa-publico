# language: pt
Funcionalidade: Tela de saldos por fundo e importação de transição
  Como tesouraria, quero ver e gerir saldos no modelo por fundo (agregado ou
  por fundo) e importar o CSV atual sem perder dados.

  Contexto:
    Dado que estou autenticado como administrador
    E um sistema de origem "SIS_TELA" cadastrado

  Cenário: Visão agregada soma os fundos da conta
    Dado uma conta de tela "133/0001/AG-1"
    E um fundo de tela "TELA1"
    E um fundo de tela "TELA2"
    E um saldo de tela "100.00" na conta "133/0001/AG-1" fundo "TELA1" em "2025-04-01"
    E um saldo de tela "250.00" na conta "133/0001/AG-1" fundo "TELA2" em "2025-04-01"
    Quando listo os saldos na visão "agregado"
    Então a conta "133/0001/AG-1" em "2025-04-01" aparece com saldo agregado "350.00"

  Cenário: Edição mantém a chave e versiona por inativação
    Dado uma conta de tela "134/0001/AG-2"
    E um fundo de tela "TELA3"
    E um saldo de tela "500.00" na conta "134/0001/AG-2" fundo "TELA3" em "2025-04-02"
    Quando edito o saldo da conta "134/0001/AG-2" fundo "TELA3" em "2025-04-02" para "600.00"
    Então a chave conta "134/0001/AG-2" fundo "TELA3" em "2025-04-02" tem 1 ativo com "600.00"
    E a chave conta "134/0001/AG-2" fundo "TELA3" em "2025-04-02" tem 1 inativo com "500.00"

  Cenário: Excluir inativa sem inserir substituta
    Dado uma conta de tela "135/0001/AG-3"
    E um fundo de tela "TELA4"
    E um saldo de tela "700.00" na conta "135/0001/AG-3" fundo "TELA4" em "2025-04-03"
    Quando inativo o saldo da conta "135/0001/AG-3" fundo "TELA4" em "2025-04-03"
    Então a chave conta "135/0001/AG-3" fundo "TELA4" em "2025-04-03" tem 0 ativo
    E a chave conta "135/0001/AG-3" fundo "TELA4" em "2025-04-03" tem 1 inativo com "700.00"

  Cenário: Import CSV atual alimenta o modelo novo no fundo GERAL
    Dado uma conta de tela "136/0001/AG-4"
    Quando importo pela tela um CSV com o saldo "1234.56" para a conta "136/0001/AG-4" em "2025-04-04"
    Então o resultado da tela informa 1 inserida e 0 com erro
    E a conta "136/0001/AG-4" tem no fundo "GERAL" em "2025-04-04" o saldo ativo "1234.56" com origem "IMPORTADO"
