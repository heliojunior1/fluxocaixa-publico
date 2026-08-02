# language: pt
Funcionalidade: Funil LOA→caixa e conciliação (F8.3)
  Como Tesouro, quero ver as gradações do funil juntas e saber se o pago
  orçamentário e o desembolso financeiro contam a mesma história.

  Contexto:
    Dado que estou autenticado como administrador
    E um órgão "70010" chamado "Secretaria do Funil"

  Cenário: Funil integra as gradações
    Dado um qualificador folha de despesa "2.9.81" com dotação inicial de 2000.00 em 2054
    E um empenho "2054NE001" de 1000.00 em 2054 no órgão "70010" e qualificador "2.9.81"
    E a liquidação "2054NL001" de 800.00 em 2054 vinculada a "2054NE001"
    E o pagamento orçamentário "2054NP001" de 300.00 em 2054 vinculado à liquidação "2054NL001"
    Quando consulto o relatório do funil de 2054
    Então a linha do funil do qualificador "2.9.81" mostra autorizado 2000.00, empenhado 1000.00, liquidado 800.00, pago 300.00 e liquidado não pago 500.00

  Cenário: Autorizado cai para a LOA sem dotação
    Dado um qualificador folha de despesa "2.9.82" com LOA de 900.00 no ano 2054
    Quando consulto o relatório do funil de 2054
    Então a linha do funil do qualificador "2.9.82" mostra autorizado 900.00, empenhado 0.00, liquidado 0.00, pago 0.00 e liquidado não pago 0.00

  Cenário: Pago no orçamento sem desembolso registrado
    Dado um desembolso financeiro de 200.00 em "2054-03-15" no órgão "70010" e qualificador "2.9.81"
    Quando consulto a conciliação de 2054
    Então a conciliação do órgão "70010" mostra diferença 100.00 com a direção "pago no orçamento sem desembolso registrado"

  Cenário: Desembolso sem execução importada
    Dado um órgão "70011" chamado "Secretaria Só Caixa"
    E um desembolso financeiro de 150.00 em "2054-04-15" no órgão "70011" e qualificador "2.9.81"
    Quando consulto a conciliação de 2054
    Então a conciliação do órgão "70011" mostra diferença -150.00 com a direção "desembolso sem execução importada"
