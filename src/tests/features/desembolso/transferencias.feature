# language: pt
Funcionalidade: Transferências internas (registro de controle)
  Como Tesouro, quero registrar o par de transferência entre contas próprias
  para a conciliação classificar a saída como neutra — sem falso positivo de
  ordem judicial.

  Contexto:
    Dado que estou autenticado como administrador
    E uma conta de transferência "001/0001/TRF-1"
    E uma conta de transferência "001/0001/TRF-2"

  Cenário: Registro válido entra no total do dia
    Quando registro uma transferência de 1234.56 de "001/0001/TRF-1" para "001/0001/TRF-2" em "2041-02-10"
    Então o total de transferências de "2041-02-10" é 1234.56

  Cenário: Origem igual ao destino é recusada
    Quando registro uma transferência de 100.00 de "001/0001/TRF-1" para "001/0001/TRF-1" em "2041-02-11"
    Então a operação de transferência é rejeitada com a mensagem "Origem e destino da transferência devem ser diferentes"

  Cenário: Valor não positivo é recusado
    Quando registro uma transferência de 0.00 de "001/0001/TRF-1" para "001/0001/TRF-2" em "2041-02-12"
    Então a operação de transferência é rejeitada com a mensagem "Valor da transferência deve ser positivo"

  Cenário: Inativada sai do total do dia
    Quando registro uma transferência de 500.00 de "001/0001/TRF-1" para "001/0001/TRF-2" em "2041-02-13"
    E inativo essa transferência
    Então o total de transferências de "2041-02-13" é 0.00
