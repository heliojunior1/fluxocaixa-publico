# language: pt
Funcionalidade: Dicionário de termos de regra
  Spec automacao-lancamentos R5 (change motor-mapeamentos-regras)

  Contexto:
    Dado que estou autenticado como administrador

  Cenário: Termo de atributo é cadastrado
    Quando cadastro o termo "Unidade Gestora" para o atributo "ug" do tipo "TEXTO"
    Então o termo "Unidade Gestora" existe ativo apontando para o atributo "ug"

  Cenário: Termo de coluna da whitelist é cadastrado
    Quando cadastro o termo "Valor" para a coluna "val_referencia" do tipo "NUMERO"
    Então o termo "Valor" existe ativo apontando para a coluna "val_referencia"

  Cenário: Termo de coluna fora da whitelist é rejeitado
    Quando cadastro o termo "Status" para a coluna "ind_status_processamento" do tipo "TEXTO"
    Então o cadastro do termo é rejeitado com mensagem contendo "não é permitido"
    E o termo "Status" não existe

  Cenário: Termo duplicado entre ativos é rejeitado
    Dado o termo "Unidade Gestora" cadastrado para o atributo "ug"
    Quando cadastro o termo "Unidade Gestora" para o atributo "outra_ug" do tipo "TEXTO"
    Então o cadastro do termo é rejeitado com mensagem contendo "já existe"
