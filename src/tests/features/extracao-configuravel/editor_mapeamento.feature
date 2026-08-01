# language: pt
Funcionalidade: Editor de mapeamento na tela (conectores de mapeamento)
  Spec extracao-configuravel R17 (modificado) e R22 (change editor-mapeamento-api)

  Contexto:
    Dado que estou autenticado como administrador
    E um sistema de origem "SIS_X" cadastrado
    E o conector de teste "FAKE" registrado

  # --- R17 (mod): conector de arquivo mostra a seção de arquivo ---

  Cenário: Conector de arquivo mostra a seção de arquivo, não a de mapeamento
    Quando abro o formulário de nova fonte para o tipo "FTP_ARQUIVO"
    Então a tela mostra a seção de layout de arquivo
    E a tela não mostra a seção de mapeamento

  Cenário: Conector sem layout_kind não mostra seção de layout
    Quando abro o formulário de nova fonte para o tipo "FAKE"
    Então a tela não mostra a seção de layout de arquivo
    E a tela não mostra a seção de mapeamento

  # --- R22: conectores de mapeamento mostram a seção de mapeamento ---

  Cenário: Conector de API mostra a seção de mapeamento
    Quando abro o formulário de nova fonte para o tipo "API_REST"
    Então a tela mostra a seção de mapeamento
    E a tela não mostra a seção de layout de arquivo

  Cenário: Conector de banco SQL usa o mesmo editor de mapeamento
    Quando abro o formulário de nova fonte para o tipo "BANCO_SQL"
    Então a tela mostra a seção de mapeamento

  Cenário: Cadastrar fonte de mapeamento persiste o json_layout
    Quando cadastro pela tela a fonte SQL "SQL Mapa" com um mapeamento válido
    Então a fonte "SQL Mapa" tem o mapeamento salvo

  Cenário: Mapeamento inválido é rejeitado no cadastro
    Quando cadastro pela tela a fonte SQL "SQL Mapa Ruim" com transformação de mapeamento "decimal"
    Então o cadastro de mapeamento é rejeitado
    E a fonte "SQL Mapa Ruim" não existe

  # --- R22: preview de mapeamento ---

  Cenário: Preview de mapeamento por amostra JSON não grava
    Quando faço o preview de mapeamento de uma amostra com 2 itens
    Então o preview de mapeamento retorna 2 linhas e 0 erros
    E o preview de mapeamento não registra execução

  Cenário: Preview aponta erro de mapeamento por item
    Quando faço o preview de mapeamento de uma amostra com um item sem o código do fundo
    Então o preview de mapeamento retorna 0 linhas e 1 erros
