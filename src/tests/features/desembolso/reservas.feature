# language: pt
Funcionalidade: Reservas financeiras e bloqueios judiciais (F7.4)
  Como Tesouro, quero segregar valores por decisão de gestão ou ordem
  judicial — com livro de eventos imutável, valor corrente derivado e a
  subtração única na simulação.

  Contexto:
    Dado que estou autenticado como administrador
    E a fonte "1.599" cadastrada na vigência 2044 como "vinculada"

  Cenário: Valor corrente deriva dos eventos
    Dado uma reserva administrativa de 1000.00 na fonte "1.599" da vigência 2044 vigente desde "2044-01-01"
    Quando reforço essa reserva em 500.00
    E reduzo essa reserva em 200.00
    Então o valor corrente dessa reserva é 1300.00

  Cenário: Administrativa acima do disponível exige confirmação
    Quando constituo uma reserva administrativa de 999999999999.00 na fonte "1.599" da vigência 2044 vigente desde "2044-01-01" sem confirmação
    Então a operação de reserva é rejeitada com a mensagem "Reserva acima do disponível do grupo exige confirmação explícita"

  Cenário: Bloqueio judicial nunca pede confirmação, só alerta
    Quando constituo um bloqueio judicial de 999999999999.00 na fonte "1.599" da vigência 2044 vigente desde "2044-01-01" com processo "0000000-00.2044"
    Então o bloqueio é registrado com alerta de grupo insuficiente
    E libero esse bloqueio com a ordem "oficio-de-desbloqueio-01"

  Cenário: Bloqueio judicial exige processo
    Quando constituo um bloqueio judicial de 100.00 na fonte "1.599" da vigência 2044 vigente desde "2044-01-01" sem processo
    Então a operação de reserva é rejeitada com a mensagem "Bloqueio judicial exige a referência do processo/ofício"

  Cenário: Liberar bloqueio exige a ordem
    Dado um bloqueio judicial de 300.00 na fonte "1.599" da vigência 2044 vigente desde "2044-01-01" com processo "0000001-00.2044"
    Quando libero esse bloqueio sem referência
    Então a operação de reserva é rejeitada com a mensagem "Evento de bloqueio judicial exige referência documental da ordem"
    E libero esse bloqueio com a ordem "oficio-de-desbloqueio-02"

  Cenário: Reserva vigente abate a simulação do grupo e liberada deixa de abater
    Dado uma reserva administrativa de 300.00 na fonte "1.599" da vigência 2044 vigente desde "2026-01-01"
    Então as reservas vigentes do grupo "V" hoje incluem 300.00
    Quando libero essa reserva
    Então as reservas vigentes do grupo "V" hoje não incluem mais os 300.00
