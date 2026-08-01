# language: pt
Funcionalidade: Categoria fiscal do qualificador, herdada pela árvore
  Spec `cadastros-nucleo` R15: a marcação é opcional e vale para os
  descendentes; a categoria resolvida é a do próprio nó ou a do ancestral
  marcado MAIS PRÓXIMO.

  O ramo de teste nasce em "2.7", sob a raiz de DESPESA: as metas fiscais só
  olham despesa, e uma raiz inventada não passaria pelo `tipo_fluxo`.

  Cenário: Folha sem marcação herda do bloco
    Dado o bloco "2.7" marcado como "EDUCACAO"
    E a folha "2.7.1" sem marcação sob "2.7"
    Quando consulto a categoria resolvida de "2.7.1"
    Então a categoria é "EDUCACAO"

  Cenário: Marcação própria vence a herdada
    Dado o bloco "2.7" marcado como "SAUDE"
    E a folha "2.7.1" marcada como "EDUCACAO" sob "2.7"
    Quando consulto a categoria resolvida de "2.7.1"
    Então a categoria é "EDUCACAO"

  Cenário: Ancestral mais próximo vence o mais distante
    Dado o bloco "2.7" marcado como "SAUDE"
    E o bloco "2.7.1" marcado como "EDUCACAO" sob "2.7"
    E a folha "2.7.1.1" sem marcação sob "2.7.1"
    Quando consulto a categoria resolvida de "2.7.1.1"
    Então a categoria é "EDUCACAO"

  Cenário: Ramo sem marcação alguma não tem categoria
    Dado o bloco "2.7" sem marcação
    E a folha "2.7.1" sem marcação sob "2.7"
    Quando consulto a categoria resolvida de "2.7.1"
    Então não há categoria

  Cenário: Reapontar o pai muda a categoria da subárvore
    # Prova que a categoria resolvida NÃO foi persistida: se fosse coluna
    # gravada, mudar de pai a deixaria desatualizada até alguém repropagar.
    Dado o bloco "2.7" marcado como "EDUCACAO"
    E o bloco "2.8" marcado como "SAUDE"
    E a folha "2.7.1" sem marcação sob "2.7"
    Quando reaponto "2.7.1" para o bloco "2.8"
    E consulto a categoria resolvida dessa folha
    Então a categoria é "SAUDE"

  Cenário: Marcação é permitida em nó com filhos
    # Exceção DELIBERADA ao "só folha" dos R12–R14: marcar o bloco e deixar as
    # folhas herdarem é justamente o propósito da regra.
    Dado o bloco "2.7" sem marcação
    E a folha "2.7.1" sem marcação sob "2.7"
    Quando marco "2.7" como "EDUCACAO"
    Então a marcação é aceita
    E a categoria resolvida de "2.7.1" é "EDUCACAO"
