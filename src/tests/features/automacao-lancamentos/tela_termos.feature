# language: pt
Funcionalidade: Tela de cadastro do dicionário de termos
  Spec automacao-lancamentos R9 (change tela-mapeamentos-builder)

  Contexto:
    Dado que estou autenticado como administrador

  Cenário: Cadastrar termo de atributo pela tela
    Quando cadastro pela tela o termo "Unidade Gestora" para o atributo "ug" do tipo "TEXTO"
    Então a lista de termos mostra "Unidade Gestora" ativo

  Cenário: Campo de coluna fora da whitelist é recusado na tela
    Quando cadastro pela tela o termo "Status" para a coluna "ind_status_processamento" do tipo "TEXTO"
    Então a tela de termos mostra erro contendo "não é permitido"

  Cenário: A tela oferece apenas as colunas permitidas
    Quando abro a tela de termos
    Então as opções de coluna são exatamente a whitelist

  Cenário: Inativar termo pela tela
    Dado o termo "Descartável" cadastrado para o atributo "x"
    Quando inativo pela tela o termo "Descartável"
    Então a lista de termos não mostra "Descartável" entre os ativos

  Cenário: Sem permissão de manutenção não vejo as ações de termo
    Dado que estou autenticado como usuário só de consulta
    Quando abro a tela de termos
    Então não vejo a ação de novo termo
