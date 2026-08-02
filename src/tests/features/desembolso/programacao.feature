# language: pt
Funcionalidade: Programação de desembolso — cotas do decreto (F7.3b)
  Como Tesouro, quero importar as cotas do decreto de programação (LRF art.
  8º) com histórico preservado e precedência sobre a derivação da LOA.

  Contexto:
    Dado que estou autenticado como administrador
    E um órgão "70007" chamado "Secretaria da Programação"

  Cenário: Cota registrada com o ato
    Quando registro uma cota de 1000.00 para o órgão "70007" em 2045-03 com o ato "decreto-01"
    Então a cota vigente do órgão "70007" em 2045-03 é 1000.00

  Cenário: Revisão inativa a anterior e preserva o histórico
    Dado uma cota de 1000.00 para o órgão "70007" em 2045-04 com o ato "decreto-01"
    Quando registro uma cota de 1500.00 para o órgão "70007" em 2045-04 com o ato "decreto-02"
    Então a cota vigente do órgão "70007" em 2045-04 é 1500.00
    E existe 1 cota inativa do órgão "70007" em 2045-04

  Cenário: Mês programado vence a derivação da LOA no previsto
    Dado um qualificador folha de despesa "2.9.51" com LOA de 1200.00 no ano 2045
    E uma cota de 700.00 para o órgão "70007" em 2045-05 com o ato "decreto-03"
    Quando consulto o previsto mensal de 2045
    Então o previsto do mês 5 de 2045 é 700.00
    E o previsto do mês 6 de 2045 é 100.00

  Cenário: Cota sem ato é recusada
    Quando registro uma cota de 100.00 para o órgão "70007" em 2045-07 sem ato
    Então a operação de programação é rejeitada com a mensagem "Referência do ato (decreto/portaria) é obrigatória"
