# language: pt
Funcionalidade: Classificação do fundo por fonte de recursos (R21)
  Como tesouraria, quero classificar cada fundo na sua fonte — e ver
  destacado o que ainda não foi classificado, que fica fora do livre.

  Contexto:
    Dado que estou autenticado como administrador

  Cenário: Classificar um fundo estampa seu saldo no grupo
    Dado uma conta de disponibilidade "001/0001/92001-1"
    E a fonte "1.530" cadastrada na vigência 2034 como "livre"
    E um fundo "9201" sem fonte de recursos
    E um saldo de 1234.56 do fundo "9201" nessa conta em "2034-09-10"
    Quando reclassifico o fundo "9201" para a fonte "1.530" da vigência 2034
    Então o grupo "L" em "2034-09-10" soma 1234.56

  Cenário: Remover o vínculo devolve o fundo ao pendente
    Dado uma conta de disponibilidade "001/0001/92002-2"
    E a fonte "1.531" cadastrada na vigência 2034 como "livre"
    E um fundo "9202" classificado na fonte "1.531" da vigência 2034
    E um saldo de 700.00 do fundo "9202" nessa conta em "2034-10-10"
    Quando removo a classificação do fundo "9202"
    Então o grupo "P" em "2034-10-10" soma 700.00
    E o grupo "L" em "2034-10-10" soma 0.00

  Cenário: Fundo sem fonte aparece destacado na tela de fundos
    Dado um fundo "9203" sem fonte de recursos
    Quando acesso a tela de fundos como administrador
    Então o fundo "9203" aparece destacado como pendente de classificação

  Cenário: Classificar fundo em fonte inativa é recusado
    Dado a fonte "1.532" cadastrada na vigência 2034 como "livre"
    E a fonte "1.532" da vigência 2034 foi inativada
    E um fundo "9204" sem fonte de recursos
    Quando reclassifico o fundo "9204" para a fonte "1.532" da vigência 2034
    Então a operação de fonte é rejeitada com a mensagem "Fonte de recursos inexistente ou inativa"
