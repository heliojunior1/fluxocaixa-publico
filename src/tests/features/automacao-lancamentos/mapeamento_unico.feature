# language: pt
Funcionalidade: Mapeamento único sem dimensão receita/despesa
  Spec automacao-lancamentos R6/R13 (change mapeamento-sem-dimensao-receita-despesa)

  Um mapeamento por (ano, sistema) reúne itens de receita E de despesa: a
  classificação vem do QUALIFICADOR do item, a direção vem do SINAL do
  valor. Dedução de receita aponta para rubrica de receita e neta a bruta —
  nunca se disfarça de despesa. Ilha 2074.

  Contexto:
    Dado que estou autenticado como administrador no mapeamento único
    E um sistema de origem "SIS_UNI" cadastrado para o mapeamento único
    E os termos de regra padrão cadastrados para o mapeamento único
    E uma folha de receita "1.76.1" e uma folha de despesa "2.76.1"

  Cenário: Itens de receita e despesa convivem no mesmo mapeamento
    Quando crio o mapeamento 2074 de "SIS_UNI" com item de receita "1.76.1" e item de despesa "2.76.1"
    Então o mapeamento de "SIS_UNI" em 2074 existe ativo com 2 itens

  Cenário: Segundo mapeamento do mesmo ano e origem é recusado
    Dado o mapeamento 2074 de "SIS_UNI" com item de receita "1.76.1" e item de despesa "2.76.1"
    Quando tento criar outro mapeamento 2074 de "SIS_UNI"
    Então recebo mensagem de negócio de mapeamento duplicado

  Cenário: Classificação mista processa pelo sinal
    Dado linhas na staging de "SIS_UNI" em 2074 com receita 1000.00, dedução -100.00 e despesa -300.00
    E o mapeamento 2074 de "SIS_UNI" com regras de receita, dedução e despesa
    Quando processo o mapeamento único
    Então a árvore de receita "1.76" tem um crédito de 1000.00 e um débito de 100.00
    E a rubrica "2.76.1" tem um débito de 300.00

  Cenário: Dedução aponta rubrica de receita e neta a bruta
    Dado linhas na staging de "SIS_UNI" em 2074 com receita 1000.00, dedução -100.00 e despesa -300.00
    E o mapeamento 2074 de "SIS_UNI" com regras de receita, dedução e despesa
    Quando processo o mapeamento único
    Então o total líquido da árvore de receita "1.76" é 900.00
