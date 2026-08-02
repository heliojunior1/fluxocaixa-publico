# language: pt
Funcionalidade: Fonte de recursos no lançamento (estágio B da estampagem)
  Como tesouraria, quero cada lançamento carregando sua fonte — estampada
  automaticamente do atributo da staging no processamento, escolhida sem
  default na porta manual — para existir fluxo realizado por fonte.

  Contexto:
    Dado que estou autenticado como administrador

  Cenário: Linha com atributo de fonte estampa o lançamento
    Dado um sistema de origem "SIS_F92A" cadastrado
    E os termos de regra padrão cadastrados
    E linhas na staging de "SIS_F92A" com o atributo de fonte "761"
    E o mapeamento 2026 de "SIS_F92A" com o item "1.7.1" e regra "Natureza começa com '1112'"
    Quando processo o mapeamento
    Então o lançamento do qualificador "1.7.1" referencia a fonte "1.761" da vigência 2026
    E a fonte "1.761" da vigência 2026 existe vinculada e pendente de revisão

  Cenário: Linha sem atributo de fonte gera lançamento sem fonte
    Dado um sistema de origem "SIS_F92B" cadastrado
    E os termos de regra padrão cadastrados
    E linhas na staging de "SIS_F92B" sem atributo de fonte
    E o mapeamento 2026 de "SIS_F92B" com o item "1.7.2" e regra "Natureza começa com '1112'"
    Quando processo o mapeamento
    Então o lançamento do qualificador "1.7.2" não referencia fonte alguma
    E a linha de natureza "11120000" está classificada

  Cenário: Valor de fonte não parseável não bloqueia nem cria fonte
    Dado um sistema de origem "SIS_F92C" cadastrado
    E os termos de regra padrão cadastrados
    E linhas na staging de "SIS_F92C" com o atributo de fonte "XYZ"
    E o mapeamento 2026 de "SIS_F92C" com o item "1.7.3" e regra "Natureza começa com '1112'"
    E anoto o total de fontes do catálogo
    Quando processo o mapeamento
    Então o lançamento do qualificador "1.7.3" não referencia fonte alguma
    E o total de fontes do catálogo não mudou

  Cenário: Lançamento manual com fonte
    Dado a fonte "1.560" cadastrada na vigência 2035 como "livre"
    E um qualificador folha "1.7.4"
    Quando crio um lançamento manual de 1234.56 em "1.7.4" na data "2035-03-15" com a fonte "1.560" da vigência 2035
    Então o lançamento manual de "1.7.4" referencia a fonte "1.560" da vigência 2035

  Cenário: Lançamento manual sem fonte é permitido
    Dado um qualificador folha "1.7.5"
    Quando crio um lançamento manual de 100.00 em "1.7.5" na data "2035-03-16" sem fonte
    Então o lançamento manual de "1.7.5" não referencia fonte alguma

  Cenário: Filtro por fonte na listagem
    Dado a fonte "1.561" cadastrada na vigência 2035 como "livre"
    E um qualificador folha "1.7.6"
    E crio um lançamento manual de 200.00 em "1.7.6" na data "2035-03-17" com a fonte "1.561" da vigência 2035
    E crio um lançamento manual de 300.00 em "1.7.6" na data "2035-03-17" sem fonte
    Quando listo os lançamentos de "2035-03-17" filtrando pela fonte "1.561" da vigência 2035
    Então a listagem traz 1 lançamento
    E listo os lançamentos de "2035-03-17" sem filtro de fonte traz 2 lançamentos
