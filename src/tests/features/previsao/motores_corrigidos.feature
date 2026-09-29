# language: pt
Funcionalidade: Motores de previsão corrigidos
  Spec previsao R12, R17, R18 e R19 (change corrigir-motores-de-previsao)

  A série mensal é regular (mês fechado sem movimento vale zero, mês ainda
  não ocorrido não entra) e a previsão é datada no mês que o modelo de fato
  previu; o crescimento atravessa a abertura de exercício pela raiz e trata o
  estorno como redução; sazonalidade só com dois ciclos; o ARIMA automático
  não compara diferenciações; os modelos de aprendizado de máquina não veem o
  próprio alvo e usam as defasagens certas na previsão recursiva.
  Ilhas 2081–2086, ramo de qualificador "8.9".

  Cenário: Série curta roda sem sazonalidade e avisa
    Dado uma série mensal de 12 meses com pico de 200.00 em dezembro e 50.00 nos demais
    Quando projeto 12 meses de 2085 com Holt-Winters sazonal
    Então a projeção não tem padrão sazonal
    E o resultado carrega a degradação citando "24 meses"

  Cenário: SARIMA com série curta não aplica diferença sazonal
    Dado uma série mensal de 18 meses em torno de 1234.56
    Quando projeto 12 meses de 2085 com SARIMA sazonal
    Então o resultado carrega a degradação citando "24 meses"

  Cenário: Seleção automática do ARIMA mantém a diferenciação configurada
    Dado uma série mensal de 36 meses em torno de 1234.56
    Quando projeto 12 meses de 2085 com ARIMA automático e diferenciação 1
    Então a ordem escolhida tem diferenciação 1

  Cenário: Crescimento atravessa a abertura de exercício
    Dado a rubrica "8.9" com 100.00 por mês no plano de 2083 e 110.00 por mês de janeiro a junho no plano de 2084, com a mesma raiz
    Quando projeto 2084 com o crescimento sobre 2083 e mês de referência 6 pela folha do plano de 2084
    Então cada mês de julho a dezembro é projetado em 110.00
    E o total do ano é 1320.00

  Cenário: Estorno reduz o acumulado do crescimento
    Dado a rubrica "8.9" de receita com crédito de 1000.00 e estorno de 200.00 em março de 2083
    Quando calculo o acumulado de março de 2083 para o crescimento
    Então o acumulado é 800.00

  Cenário: Mês fechado sem movimento entra como zero
    Dado a rubrica "8.9" com 1234.56 em todos os meses de 2083 exceto março
    Quando obtenho a série mensal de 2083 com execução em 2085-01-10
    Então a série tem 12 pontos
    E o ponto de março de 2083 vale 0.00

  Cenário: Mês ainda não ocorrido não entra na série
    Dado a rubrica "8.9" com 1234.56 em todos os meses de 2082 e de janeiro a setembro de 2084
    Quando obtenho a série para o ano-base 2085 com janela de 3 anos e execução em 2084-10-15
    Então o último ponto da série é setembro de 2084
    E o ponto de março de 2083 vale 0.00

  Cenário: Pico sazonal fica no mês certo quando o ano anterior está incompleto
    Dado uma série de janeiro de 2082 a setembro de 2084 com 100.00 em dezembro e 10.00 nos demais meses
    Quando projeto 12 meses de 2085 com Holt-Winters sazonal
    Então o maior valor projetado está em dezembro de 2085

  Cenário: Janela começa em 1º de janeiro
    Dado a rubrica "8.9" com 500.00 em 2081-12-31 e 1234.56 em 2082-06-15
    Quando obtenho a série para o ano-base 2085 com janela de 3 anos e execução em 2086-01-10
    Então o primeiro ponto da série é junho de 2082

  Cenário: Atributos do treino não contêm o alvo
    Dado uma série mensal de 36 meses com valores 1.00 a 36.00
    Quando altero o valor do mês 18 para 999.00
    Então nenhum atributo de treino do mês 18 muda

  Cenário: Defasagens corretas na previsão recursiva
    Dado uma série mensal de 36 meses com valores 1.00 a 36.00
    Quando monto os atributos do mês seguinte a duas previsões de 100.00 e 101.00
    Então a defasagem 1 é 101.00, a defasagem 2 é 100.00 e a defasagem 3 é 36.00

  Cenário: Série constante é projetada constante
    Dado uma série mensal de 36 meses com 1234.56 em todos os meses
    Quando projeto 12 meses de 2085 com XGBoost
    Então todos os meses projetados ficam a menos de 1% de 1234.56

  Cenário: Mínimo de 14 meses
    Dado uma série mensal de 13 meses em torno de 1234.56
    Quando projeto 12 meses de 2085 com LightGBM
    Então recebo erro de negócio citando "13" e "14"
