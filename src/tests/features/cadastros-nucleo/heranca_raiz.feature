# language: pt
Funcionalidade: Herança da identidade estável na criação
  Spec `cadastros-nucleo` R30 (change heranca-rubrica-raiz, F10.5): nos
  cenários em que a resposta não é automática — desdobramento (C3), fusão
  (C4) e reativação (C7) — a decisão humana fica registrada herdando a
  `cod_rubrica_raiz` na criação. Uma raiz por exercício entre ativos; a
  série do herdeiro atravessa a herança.

  Ramo "7.11", ilhas 2090/2091.

  Contexto:
    Dado a rubrica de origem "7.11" chamada "Material De Consumo Ilha" no exercício 2090 com lançamento de 300.00

  Cenário: Herdeira enxerga a série da rubrica de origem
    Quando crio "7.11" chamada "Material De Expediente Ilha" no exercício 2091 herdando a raiz da origem
    Então a série histórica da herdeira contém o lançamento de 2090

  Cenário: Irmã sem herança nasce zerada
    Quando crio "7.11" chamada "Material Hospitalar Ilha" no exercício 2091 sem herdar raiz
    Então a rubrica criada tem raiz própria e série vazia

  Cenário: Raiz em uso por ativo do mesmo exercício é recusada
    Quando crio "7.11" chamada "Material De Expediente Ilha" no exercício 2091 herdando a raiz da origem
    E tento criar "7.12" chamada "Material Duplicado Ilha" no exercício 2091 herdando a raiz da origem
    Então a criação é recusada com mensagem contendo "raiz"

  Cenário: Raiz inexistente é recusada
    Quando tento criar "7.12" chamada "Material Fantasma Ilha" no exercício 2091 herdando a raiz 99999999
    Então a criação é recusada com mensagem contendo "raiz"

  Cenário: Reativação retoma a série
    Dado a rubrica de origem inativada
    Quando crio "7.13" chamada "Material Reativado Ilha" no exercício 2090 herdando a raiz da origem
    Então a série histórica da herdeira contém o lançamento de 2090
