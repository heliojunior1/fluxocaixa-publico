# language: pt
Funcionalidade: Telas de fontes e execuções de extração
  Spec extracao-configuravel R10, R11, R12 e R13 (change telas-fontes-extracao)

  Contexto:
    Dado que estou autenticado como administrador
    E um sistema de origem "SIS_X" cadastrado
    E o conector de teste "FAKE" registrado

  # --- R10: tela de fontes ---

  Cenário: Listar fontes com o status da última execução
    Dado uma fonte de tela "Saldos diários" do tipo "FAKE"
    E uma execução "PARCIAL" registrada para a fonte "Saldos diários"
    Quando abro a tela de fontes
    Então a tela de fontes mostra "Saldos diários" com o status "PARCIAL"

  Cenário: Perfil sem manutenção não vê ações de escrita
    Dado uma fonte de tela "Fonte Consulta" do tipo "FAKE"
    E um cliente HTTP autenticado com o perfil "CONSULTA"
    Quando o cliente abre a tela de fontes
    Então a tela não oferece a ação de nova fonte

  Cenário: Inativar fonte exige confirmação
    Dado uma fonte de tela "Fonte Inativar" do tipo "FAKE"
    Quando inativo a fonte "Fonte Inativar" pela tela sem confirmar
    Então a fonte "Fonte Inativar" continua ativa
    Quando inativo a fonte "Fonte Inativar" pela tela com confirmação
    Então a fonte "Fonte Inativar" fica inativa

  Cenário: Sem conector registrado, tela mostra estado vazio
    Dado que nenhum conector de extração está registrado
    Quando abro a tela de fontes
    Então a tela de fontes mostra o estado vazio de conectores
    E a tela não oferece a ação de nova fonte

  Cenário: Testar conexão pela tela não registra execução
    Dado uma fonte de tela "Fonte Testar" do tipo "FAKE"
    Quando aciono testar conexão da fonte "Fonte Testar" pela tela
    Então o resultado do teste é sucesso
    E nenhuma execução foi registrada para a fonte de tela "Fonte Testar"

  Cenário: Executar agora pela tela registra execução manual
    Dado uma conta de tela "001/0001/22222-2"
    E um fundo de tela "8888"
    E uma fonte de tela "Fonte Executar" do tipo "FAKE"
    E que o conector de tela devolve um saldo de "1500.00" para a conta "001/0001/22222-2" e fundo "8888"
    Quando aciono executar agora da fonte "Fonte Executar" pela tela
    Então a resposta da execução tem status "SUCESSO"
    E a última execução da fonte de tela "Fonte Executar" tem disparo "MANUAL"

  # --- R11: histórico de execuções ---

  Cenário: Histórico exibe execução com contadores e status
    Dado uma fonte de tela "Fonte Hist" do tipo "FAKE"
    E uma execução "PARCIAL" registrada para a fonte "Fonte Hist"
    Quando abro a tela de execuções
    Então a tela de execuções mostra o status "PARCIAL"

  Cenário: Filtrar execuções por fonte
    Dado uma fonte de tela "Fonte Alpha" do tipo "FAKE"
    E uma fonte de tela "Fonte Beta" do tipo "FAKE"
    E uma execução "SUCESSO" registrada para a fonte "Fonte Alpha"
    E uma execução "SUCESSO" registrada para a fonte "Fonte Beta"
    Quando abro a tela de execuções filtrando pela fonte "Fonte Alpha"
    Então a tela de execuções lista a fonte "Fonte Alpha"
    E a tela de execuções não lista a fonte "Fonte Beta"

  Cenário: Detalhe de erros de uma execução com falha
    Dado uma fonte de tela "Fonte Erro" do tipo "FAKE"
    E uma execução com erro na conta "999/9999/00000-0" registrada para a fonte "Fonte Erro"
    Quando abro a tela de execuções
    Então o detalhe da execução menciona "999/9999/00000-0"

  # --- R12: formulário dinâmico ---

  Cenário: Campos do formulário vêm do schema do conector
    Quando abro o formulário de nova fonte para o tipo "FAKE"
    Então o formulário tem um campo "caminho" obrigatório
    E o formulário tem o campo secreto "token" mascarado

  Cenário: Editar fonte não expõe o segredo
    Dado uma fonte de tela "Fonte Segredo" do tipo "FAKE" com token "${FONTE_TOKEN_TELA}"
    Quando abro o formulário de edição da fonte "Fonte Segredo"
    Então o formulário não pré-preenche o valor "${FONTE_TOKEN_TELA}" no campo secreto

  Cenário: Config inválido é rejeitado na tela
    Quando crio pela tela a fonte "Fonte Sem Caminho" do tipo "FAKE" sem o campo "caminho"
    Então o cadastro pela tela é rejeitado com mensagem contendo "caminho"
    E a fonte de tela "Fonte Sem Caminho" não existe

  # --- R13: conector demo por env ---

  Cenário: Demo desligado por padrão
    Dado que a variável "EXTRACAO_DEMO_CONNECTOR" não está definida
    Quando os conectores disponíveis são registrados
    Então o tipo "DEMO_MANUAL" não está entre os conectores disponíveis

  Cenário: Demo habilitado por env
    Dado que a variável "EXTRACAO_DEMO_CONNECTOR" está habilitada
    Quando os conectores disponíveis são registrados
    Então o tipo "DEMO_MANUAL" está entre os conectores disponíveis
