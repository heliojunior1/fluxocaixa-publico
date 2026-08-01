# language: pt
Funcionalidade: Modelo de saldo por conta, fundo e dia
  Como tesouraria, quero saldos granulares por fundo de investimento com
  histórico preservado, rendimento derivado e agregação por conta.

  Cenário: Estrutura criada pela migração e domínio seedado
    Então as tabelas do saldo por fundo existem
    E os tipos de origem "MANUAL,AUTOMATIZADO,IMPORTADO" estão seedados
    Quando o seed de domínio executa novamente
    Então nenhum sistema de origem novo é criado pelo seed

  Cenário: Segunda linha ativa da mesma chave é bloqueada pelo banco
    Dado uma conta de fundo "077/0001/111-1"
    E um fundo "F111" de origem "MANUAL"
    E um saldo gravado de "1000.00" para essa conta e fundo em "2026-07-10"
    Quando insiro diretamente outra linha ativa para a mesma chave
    Então o banco rejeita com violação de unicidade

  Cenário: Regravar preserva o histórico por inativação
    Dado uma conta de fundo "077/0001/222-2"
    E um fundo "F222" de origem "MANUAL"
    E um saldo gravado de "1000.00" para essa conta e fundo em "2026-07-10"
    Quando gravo "1200.00" para a mesma chave
    Então existe exatamente 1 linha ativa com valor "1200.00" para a chave
    E existe 1 linha inativa com valor "1000.00" para a chave

  Cenário: Origem automatizada exige sistema de origem
    Dado uma conta de fundo "077/0001/333-3"
    E um fundo "F333" de origem "MANUAL"
    Quando gravo um saldo com tipo "AUTOMATIZADO" e sem sistema de origem
    Então a gravação é rejeitada com a mensagem "Origem automatizada exige o sistema de origem"

  Cenário: Origem manual não deve informar sistema
    Dado uma conta de fundo "077/0001/444-4"
    E um fundo "F444" de origem "MANUAL"
    E um sistema de origem "SIS_TESTE" cadastrado
    Quando gravo um saldo com tipo "MANUAL" e sistema "SIS_TESTE"
    Então a gravação é rejeitada com a mensagem "Origem manual/importada não deve informar sistema de origem"

  Cenário: Rendimento calculado com dia anterior
    Dado uma conta de fundo "077/0001/555-5"
    E um fundo "F555" de origem "MANUAL"
    E um saldo gravado de "1000.00" para essa conta e fundo em "2026-07-10"
    E um saldo gravado de "1010.00" com aplicações "5.00" e resgates "2.00" em "2026-07-11"
    Quando consulto a view de cálculo em "2026-07-11"
    Então o saldo inicial derivado é "1000.00"
    E o rendimento calculado é "7.00"

  Cenário: Primeiro dia do par tem saldo inicial zero
    Dado uma conta de fundo "077/0001/666-6"
    E um fundo "F666" de origem "MANUAL"
    E um saldo gravado de "1000.00" para essa conta e fundo em "2026-07-10"
    Quando consulto a view de cálculo em "2026-07-10"
    Então o saldo inicial derivado é "0.00"

  Cenário: Linhas inativas não entram no cálculo
    Dado uma conta de fundo "077/0001/777-7"
    E um fundo "F777" de origem "MANUAL"
    E um saldo gravado de "999.00" para essa conta e fundo em "2026-07-10"
    E gravo "1000.00" para a mesma chave
    Quando consulto a view de cálculo em "2026-07-10"
    Então a view retorna 1 linha com valor "1000.00"

  Cenário: Agregado soma os fundos da conta
    Dado uma conta de fundo "077/0001/888-8"
    E um fundo "F881" de origem "MANUAL"
    E um fundo "F882" de origem "MANUAL"
    E um saldo gravado de "100.00" para o fundo "F881" dessa conta em "2026-07-10"
    E um saldo gravado de "200.00" para o fundo "F882" dessa conta em "2026-07-10"
    Quando consulto o agregado da conta em "2026-07-10"
    Então o saldo agregado é "300.00"
    E a origem consolidada é "Manual"

  Cenário: Origem consolidada Mista quando origens divergem
    Dado uma conta de fundo "077/0001/999-9"
    E um fundo "F991" de origem "MANUAL"
    E um fundo "F992" de origem "IMPORTADO"
    E um saldo gravado de "100.00" para o fundo "F991" dessa conta em "2026-07-10"
    E um saldo importado de "200.00" para o fundo "F992" dessa conta em "2026-07-10"
    Quando consulto o agregado da conta em "2026-07-10"
    Então a origem consolidada é "Mista"
