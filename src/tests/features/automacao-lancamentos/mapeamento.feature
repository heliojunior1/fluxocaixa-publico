# language: pt
Funcionalidade: Cadastro de mapeamento e itens
  Spec automacao-lancamentos R6 (change motor-mapeamentos-regras)

  Contexto:
    Dado que estou autenticado como administrador
    E um sistema de origem "SIS_X" cadastrado
    E um sistema de origem "SIS_Y" cadastrado
    E os termos de regra padrão cadastrados
    E um qualificador folha "1.1.1"

  Cenário: Mapeamento válido é criado
    Quando crio o mapeamento 2026 origem "SIS_X" com um item no qualificador "1.1.1" e regra "Unidade Gestora = '999001'"
    Então o mapeamento 2026 origem "SIS_X" existe ativo com 1 item

  Cenário: Mapeamento duplicado no mesmo ano e origem é rejeitado
    Dado o mapeamento 2026 origem "SIS_X" cadastrado
    Quando crio o mapeamento 2026 origem "SIS_X" com um item no qualificador "1.1.1" e regra "Unidade Gestora = '999001'"
    Então o cadastro do mapeamento é rejeitado com mensagem contendo "já existe"

  Cenário: Mesmo ano com origem diferente coexiste
    Dado o mapeamento 2026 origem "SIS_X" cadastrado
    Quando crio o mapeamento 2026 origem "SIS_Y" com um item no qualificador "1.1.1" e regra "Unidade Gestora = '999001'"
    Então o mapeamento 2026 origem "SIS_Y" existe ativo com 1 item

  Cenário: Mapeamento sem item ativo é rejeitado
    Quando crio o mapeamento 2026 origem "SIS_X" sem itens
    Então o cadastro do mapeamento é rejeitado com mensagem contendo "item"

  Cenário: Item em qualificador não-folha é rejeitado
    Dado um qualificador "1.1" com filhos ativos
    Quando crio o mapeamento 2026 origem "SIS_X" com um item no qualificador "1.1" e regra "Unidade Gestora = '999001'"
    Então o cadastro do mapeamento é rejeitado com mensagem contendo "folha"

  Cenário: Qualificador repetido entre itens ativos é rejeitado
    Quando crio o mapeamento 2026 origem "SIS_X" com dois itens no mesmo qualificador "1.1.1"
    Então o cadastro do mapeamento é rejeitado com mensagem contendo "repetido"

  Cenário: Inversão de sinal é persistida sem ser aplicada
    Quando crio o mapeamento 2026 origem "SIS_X" com um item no qualificador "1.1.1" com inversão de sinal
    Então o item do mapeamento tem inversão de sinal "1"
