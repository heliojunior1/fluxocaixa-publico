# language: pt
Funcionalidade: Catálogo de fontes de recurso (decomposto e versionado)
  Como tesouraria, quero um catálogo de fontes no padrão STN — decomposto em
  identificador de exercício + fonte + detalhamento, versionado por vigência,
  com vinculação explícita — para classificar o dinheiro pela destinação legal.

  Contexto:
    Dado que estou autenticado como administrador

  Cenário: Mesma fonte STN coexiste em dois exercícios
    Dado a fonte "1.510" cadastrada na vigência 2031 como "livre"
    Quando cadastro a fonte "1.510" na vigência 2032 como "livre"
    Então existem 2 fontes ativas com o código "1.510"

  Cenário: Duplicidade no mesmo exercício é recusada
    Dado a fonte "1.511" cadastrada na vigência 2031 como "livre"
    Quando cadastro a fonte "1.511" na vigência 2031 como "livre"
    Então a operação de fonte é rejeitada com a mensagem "Já existe fonte ativa com este código nesta vigência"

  Cenário: Código completo é derivado das partes
    Dado a fonte "1.512" cadastrada na vigência 2031 como "livre"
    Então o código exibido da fonte "1.512" na vigência 2031 é "1.512"

  Cenário: Identificador de exercício inválido é recusado
    Quando cadastro a fonte "5.513" na vigência 2031 como "livre"
    Então a operação de fonte é rejeitada com a mensagem "Identificador de exercício deve ser 1, 2 ou 9"

  Cenário: Vinculação não segue o prefixo do código
    Dado a fonte "1.514" cadastrada na vigência 2031 como "vinculada"
    Então a fonte "1.514" da vigência 2031 pertence ao grupo "V"

  Cenário: Ajuste manual sobrevive ao seed
    Dado a fonte do seed "1.500" do exercício corrente
    Quando altero a vinculação dessa fonte para "vinculada"
    E o seed de domínio roda novamente
    Então a vinculação dessa fonte permanece "vinculada"

  Cenário: Preview de importação aponta erro sem gravar
    Dado uma planilha da tabela STN da vigência 2037 com uma linha sem código de fonte
    Quando envio a planilha para preview
    Então a linha inválida é apontada como erro
    E nenhuma fonte da vigência 2037 foi gravada

  Cenário: Confirmação da importação grava só a vigência importada
    Dado a fonte "1.516" cadastrada na vigência 2034 como "livre"
    E uma planilha válida da tabela STN da vigência 2035 com a fonte "516"
    Quando envio a planilha para preview
    E confirmo a importação da planilha
    Então a fonte "1.516" existe ativa na vigência 2035
    E a fonte "1.516" da vigência 2034 permanece intacta

  Cenário: Importação ignora fonte já existente na vigência
    Dado a fonte "1.517" cadastrada na vigência 2031 como "livre"
    E uma planilha válida da tabela STN da vigência 2031 com a fonte "517"
    Quando envio a planilha para preview
    Então a linha aparece como aviso de já existente
