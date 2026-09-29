# language: pt
Funcionalidade: Backtest mede o que a produção faz
  Spec previsao R16 (change corrigir-motores-de-previsao)

  Série e realizado em magnitude; cada ano de teste previsto só com dados
  até o ano anterior; a mesma rubrica uma vez só, mesmo em vários
  exercícios; o crescimento é reprojeção intra-ano — nunca recebe o
  realizado que avalia e não disputa o melhor modelo.
  Ilhas 2081–2084, ramo de qualificador "8.8".

  Cenário: Despesa é avaliada em magnitude
    Dado uma folha de despesa com 1234.56 por mês de 2081 a 2083
    Quando executo o backtest com média histórica treinando em 2081 e 2082 e testando 2083
    Então o erro percentual da média histórica é 0.00
    E a projeção de 2083 não é zero

  Cenário: Crescimento não recebe o realizado que avalia
    Dado uma folha de receita com 100.00 por mês em 2082 e 150.00 por mês em 2083
    Quando executo o backtest com média histórica e crescimento, mês de referência 6, treinando em 2082 e testando 2083
    Então o crescimento é medido apenas nos meses 7 a 12
    E o crescimento aparece na reprojeção intra-ano
    E o melhor modelo não é o crescimento
    E o ranking geral não contém o crescimento

  Cenário: Cada ano de teste tem a sua projeção
    Dado uma folha de receita com 100.00 por mês em 2081, 200.00 em 2082, 300.00 em 2083 e 400.00 em 2084
    Quando executo o backtest com média histórica treinando em 2081 e 2082 e testando 2083 e 2084
    Então a projeção de janeiro comparada com 2083 é 150.00
    E a projeção de janeiro comparada com 2084 é 200.00

  Cenário: Rubrica em dois exercícios aparece uma vez
    Dado a mesma folha de receita nos planos de 2083 e 2084, com a mesma raiz e histórico
    Quando executo o backtest com média histórica das duas linhas treinando em 2082 e testando 2083
    Então a rubrica aparece uma única vez no resultado
