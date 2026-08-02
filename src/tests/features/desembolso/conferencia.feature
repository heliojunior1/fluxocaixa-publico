# language: pt
Funcionalidade: Conferência do desembolso (três visões derivadas)
  Como Tesouro, quero o batimento diário separado em três saldos — controle,
  bancário e conciliação — tudo derivado, série contínua, diferença
  categorizada e apurado externo sinalizado.

  Contexto:
    Dado que estou autenticado como administrador
    E um órgão "70004" chamado "Secretaria da Conferência"
    E a fonte "1.596" cadastrada na vigência 2041 como "livre"

  Cenário: Controle encadeia o pendente e o dia vazio aparece com zeros
    Dado um qualificador folha de despesa "2.9.31"
    E uma liberação confirmada de 1000.00 em "2041-05-10" no órgão "70004", qualificador "2.9.31" e fonte "1.596" da vigência 2041
    E um pagamento de 300.00 em "2041-05-12" no órgão "70004" e qualificador "2.9.31" apropriado nessa liberação
    Quando consulto o controle de "2041-05-10" a "2041-05-12"
    Então o movimento do controle de "2041-05-10" é 1000.00
    E o dia "2041-05-11" aparece no controle com liberações 0.00
    E o movimento do controle de "2041-05-12" é -300.00

  Cenário: Transferência interna neutraliza a diferença da conciliação
    Dado um qualificador folha de despesa "2.9.32"
    E um pagamento de 300.00 em "2041-06-10" no órgão "70004" e qualificador "2.9.32"
    E uma saída bancária de 500.00 em "2041-06-10" no qualificador "2.9.32"
    E uma transferência interna de 200.00 em "2041-06-10"
    Quando consulto a conciliação de "2041-06-10" a "2041-06-10"
    Então a parcela neutra de "2041-06-10" é 200.00
    E o valor a investigar de "2041-06-10" é 0.00

  Cenário: Diferença sem transferência vira "a investigar"
    Dado um qualificador folha de despesa "2.9.33"
    E um pagamento de 300.00 em "2041-07-10" no órgão "70004" e qualificador "2.9.33"
    E uma saída bancária de 500.00 em "2041-07-10" no qualificador "2.9.33"
    Quando consulto a conciliação de "2041-07-10" a "2041-07-10"
    Então o valor a investigar de "2041-07-10" é 200.00

  Cenário: Apurado externo que bate é conferido; divergente é sinalizado
    Dado um qualificador folha de despesa "2.9.34"
    E uma liberação confirmada de 1000.00 em "2041-08-10" no órgão "70004", qualificador "2.9.34" e fonte "1.596" da vigência 2041
    E o apurado externo de liberações de "2041-08-10" informado como 1000.00
    Quando consulto o controle de "2041-08-10" a "2041-08-10"
    Então a situação do apurado de "2041-08-10" é "CONFERIDO"
    Quando o apurado externo de liberações de "2041-08-10" é alterado para 900.00
    E consulto o controle de "2041-08-10" a "2041-08-10"
    Então a situação do apurado de "2041-08-10" é "DIVERGENTE"

  Cenário: Dia sem apurado fica neutro
    Quando consulto o controle de "2041-09-10" a "2041-09-10"
    Então a situação do apurado de "2041-09-10" é "NEUTRO"
