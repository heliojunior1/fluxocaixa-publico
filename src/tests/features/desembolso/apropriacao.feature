# language: pt
Funcionalidade: Apropriação pagamento ↔ liberação (F7.1b)
  Como Tesouro, quero apropriar pagamentos nas liberações que os autorizaram
  — com estouro proibido, estorno por evento e a fonte do pagamento sempre
  herdada da apropriação (monofonte).

  Contexto:
    Dado que estou autenticado como administrador
    E um órgão "70002" chamado "Secretaria de Apropriação"
    E a fonte "1.580" cadastrada na vigência 2038 como "livre"

  Cenário: Escrita nova sem qualificador é recusada
    Quando tento registrar um pagamento de 100.00 em "2038-09-01" sem qualificador
    Então a operação de pagamento é rejeitada com a mensagem "Pagamento exige qualificador"

  Cenário: Apropriação válida baixa o pendente e herda a fonte
    Dado um qualificador folha de despesa "2.8.1"
    E uma liberação confirmada de 1000.00 em "2038-09-02" no órgão "70002", qualificador "2.8.1" e fonte "1.580" da vigência 2038
    E um pagamento de 300.00 em "2038-09-02" no órgão "70002" e qualificador "2.8.1"
    Quando aproprio 300.00 dessa liberação nesse pagamento
    Então o saldo restante dessa liberação é 700.00
    E o pagamento referencia a fonte "1.580" da vigência 2038

  Cenário: Estouro do saldo da liberação é proibido
    Dado um qualificador folha de despesa "2.8.2"
    E uma liberação confirmada de 100.00 em "2038-09-03" no órgão "70002", qualificador "2.8.2" e fonte "1.580" da vigência 2038
    E um pagamento de 500.00 em "2038-09-03" no órgão "70002" e qualificador "2.8.2"
    Quando aproprio 150.00 dessa liberação nesse pagamento
    Então a operação de pagamento é rejeitada com a mensagem "Apropriação acima do saldo restante da liberação é proibida"
    E o saldo restante dessa liberação é 100.00

  Cenário: Soma acima do valor do pagamento é proibida
    Dado um qualificador folha de despesa "2.8.3"
    E uma liberação confirmada de 1000.00 em "2038-09-04" no órgão "70002", qualificador "2.8.3" e fonte "1.580" da vigência 2038
    E um pagamento de 300.00 em "2038-09-04" no órgão "70002" e qualificador "2.8.3"
    E aproprio 250.00 dessa liberação nesse pagamento
    Quando aproprio 100.00 dessa liberação nesse pagamento
    Então a operação de pagamento é rejeitada com a mensagem "Soma das apropriações excede o valor do pagamento"

  Cenário: Estorno devolve o saldo e zerar limpa a fonte herdada
    Dado um qualificador folha de despesa "2.8.4"
    E uma liberação confirmada de 1000.00 em "2038-09-05" no órgão "70002", qualificador "2.8.4" e fonte "1.580" da vigência 2038
    E um pagamento de 300.00 em "2038-09-05" no órgão "70002" e qualificador "2.8.4"
    E aproprio 300.00 dessa liberação nesse pagamento
    Quando estorno a última apropriação desse pagamento
    Então o saldo restante dessa liberação é 1000.00
    E o pagamento não referencia fonte alguma

  Cenário: Candidata de outra fonte é recusada (monofonte)
    Dado a fonte "1.581" cadastrada na vigência 2038 como "vinculada"
    E um qualificador folha de despesa "2.8.5"
    E uma liberação confirmada de 500.00 em "2038-09-06" no órgão "70002", qualificador "2.8.5" e fonte "1.580" da vigência 2038
    E um pagamento de 400.00 em "2038-09-06" no órgão "70002" e qualificador "2.8.5"
    E aproprio 200.00 dessa liberação nesse pagamento
    E uma liberação confirmada de 500.00 em "2038-09-06" no órgão "70002", qualificador "2.8.5" e fonte "1.581" da vigência 2038
    Quando aproprio 100.00 dessa liberação nesse pagamento
    Então a operação de pagamento é rejeitada com a mensagem "Pagamento é monofonte — liberação de fonte diferente da herdada"

  Cenário: Exclusão com apropriação é vetada
    Dado um qualificador folha de despesa "2.8.6"
    E uma liberação confirmada de 500.00 em "2038-09-07" no órgão "70002", qualificador "2.8.6" e fonte "1.580" da vigência 2038
    E um pagamento de 200.00 em "2038-09-07" no órgão "70002" e qualificador "2.8.6"
    E aproprio 200.00 dessa liberação nesse pagamento
    Quando tento excluir esse pagamento com confirmação explícita
    Então a operação de pagamento é rejeitada com a mensagem "Pagamento possui apropriações — estorne-as antes de excluir"

  Cenário: Reduzir valor abaixo do apropriado é recusado
    Dado um qualificador folha de despesa "2.8.7"
    E uma liberação confirmada de 500.00 em "2038-09-08" no órgão "70002", qualificador "2.8.7" e fonte "1.580" da vigência 2038
    E um pagamento de 500.00 em "2038-09-08" no órgão "70002" e qualificador "2.8.7"
    E aproprio 300.00 dessa liberação nesse pagamento
    Quando tento alterar o valor desse pagamento para 200.00
    Então a operação de pagamento é rejeitada com a mensagem "Valor não pode ficar abaixo do total já apropriado"

  Cenário: Pagamento sem apropriação é destacado na lista
    Dado um qualificador folha de despesa "2.8.8"
    E um pagamento de 77.00 em "2038-09-09" no órgão "70002" e qualificador "2.8.8"
    Quando abro a lista de pagamentos como administrador
    Então esse pagamento aparece com o destaque de sem apropriação
