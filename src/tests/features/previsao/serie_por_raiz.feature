# language: pt
Funcionalidade: Série histórica costurada pela identidade estável
  Spec `previsao` R17 (change serie-historica-por-raiz, F10.2): a série
  histórica da previsão é consultada pela `cod_rubrica_raiz`, nunca pelo
  `seq_qualificador` — renumeração entre exercícios não trunca a série (C2)
  e código reutilizado não contamina (C6). Série insuficiente é erro de
  negócio citando a contagem (R14); o resultado declara o treino.

  Ramo "7.7", ilhas 2072/2073 (pares de exercício do roadmap F10.x).

  Cenário: Série atravessa a renumeração entre exercícios
    Dado a rubrica "7.7.1" no exercício 2072 com lançamento de 100.00 em 2072
    E o espelho renumerado "7.7.2" no exercício 2073 herdando a raiz de "7.7.1" com lançamento de 200.00 em 2073
    Quando consulto os dados históricos do espelho de 2073
    Então a série contém os anos 2072 e 2073

  Cenário: Código reutilizado não contamina a série
    Dado a rubrica "7.7.1" no exercício 2072 com lançamento de 100.00 em 2072
    E a rubrica nova "7.7.1" no exercício 2073 com raiz própria e lançamento de 50.00 em 2073
    Quando consulto os dados históricos da rubrica nova de 2073
    Então a série contém apenas o ano 2073

  Cenário: Rubrica sem histórico é erro explícito com a contagem
    Dado a rubrica "7.7.3" no exercício 2072 sem lançamentos
    Quando peço a projeção de média histórica da rubrica "7.7.3" de 2072
    Então a projeção é recusada citando "0 meses"

  Cenário: Resultado declara o tamanho da série treinada
    Dado a rubrica "7.7.1" no exercício 2072 com lançamento de 100.00 em 2072
    Quando peço a projeção de média histórica da rubrica "7.7.1" de 2072 para o ano seguinte
    Então o resultado declara os pontos e anos da série treinada
