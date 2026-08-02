# language: pt
Funcionalidade: Disponibilidade por grupo de fonte (saldo bruto derivado)
  Como tesouraria, quero o saldo por grupo — livre, vinculado e pendente —
  derivado na leitura, com o fundo sem fonte fora do livre (conservador),
  para nunca superestimar o que posso usar.

  Contexto:
    Dado que estou autenticado como administrador

  Cenário: Fonte desconhecida em carga nasce vinculada e pendente
    Quando uma carga referencia a fonte desconhecida "899" na vigência 2034
    Então a fonte "1.899" da vigência 2034 existe vinculada e pendente de revisão

  Cenário: Fundo classificado como livre soma no grupo livre
    Dado uma conta de disponibilidade "001/0001/91001-1"
    E a fonte "1.520" cadastrada na vigência 2034 como "livre"
    E um fundo "9101" classificado na fonte "1.520" da vigência 2034
    E um saldo de 1234.56 do fundo "9101" nessa conta em "2034-05-10"
    Então o grupo "L" em "2034-05-10" soma 1234.56

  Cenário: Fundo sem fonte fica fora do livre e conta como pendente
    Dado uma conta de disponibilidade "001/0001/91002-2"
    E um fundo "9102" sem fonte de recursos
    E um saldo de 999.99 do fundo "9102" nessa conta em "2034-06-10"
    Então o grupo "L" em "2034-06-10" soma 0.00
    E o grupo "P" em "2034-06-10" soma 999.99

  Cenário: Soma dos grupos fecha com o agregado total
    Dado uma conta de disponibilidade "001/0001/91003-3"
    E a fonte "1.521" cadastrada na vigência 2034 como "livre"
    E a fonte "1.621" cadastrada na vigência 2034 como "vinculada"
    E um fundo "9103" classificado na fonte "1.521" da vigência 2034
    E um fundo "9104" classificado na fonte "1.621" da vigência 2034
    E um fundo "9105" sem fonte de recursos
    E um saldo de 100.00 do fundo "9103" nessa conta em "2034-07-10"
    E um saldo de 200.00 do fundo "9104" nessa conta em "2034-07-10"
    E um saldo de 300.00 do fundo "9105" nessa conta em "2034-07-10"
    Então a soma dos grupos em "2034-07-10" é igual ao agregado da conta em "2034-07-10"

  Cenário: Reclassificar o fundo muda o grupo imediatamente
    Dado uma conta de disponibilidade "001/0001/91004-4"
    E a fonte "1.522" cadastrada na vigência 2034 como "livre"
    E a fonte "1.622" cadastrada na vigência 2034 como "vinculada"
    E um fundo "9106" classificado na fonte "1.522" da vigência 2034
    E um saldo de 500.00 do fundo "9106" nessa conta em "2034-08-10"
    Quando reclassifico o fundo "9106" para a fonte "1.622" da vigência 2034
    Então o grupo "V" em "2034-08-10" soma 500.00
    E o grupo "L" em "2034-08-10" soma 0.00

  Cenário: Inativar fonte com fundo ativo é recusado
    Dado a fonte "1.523" cadastrada na vigência 2034 como "livre"
    E um fundo "9107" classificado na fonte "1.523" da vigência 2034
    Quando inativo a fonte "1.523" da vigência 2034
    Então a operação de fonte é rejeitada com a mensagem "Fonte possui fundos ativos classificados nela e não pode ser inativada"
    E a fonte "1.523" da vigência 2034 permanece ativa

  Cenário: Consulta do catálogo exige permissão
    Dado um usuário de fontes autenticado com o perfil "EXTRACAO"
    Quando esse usuário acessa a tela do catálogo de fontes
    Então o acesso à tela de fontes é negado

  Cenário: Tela do catálogo exibe a decomposição operacional
    Quando acesso a tela do catálogo de fontes como administrador
    Então a tela exibe a decomposição da disponibilidade operacional
