# language: pt
Funcionalidade: Série histórica única da previsão
  Spec previsao R11 (change serie-historica-unica-previsao)

  A série que alimenta fórmulas, modelos econométricos e modelos de
  crescimento considera SOMENTE lançamentos ativos — a mesma série do
  backtest —, e falha de banco vira erro explícito, nunca projeção zero
  com cara de dado apurado. Ilha de datas 2063.

  Contexto:
    Dado um qualificador folha de série histórica

  Cenário: Lançamento excluído fica fora da base da fórmula
    Dado lançamentos ativos de 100.00 e 200.00 em março de 2063
    E um lançamento inativo de 999.00 em março de 2063
    Quando calculo a base de março por média simples do ano 2063
    Então a base é 300.00

  Cenário: Lançamento excluído fica fora da série dos modelos
    Dado lançamentos ativos de 100.00 e 200.00 em março de 2063
    E um lançamento inativo de 999.00 em março de 2063
    Quando obtenho os dados históricos do qualificador em 2063
    Então a série soma 300.00

  Cenário: Lançamento excluído fica fora do acumulado de crescimento
    Dado lançamentos ativos de 100.00 e 200.00 em março de 2063
    E um lançamento inativo de 999.00 em março de 2063
    Quando calculo a soma acumulada de janeiro a dezembro de 2063
    Então o acumulado é 300.00

  Cenário: Falha de banco não vira projeção zero
    Dado que a consulta de valores históricos falhará com erro de banco
    Quando calculo a base de março por média simples do ano 2063
    Então a chamada levanta erro explícito
