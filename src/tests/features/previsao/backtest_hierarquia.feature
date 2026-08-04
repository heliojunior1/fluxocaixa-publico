# language: pt
Funcionalidade: Backtest com métrica zero visível e agregação profunda
  Spec previsao R16 (change backtest-metricas-e-hierarquia-profunda)

  Viés 0.0 é MEDIÇÃO, não ausência; e a agregação por pai alcança as
  folhas em qualquer profundidade — antes o pai de nível 1 só via os
  filhos diretos de nível 2 (sem lançamentos) e ficava vazio.
  Treino 2062 / teste 2063, isolado por qualificadores_ids.

  Cenário: Viés zero aparece como zero
    Dado uma recomendação de backtest gravada com viés zero
    Quando leio as recomendações do backtest
    Então o viés da recomendação é 0.0, não ausência

  Cenário: Ancestral de nível 1 agrega folha de nível 3
    Dado uma árvore "1.75" com bloco "1.75.1" e folha "1.75.1.1" com histórico
    Quando executo o backtest da folha com média histórica
    Então o agregado do bloco "1.75.1" contém métricas
    E o agregado da raiz "1.75" também contém métricas
