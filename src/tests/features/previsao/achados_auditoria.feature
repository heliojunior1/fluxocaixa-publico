# language: pt
Funcionalidade: Achados da auditoria da previsão
  Change corrigir-achados-auditoria-previsao — spec previsao R22–R29 e
  cadastros-nucleo R30. Cada cenário reproduz um contraexemplo conferido da
  auditoria de 29/09/2026 (A2–A9 e limites do backtest).
  Ilha: exercícios 2121–2124, receita "1.83", despesa "2.83".

  Cenário: Cenário anual com média histórica
    Dado uma despesa com saída de "100.00" em todos os meses de 2121 a 2123
    Quando executo um cenário "ANUAL" de 2124 com 1 período e média histórica na despesa
    Então a projeção tem 1 período, todos em 2124, somando "1200.00"

  Cenário: Cenário quinzenal com média histórica
    Dado uma despesa com saída de "100.00" em todos os meses de 2121 a 2123
    Quando executo um cenário "QUINZENAL" de 2124 com 24 períodos e média histórica na despesa
    Então a projeção tem 24 períodos, todos em 2124, somando "1200.00"

  Cenário: Média de crescimento com taxas diferentes conserva o total
    Dado uma receita com realizado mensal
      | ano  | jan_jun | jul_dez |
      | 2121 | 50.00   | 150.00  |
      | 2122 | 150.00  | 50.00   |
      | 2123 | 100.00  |         |
    Quando projeto 2123 por média de crescimento de 2121 e 2122 com referência em junho
    Então a soma dos doze meses é "1600.00"
    E janeiro a junho valem "100.00"

  Cenário: Período-base de 12 meses repete o último ano
    Dado uma série de 24 meses de "100.00" seguidos de 12 meses de "300.00"
    Quando projeto por média histórica sazonal com período-base de 12 meses
    Então todos os meses projetados valem "300.00"

  Cenário: LightGBM aprende tendência e sazonalidade
    Dado a série de 36 meses com tendência e sazonalidade
    Quando projeto 12 meses com LightGBM
    Então a projeção não é constante

  Cenário: LightGBM sem divisão possível é declarado
    Dado uma série de 14 meses de "100.00" com um pico de "500.00" no último mês
    Quando projeto 12 meses com LightGBM
    Então o resultado declara a degradação "sem divisões"

  Cenário: SARIMA usa a mesma janela nas três portas
    Quando consulto a janela do SARIMA nas três portas
    Então as três usam 4 anos

  Cenário: Backtest com ano de teste em curso mede só meses encerrados
    Dado uma receita com entrada de "100.00" em todos os meses de 2121 a 2124
    Quando executo o backtest de 2124 com média histórica e data de corte "2124-09-20"
    Então os meses medidos de 2124 são de janeiro a agosto
    E o resultado informa a data de corte "2124-09-20"

  Cenário: Erro em mês de realizado zero pesa na escolha
    Dado o realizado "100.00;0.00"
    E o modelo "A" com previsão "100.00;1000.00" e o modelo "B" com "110.00;0.00"
    Quando comparo os modelos
    Então o WMAPE de "A" é "1000.00" e o de "B" é "10.00"
    E o melhor modelo é "B"

  Cenário: Realizado todo zero mantém o MAE
    Dado o realizado "0.00;0.00"
    E o modelo "A" com previsão "10.00;30.00" e o modelo "B" com "40.00;40.00"
    Quando comparo os modelos
    Então o WMAPE de "A" é nulo e o MAE é "20.00"
    E o melhor modelo é "A"

  Cenário: Modelo degradado não é recomendado
    Dado o realizado "100.00;100.00"
    E o modelo "SARIMA" com previsão "100.00;100.00" e o modelo "HOLT_WINTERS" com "90.00;90.00"
    E o modelo "SARIMA" caiu para o fallback
    Quando comparo os modelos
    Então o melhor modelo é "HOLT_WINTERS"

  Cenário: Modelo com menos anos de teste não concorre
    Dado o realizado "100.00;100.00"
    E o modelo "A" com previsão "100.00;100.00" e o modelo "B" com "90.00;90.00"
    E o modelo "A" foi medido em 1 ano e o modelo "B" em 2 anos
    Quando comparo os modelos
    Então o melhor modelo é "B"

  Cenário: Métrica do pai é a da série somada
    Dado a folha "F1" com realizado "100.00;100.00" e previsão "150.00;150.00"
    E a folha "F2" com realizado "1000.00;1000.00" e previsão "1000.00;1000.00"
    Quando agrego o pai das duas folhas
    Então o WMAPE do pai é "4.55"

  Cenário: Previsão × Realizado usa a base do exercício anterior pela raiz
    Dado uma receita do plano de 2121 com "100.00" em cada mês de 2121
    E a mesma rubrica, herdada, no plano de 2122
    Quando consulto Previsão × Realizado de 2122 para a rubrica de 2122 sem cenário
    Então a previsão inicial soma "1200.00"

  Cenário: Despesa não herda raiz de receita
    Dado uma receita do plano de 2121 com "100.00" em cada mês de 2121
    Quando uma despesa do plano de 2122 tenta herdar a raiz da receita
    Então a operação é recusada citando a natureza

  Cenário: Mover nó para árvore de outra natureza é recusado
    Dado uma receita do plano de 2121 com "100.00" em cada mês de 2121
    E a mesma rubrica, herdada, no plano de 2122
    E uma despesa "2.83" no plano de 2122
    Quando reaponto a rubrica de 2122 para a despesa
    Então a operação é recusada citando a natureza
