# language: pt
Funcionalidade: Modelos econométricos corrigidos
  Spec previsao R12 (change modelos-econometricos-corrigidos)

  Transformação de treino é revertida na projeção; mais de 12 períodos
  atravessa o calendário; fallback de modelo é visível no resultado;
  fórmula com parâmetro faltante falha explícito; validação de fórmula é
  só parse. Massa sintética — sem banco.

  Cenário: Deslocamento do Holt-Winters é revertido
    Dado uma série mensal de 24 pontos em torno de 100.00 com um mês negativo de -50.00
    Quando projeto com Holt-Winters sazonal multiplicativo
    Então a projeção fica na ordem de grandeza da série original

  Cenário: Mais de 12 períodos atravessa o calendário
    Dado uma série histórica mensal válida
    Quando projeto 24 períodos de média histórica com ano-base 2063
    Então as datas projetadas cobrem 2063 e 2064
    E nenhum erro de mês inválido é levantado

  Cenário: Fallback do modelo fica visível
    Dado que o treino do Holt-Winters configurado falhará
    Quando projeto com Holt-Winters sazonal multiplicativo
    Então o resultado carrega a degradação citando o fallback

  Cenário: Fórmula com parâmetro faltante falha explícito
    Dado a fórmula "base * (1 + ipca)" com base fixa de 1000.00
    Quando projeto com a fórmula sem informar "ipca"
    Então recebo erro de negócio citando "ipca"

  Cenário: Validação aceita fórmula com singularidade
    Quando valido a fórmula "base / (x - 1)"
    Então ela é aceita como sintaticamente válida
