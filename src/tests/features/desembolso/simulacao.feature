# language: pt
Funcionalidade: Simulação de disponibilidade por grupo de fonte (F7.2)
  Como Tesouro, quero ver a curva projetada do grupo antes de confirmar o
  lote — modo prudente exclui receita não classificada, o estouro bloqueia,
  o colchão exige justificativa e a decisão fica gravada em snapshot.

  Contexto:
    Dado que estou autenticado como administrador
    E um órgão "70003" chamado "Secretaria da Simulação"
    E a fonte "1.595" cadastrada na vigência 2040 como "livre"
    E a fonte "1.695" cadastrada na vigência 2040 como "vinculada"
    E um qualificador folha de receita "1.9.21" repartido 100% na fonte "1.595" da vigência 2040
    E um qualificador folha de receita "1.9.22" sem repartição
    E um qualificador folha de despesa "2.9.21"
    E um cenário publicado "CEN F72" para 2040 com receita mensal de 100.00 em "1.9.21", receita mensal de 50.00 em "1.9.22" e despesa mensal de 80.00 em "2.9.21"

  Cenário: Prudente exclui o não classificado; informativo inclui
    Quando simulo o grupo "L" no modo "prudente" de 2040 a partir do mês 1 por 3 meses
    Então as receitas do mês 1 são 100.00
    E o total não classificado é 150.00
    Quando simulo o grupo "L" no modo "informativo" de 2040 a partir do mês 1 por 3 meses
    Então as receitas do mês 1 são 150.00

  Cenário: Anti-dupla contagem com piso zero
    Dado uma liberação confirmada de 150.00 no órgão "70003", qualificador "2.9.21", fonte "1.595" da vigência 2040, prevista para "2040-03-15"
    Quando simulo o grupo "L" no modo "prudente" de 2040 a partir do mês 2 por 3 meses
    Então as despesas ajustadas do mês 3 são 0.00
    E o pendente do mês 3 é 150.00
    E as despesas ajustadas do mês 4 são 80.00

  Cenário: Curva negativa bloqueia a confirmação
    Dado o colchão do grupo "V" definido como 0.00
    E uma liberação em rascunho de 999999999999.00 no órgão "70003", qualificador "2.9.21", fonte "1.695" da vigência 2040, prevista para "2040-03-15"
    Quando simulo o grupo "V" no modo "prudente" de 2040 a partir do mês 2 por 3 meses
    Então o veredicto é "BLOQUEIO"
    Quando confirmo o lote do grupo "V" de 2040 a partir do mês 2
    Então a operação de simulação é rejeitada com a mensagem "Caixa insuficiente — a curva fica negativa; confirmação bloqueada"
    E cancelo essa liberação de teste

  Cenário: Abaixo do colchão exige justificativa e acusa insuficiência estrutural
    Dado um saldo de 1000000.00 num fundo da fonte "1.695" da vigência 2040 em "2040-01-15"
    E o colchão do grupo "V" definido como 999999999999.00
    E uma liberação em rascunho de 10.00 no órgão "70003", qualificador "2.9.21", fonte "1.695" da vigência 2040, prevista para "2040-03-15"
    Quando simulo o grupo "V" no modo "prudente" de 2040 a partir do mês 2 por 3 meses
    Então o veredicto é "ALERTA"
    E a simulação acusa insuficiência estrutural
    Quando confirmo o lote do grupo "V" de 2040 a partir do mês 2
    Então a operação de simulação é rejeitada com a mensagem "Abaixo do colchão mínimo — confirmar exige justificativa registrada"
    Quando confirmo o lote do grupo "V" de 2040 a partir do mês 2 com a justificativa "repasse confirmado para o mês seguinte"
    Então o lote foi confirmado com snapshot

  Cenário: Modo informativo não confirma
    Dado uma liberação em rascunho de 10.00 no órgão "70003", qualificador "2.9.21", fonte "1.695" da vigência 2040, prevista para "2040-04-15"
    Quando confirmo o lote do grupo "V" de 2040 no modo "informativo"
    Então a operação de simulação é rejeitada com a mensagem "Confirmação de lote exige o modo prudente (autorizativo)"

  Cenário: Confirmação OK grava snapshot e eventos referenciados
    Dado um saldo de 500000.00 num fundo da fonte "1.695" da vigência 2040 em "2040-01-16"
    E o colchão do grupo "V" definido como 0.00
    E uma liberação em rascunho de 20.00 no órgão "70003", qualificador "2.9.21", fonte "1.695" da vigência 2040, prevista para "2040-05-15"
    Quando confirmo o lote do grupo "V" de 2040 a partir do mês 5
    Então o lote foi confirmado com snapshot
    E essa liberação está confirmada com evento referenciando o snapshot
