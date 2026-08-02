# language: pt
Funcionalidade: Previsto da LOA e teto do autorizado (F7.3a)
  Como Tesouro, quero o previsto derivado da LOA na visão de liberações e o
  teto do autorizado como alerta consciente na confirmação.

  Contexto:
    Dado que estou autenticado como administrador
    E um órgão "70006" chamado "Secretaria do Previsto"
    E a fonte "1.598" cadastrada na vigência 2043 como "livre"

  Cenário: Previsto mensal com fallback 1/12
    Dado um qualificador folha de despesa "2.9.41" com LOA de 1200.00 no ano 2043
    Quando consulto o previsto mensal de 2043
    Então o previsto do mês 5 de 2043 é 100.00

  Cenário: Previsto mensal segue o perfil do realizado do ano anterior
    Dado um qualificador folha de despesa "2.9.42" com LOA de 1200.00 no ano 2053
    E uma saída realizada de 999.00 em "2052-03-15" no qualificador "2.9.42"
    Quando consulto o previsto mensal de 2053
    Então o previsto do mês 3 de 2053 é 1200.00
    E o previsto do mês 4 de 2053 é 0.00

  Cenário: Exceder o teto exige confirmação explícita e registra o excedente
    Dado um qualificador folha de despesa "2.9.43" com LOA de 1000.00 no ano 2043
    E uma liberação confirmada de 900.00 em "2043-04-10" no órgão "70006", qualificador "2.9.43" e fonte "1.598" da vigência 2043
    E uma liberação em rascunho de 200.00 em "2043-04-11" no órgão "70006", qualificador "2.9.43" e fonte "1.598" da vigência 2043
    Quando confirmo essa liberação sem confirmação explícita do teto
    Então a operação do teto é rejeitada com a mensagem "Liberação excede o autorizado do exercício em R$ 100.00 — confirme explicitamente para prosseguir"
    Quando confirmo essa liberação com confirmação explícita do teto
    Então essa liberação está confirmada e o evento registra o excedente "Teto do autorizado excedido em R$ 100.00"

  Cenário: Sem LOA não há teto
    Dado um qualificador folha de despesa "2.9.44"
    E uma liberação em rascunho de 50000.00 em "2043-05-10" no órgão "70006", qualificador "2.9.44" e fonte "1.598" da vigência 2043
    Quando confirmo essa liberação sem confirmação explícita do teto
    Então essa liberação está confirmada sem exigência extra
