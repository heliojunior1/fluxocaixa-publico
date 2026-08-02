# language: pt
Funcionalidade: Painel analítico do desembolso (F7.6)
  Como gestor do Tesouro, quero o liberado × pago × pendente por órgão,
  natureza e fonte, e a evolução do pendente — dentro do sistema, sem BI.

  Contexto:
    Dado que estou autenticado como administrador
    E um órgão "70014" chamado "Secretaria do Painel"
    E um qualificador folha de despesa "2.9.95"
    E a fonte "1.503" cadastrada na vigência 2059 como "livre"
    E a fonte "1.653" cadastrada na vigência 2059 como "vinculada"

  Cenário: Consolidação por órgão reusa a derivação do pendente
    Dado uma liberação confirmada de 1000.00 em "2059-03-10" no órgão "70014", qualificador "2.9.95" e fonte "1.503" da vigência 2059
    E uma apropriação de 300.00 sobre essa liberação em "2059-04-15"
    Quando abro o painel analítico de 2059
    Então a linha analítica do órgão "70014" mostra liberado 1000.00, pago 300.00 e pendente 700.00

  Cenário: Composição por natureza e por grupo de fonte fecha no liberado
    Dado uma liberação confirmada de 250.00 em "2059-05-10" no órgão "70014", qualificador "2.9.95", fonte "1.653" da vigência 2059 e natureza "J"
    Quando abro o painel analítico de 2059
    Então a composição por natureza mostra "D" com 80.00% e "J" com 20.00%
    E a composição por grupo de fonte mostra "L" com 80.00% e "V" com 20.00%

  Cenário: Evolução do pendente reage aos eventos mês a mês
    Quando abro o painel analítico de 2059
    Então o pendente acumulado do mês 3 de 2059 é 1000.00
    E o pendente acumulado do mês 4 de 2059 é 700.00
    E o pendente acumulado do mês 5 de 2059 é 950.00
