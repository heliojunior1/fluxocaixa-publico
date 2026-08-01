# language: pt
Funcionalidade: Editor de layout na tela e preview de parsing
  Spec extracao-configuravel R17 e R18 (change editor-layout-extracao)

  Contexto:
    Dado que estou autenticado como administrador
    E um sistema de origem "SIS_X" cadastrado
    E o conector "FTP_ARQUIVO" registrado
    E o conector de teste "FAKE" registrado

  # --- R17: editor de layout e persistência ---

  Cenário: Formulário de conector de arquivo mostra a seção de layout
    Quando abro o formulário de nova fonte para o tipo "FTP_ARQUIVO"
    Então o formulário mostra a seção de layout do arquivo

  Cenário: Conector sem schema_layout não mostra a seção de layout
    Quando abro o formulário de nova fonte para o tipo "FAKE"
    Então o formulário não mostra a seção de layout do arquivo

  Cenário: Cadastrar fonte de arquivo com layout persiste o json_layout
    Dado uma pasta de exemplo com o arquivo "extrato_ok.csv" para o dia "2026-07-10"
    E as contas de exemplo cadastradas
    Quando cadastro pela tela a fonte "Caixa Layout" apontando para a pasta com o layout de extrato
    Então a fonte "Caixa Layout" tem o layout salvo
    E executar a fonte "Caixa Layout" para o dia "2026-07-10" grava 2 saldos

  Cenário: Editar fonte pré-carrega o layout salvo
    Dado uma pasta de exemplo com o arquivo "extrato_ok.csv" para o dia "2026-07-10"
    E uma fonte de arquivo "Caixa Editar" com o layout de extrato na pasta de exemplo
    Quando abro o formulário de edição da fonte "Caixa Editar"
    Então o formulário de edição traz o layout salvo

  Cenário: Layout inválido é rejeitado no cadastro
    Dado uma pasta de exemplo vazia
    Quando cadastro pela tela a fonte "Layout Ruim" com transformação de coluna "inexistente"
    Então o cadastro pela tela de layout é rejeitado
    E a fonte "Layout Ruim" não existe

  # --- R18: preview ---

  Cenário: Preview do layout oficial mostra as linhas
    Quando faço o preview do arquivo "extrato_ok.csv" com o layout de extrato
    Então o preview retorna 2 linhas e 0 erros
    E o preview não registra execução

  Cenário: Preview aponta erros de linha sem abortar
    Quando faço o preview do arquivo "extrato_linha_ruim.csv" com o layout de extrato
    Então o preview retorna 1 linhas e 1 erros

  Cenário: Preview com header divergente reporta arquivo rejeitado
    Quando faço o preview do arquivo "extrato_header_ruim.csv" com o layout de extrato
    Então o preview informa arquivo rejeitado
