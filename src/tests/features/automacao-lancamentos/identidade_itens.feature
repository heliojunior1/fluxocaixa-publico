# language: pt
Funcionalidade: Identidade dos itens na alteração do mapeamento
  Spec automacao-lancamentos R6 (change tela-mapeamentos-builder)

  A F4.3 detecta item sujo pela AUSÊNCIA do marco de execução. Se a alteração recriasse
  os itens, todo save marcaria tudo como sujo e a limpeza cirúrgica viraria recarga total
  do ano. Item inalterado mantém o marco; item alterado o descarta (não foi executado na
  forma em que está).

  Contexto:
    Dado que estou autenticado como administrador
    E um sistema de origem "SIS_X" cadastrado
    E os termos de regra padrão cadastrados
    E um qualificador folha "1.1.1"
    E um qualificador folha "1.1.2"

  Cenário: Alterar sem mudar o item não o marca como alterado
    Dado um mapeamento com um item já processado no qualificador "1.1.1"
    Quando altero apenas a descrição do mapeamento, reenviando o item igual
    Então o item mantém o mesmo identificador
    E o item mantém a data de última execução
    E o item não tem data de alteração

  Cenário: Alterar a regra preserva a identidade e descarta o marco de execução
    Dado um mapeamento com um item já processado no qualificador "1.1.1"
    Quando altero a regra desse item para "Natureza começa com '2222'"
    Então o item mantém o mesmo identificador
    E o item fica sem data de última execução
    E o item tem data de alteração

  Cenário: Item novo entra sem marco de execução
    Dado um mapeamento com um item já processado no qualificador "1.1.1"
    Quando acrescento um item no qualificador "1.1.2"
    Então o mapeamento tem 2 itens ativos
    E o item do qualificador "1.1.2" não tem data de última execução

  Cenário: Item removido da alteração é inativado
    Dado um mapeamento com um item já processado no qualificador "1.1.1"
    E um item ativo no qualificador "1.1.2"
    Quando altero o mapeamento reenviando apenas o item do qualificador "1.1.2"
    Então o item do qualificador "1.1.1" fica inativo
    E o item do qualificador "1.1.1" mantém a data de última execução

  Cenário: Item de outro mapeamento é rejeitado
    Dado um mapeamento com um item já processado no qualificador "1.1.1"
    E outro mapeamento 2025 com um item no qualificador "1.1.2"
    Quando altero o mapeamento enviando um item que pertence ao outro mapeamento
    Então a alteração é rejeitada com mensagem contendo "não pertence"
