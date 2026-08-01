# language: pt
Funcionalidade: Tradutor de regra em pt-BR para predicado validado
  Spec automacao-lancamentos R7 (change motor-mapeamentos-regras)

  Contexto:
    Dado que estou autenticado como administrador
    E os termos de regra padrão cadastrados

  # --- colisão de prefixo: o motivo da ordenação por comprimento decrescente ---

  Cenário: Termo mais longo vence o prefixo
    Dado o termo "Unidade Gestora" cadastrado para o atributo "ug"
    E o termo "Unidade Gestora Emitente" cadastrado para o atributo "ug_emitente"
    Quando traduzo a regra "Unidade Gestora Emitente = '999001'"
    Então o predicado referencia o atributo "ug_emitente"
    E o predicado não referencia o atributo "ug"

  Cenário: Regra com em e conectivos é traduzida
    Quando traduzo a regra "Unidade Gestora em ('999001','999002') e Natureza começa com '1112'"
    Então a regra é traduzida com sucesso

  Cenário: Regra com não e parênteses é traduzida
    Quando traduzo a regra "não (Unidade Gestora = '999001') ou Natureza começa com '1112'"
    Então a regra é traduzida com sucesso

  # --- rejeições: nada não reconhecido chega ao banco ---

  Cenário: Termo desconhecido é rejeitado
    Quando traduzo a regra "Coisa Inexistente = '1'"
    Então a tradução é rejeitada com mensagem contendo "Coisa Inexistente"

  Cenário: Regra malformada é rejeitada
    Quando traduzo a regra "Unidade Gestora ="
    Então a tradução é rejeitada

  Cenário: Operador incompatível com o tipo do termo é rejeitado
    Quando traduzo a regra "Valor começa com '1112'"
    Então a tradução é rejeitada com mensagem contendo "começa com"

  Cenário: Regra inválida é rejeitada no cadastro do item
    Dado um sistema de origem "SIS_X" cadastrado
    E um qualificador folha "1.1.1"
    Quando crio o mapeamento 2026 tipo "1" origem "SIS_X" com um item no qualificador "1.1.1" e regra "Coisa Inexistente = '1'"
    Então o cadastro do mapeamento é rejeitado com mensagem contendo "Coisa Inexistente"
