# language: pt
Funcionalidade: Importação de saldos em lote idempotente
  Como sistema de extração (embutido ou ETL externo), quero entregar lotes de
  saldos com tolerância a erro pontual, auto-cadastro de fundos e resultado
  auditável — sem nunca duplicar a chave (conta, fundo, dia).

  Contexto:
    Dado que estou autenticado como administrador

  Cenário: Lote misto com erro pontual
    Dado uma conta de lote "066/0001/100-1"
    E uma conta de lote "066/0001/100-2"
    E um fundo importável "6001"
    Quando importo um lote com as linhas:
      | conta          | fundo | valor   |
      | 066/0001/100-1 | 6001  | 1000.00 |
      | 066/0001/100-2 | 6001  | 2000.00 |
      | 066/9999/999-9 | 6001  | 3000.00 |
    Então o resultado informa 2 inseridas e 1 com erro
    E o detalhe de erros aponta a linha 3

  Cenário: Reimportar o mesmo lote é idempotente
    Dado uma conta de lote "066/0001/200-1"
    E um fundo importável "6002"
    E um lote já importado com "1000.00" para a conta "066/0001/200-1" e fundo "6002"
    Quando importo um lote com "1200.00" para a conta "066/0001/200-1" e fundo "6002"
    Então a chave da conta "066/0001/200-1" e fundo "6002" tem 1 linha ativa com "1200.00"
    E a chave da conta "066/0001/200-1" e fundo "6002" tem 1 linha inativa com "1000.00"

  Cenário: Duplicata dentro do mesmo lote — última vence
    Dado uma conta de lote "066/0001/300-1"
    E um fundo importável "6003"
    Quando importo um lote com as linhas:
      | conta          | fundo | valor  |
      | 066/0001/300-1 | 6003  | 100.00 |
      | 066/0001/300-1 | 6003  | 200.00 |
    Então a chave da conta "066/0001/300-1" e fundo "6003" tem 1 linha ativa com "200.00"

  Cenário: Fundo desconhecido é auto-cadastrado conforme a origem
    Dado uma conta de lote "066/0001/400-1"
    E um sistema de origem "SIS_LOTE" cadastrado
    Quando importo um lote da origem "SIS_LOTE" com o fundo inexistente "9001" para a conta "066/0001/400-1"
    Então o fundo "9001" existe pendente, com origem "AUTOMATIZADO", sistema "SIS_LOTE" e data de auto-cadastro
    E o resultado lista "9001" nos fundos auto-cadastrados

  Cenário: Sem origem, fundo desconhecido nasce IMPORTADO
    Dado uma conta de lote "066/0001/500-1"
    Quando importo um lote sem origem com o fundo inexistente "9002" para a conta "066/0001/500-1"
    Então o fundo "9002" existe pendente, com origem "IMPORTADO" e sem sistema

  Cenário: Upsert direto sem sistema nasce IMPORTADO
    Quando o upsert de fundo é chamado para "7779" sem sistema de origem
    Então o fundo "7779" existe pendente, com origem "IMPORTADO" e sem sistema

  Cenário: Lote vazio é sucesso
    Quando importo um lote sem linhas
    Então o resultado informa 0 inseridas e 0 com erro

  Cenário: Sistema de origem inválido é erro de chamada
    Dado uma conta de lote "066/0001/600-1"
    Quando importo um lote da origem "NAO_EXISTE" com o fundo inexistente "9003" para a conta "066/0001/600-1"
    Então a importação é rejeitada com a mensagem "Sistema de origem 'NAO_EXISTE' não encontrado ou inativo"
    E o fundo "9003" não existe

  Cenário: Falha sistêmica identificável
    Quando importo um lote com as linhas:
      | conta          | fundo | valor  |
      | 066/8888/888-8 | 6001  | 100.00 |
      | 066/8888/888-9 | 6001  | 200.00 |
    Então o resultado indica falha sistêmica

  Cenário: EXTRACAO importa pelo endpoint HTTP
    Dado uma conta de lote "066/0001/700-1"
    E um fundo importável "6007"
    E um cliente HTTP autenticado com o perfil "EXTRACAO"
    Quando o cliente envia ao endpoint um lote com valSaldo "1234.56" para a conta "066/0001/700-1" e fundo "6007"
    Então a resposta HTTP é 200 com linhasInseridas 1
    E a chave da conta "066/0001/700-1" e fundo "6007" tem 1 linha ativa com "1234.56"

  Cenário: Perfil sem a permissão recebe 403 no endpoint
    Dado um cliente HTTP autenticado com o perfil "CONSULTA"
    Quando o cliente envia ao endpoint um lote qualquer
    Então a resposta HTTP é 403 em JSON

  Cenário: Cliente não autenticado recebe 401 no endpoint
    Quando um cliente anônimo envia ao endpoint um lote qualquer
    Então a resposta HTTP é 401 em JSON
