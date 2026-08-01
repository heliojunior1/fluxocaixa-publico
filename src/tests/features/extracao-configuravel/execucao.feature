# language: pt
Funcionalidade: Execução de fontes de extração com registro auditável
  Spec extracao-configuravel R3, R4, R6, R7, R8 e R9 (change infra-extracao-agendador)

  Contexto:
    Dado que estou autenticado como administrador
    E um sistema de origem "SIS_X" cadastrado
    E o conector de teste "FAKE" registrado
    E uma conta extraível "001/0001/11111-1"
    E um fundo extraível "9999"

  Cenário: Execução com todas as linhas válidas é SUCESSO
    Dado uma fonte "Fonte Sucesso" do tipo "FAKE"
    E que o conector devolve saldos válidos de "100.00" para 3 dias na conta "001/0001/11111-1" e fundo "9999"
    Quando executo a fonte "Fonte Sucesso"
    Então a execução registra status "SUCESSO" com 3 inseridas e 0 com erro

  Cenário: Lote com erro pontual é PARCIAL
    Dado uma fonte "Fonte Parcial" do tipo "FAKE"
    E que o conector devolve saldos válidos de "100.00" para 2 dias na conta "001/0001/11111-1" e fundo "9999"
    E que o conector devolve também um saldo para a conta inexistente "999/9999/00000-0"
    Quando executo a fonte "Fonte Parcial"
    Então a execução registra status "PARCIAL" com 2 inseridas e 1 com erro
    E o detalhe de erros da execução menciona "999/9999/00000-0"

  Cenário: Falha sistêmica do lote é ERRO
    Dado uma fonte "Fonte Sistemica" do tipo "FAKE"
    E que o conector devolve também um saldo para a conta inexistente "999/9999/00000-0"
    Quando executo a fonte "Fonte Sistemica"
    Então a execução registra status "ERRO" com 0 inseridas e 1 com erro

  Cenário: Janela sem dados é SEM_DADOS, não falha
    Dado uma fonte "Fonte Vazia" do tipo "FAKE"
    Quando executo a fonte "Fonte Vazia"
    Então a execução registra status "SEM_DADOS" com 0 inseridas e 0 com erro

  Cenário: Exceção do conector vira ERRO com detalhe
    Dado uma fonte "Fonte Quebrada" do tipo "FAKE"
    E que o conector está configurado para falhar com "falha de conexão simulada"
    Quando executo a fonte "Fonte Quebrada"
    Então a execução registra status "ERRO" com 0 inseridas e 0 com erro
    E o detalhe de erros da execução menciona "falha de conexão simulada"

  Cenário: Saldo extraído grava com origem da fonte
    Dado uma fonte "Fonte Origem" do tipo "FAKE"
    E que o conector devolve um saldo de "1234.56" para a conta "001/0001/11111-1" e fundo "9999"
    Quando executo a fonte "Fonte Origem"
    Então o saldo ativo da conta "001/0001/11111-1" e fundo "9999" vale "1234.56" com tipo "AUTOMATIZADO" e sistema "SIS_X"

  Cenário: Reexecução da mesma janela é idempotente
    Dado uma fonte "Fonte Reexec" do tipo "FAKE"
    E que o conector devolve um saldo de "1000.00" para a conta "001/0001/11111-1" e fundo "9999"
    E que executei a fonte "Fonte Reexec"
    E que o conector devolve um saldo de "1200.00" para a conta "001/0001/11111-1" e fundo "9999"
    Quando executo a fonte "Fonte Reexec"
    Então o saldo ativo da conta "001/0001/11111-1" e fundo "9999" passa a valer "1200.00"
    E existe saldo inativo de "1000.00" para a conta "001/0001/11111-1" e fundo "9999"

  Cenário: Executar agora pelo endpoint registra execução MANUAL
    Dado uma fonte "Fonte Manual" do tipo "FAKE"
    E que o conector devolve um saldo de "500.00" para a conta "001/0001/11111-1" e fundo "9999"
    E um cliente HTTP autenticado com o perfil "EXTRACAO"
    Quando o cliente chama o endpoint de execução da fonte "Fonte Manual" sem janela
    Então a resposta HTTP é 200 com status "SUCESSO"
    E a última execução da fonte "Fonte Manual" tem disparo "MANUAL" e janela do dia corrente

  Cenário: Janela maior que 90 dias é rejeitada
    Dado uma fonte "Fonte Janela Grande" do tipo "FAKE"
    E um cliente HTTP autenticado com o perfil "EXTRACAO"
    Quando o cliente chama o endpoint de execução da fonte "Fonte Janela Grande" com janela de "2026-01-01" a "2026-06-30"
    Então a resposta HTTP é 400 com mensagem contendo "90"
    E nenhuma execução foi registrada para a fonte "Fonte Janela Grande"

  Cenário: Janela incompleta é rejeitada
    Dado uma fonte "Fonte Janela Incompleta" do tipo "FAKE"
    E um cliente HTTP autenticado com o perfil "EXTRACAO"
    Quando o cliente chama o endpoint de execução da fonte "Fonte Janela Incompleta" com apenas data_inicio "2026-07-01"
    Então a resposta HTTP é 400 com mensagem contendo "conjunto"
    E nenhuma execução foi registrada para a fonte "Fonte Janela Incompleta"

  Cenário: Janela invertida é rejeitada
    Dado uma fonte "Fonte Janela Invertida" do tipo "FAKE"
    E um cliente HTTP autenticado com o perfil "EXTRACAO"
    Quando o cliente chama o endpoint de execução da fonte "Fonte Janela Invertida" com janela de "2026-07-10" a "2026-07-01"
    Então a resposta HTTP é 400 com mensagem contendo "anterior"
    E nenhuma execução foi registrada para a fonte "Fonte Janela Invertida"

  Cenário: Fonte inativa não executa
    Dado uma fonte "Fonte Inativa" do tipo "FAKE"
    E que a fonte "Fonte Inativa" foi inativada
    E um cliente HTTP autenticado com o perfil "EXTRACAO"
    Quando o cliente chama o endpoint de execução da fonte "Fonte Inativa" sem janela
    Então a resposta HTTP é 400 com mensagem contendo "inativa"
    E nenhuma execução foi registrada para a fonte "Fonte Inativa"

  Cenário: CONSULTA não executa fonte
    Dado uma fonte "Fonte Restrita" do tipo "FAKE"
    E um cliente HTTP autenticado com o perfil "CONSULTA"
    Quando o cliente chama o endpoint de execução da fonte "Fonte Restrita" sem janela
    Então a resposta HTTP é 403 em JSON
    E nenhuma execução foi registrada para a fonte "Fonte Restrita"

  Cenário: Credencial resolvida só na execução
    Dado a variável de ambiente "FONTE_TOKEN_BDD" definida como "valor-super-secreto"
    E uma fonte "Fonte Token" do tipo "FAKE" com token "${FONTE_TOKEN_BDD}"
    E que o conector devolve um saldo de "10.00" para a conta "001/0001/11111-1" e fundo "9999"
    Quando executo a fonte "Fonte Token"
    Então o conector recebeu o token "valor-super-secreto"
    E o config persistido da fonte "Fonte Token" contém "${FONTE_TOKEN_BDD}" e não contém "valor-super-secreto"

  Cenário: Variável indefinida gera ERRO nominal
    Dado uma fonte "Fonte Sem Var" do tipo "FAKE" com token "${VAR_INEXISTENTE_BDD}"
    Quando executo a fonte "Fonte Sem Var"
    Então a execução registra status "ERRO" com 0 inseridas e 0 com erro
    E o detalhe de erros da execução menciona "VAR_INEXISTENTE_BDD"

  Cenário: Teste de conexão não registra execução
    Dado uma fonte "Fonte Teste Conexao" do tipo "FAKE"
    Quando testo a conexão da fonte "Fonte Teste Conexao"
    Então o teste de conexão retorna sucesso
    E nenhuma execução foi registrada para a fonte "Fonte Teste Conexao"
