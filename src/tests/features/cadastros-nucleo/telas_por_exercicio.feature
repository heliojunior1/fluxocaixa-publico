# language: pt
Funcionalidade: Leitura e telas por exercício
  Spec `cadastros-nucleo` R28 (change telas-por-exercicio, F10.4): a
  resolução "qual plano vale para o ano X" tem origem única, as listagens e
  a árvore dos relatórios são recortadas pelo exercício resolvido, e a tela
  de qualificadores exibe e filtra por exercício — criação herda o filtro.

  Ilhas 2078/2079/2080. Os planos-ilha criam raízes "1"/"2" NO ANO-ILHA
  (a unicidade é por exercício — R25); a limpeza remove tudo dos anos-ilha.

  Cenário: Ano sem plano resolve para o plano anterior mais recente
    Dado um plano no exercício 2078 com a folha de receita "Rubrica Ilha A"
    E um plano no exercício 2079 com a folha de receita "Rubrica Ilha B"
    Quando resolvo o plano do ano 2080
    Então o exercício resolvido é 2079

  Cenário: Listagem da tela recorta pelo exercício selecionado
    Dado um plano no exercício 2078 com a folha de receita "Rubrica Ilha A"
    E um plano no exercício 2079 com a folha de receita "Rubrica Ilha B"
    Quando abro a tela de qualificadores no exercício 2078
    Então a tela lista "Rubrica Ilha A" e não lista "Rubrica Ilha B"

  Cenário: Criação pela tela herda o exercício do filtro
    Dado um plano no exercício 2078 com a folha de receita "Rubrica Ilha A"
    Quando cadastro pela tela a rubrica "1.9" chamada "Rubrica Criada Na Tela" no exercício 2078
    Então a rubrica "Rubrica Criada Na Tela" existe no exercício 2078

  Cenário: Relatório de árvore não mistura planos
    Dado um plano no exercício 2078 com a folha de receita "Rubrica Ilha A"
    E um plano no exercício 2079 com a folha de receita "Rubrica Ilha B"
    Quando gero o DFC anual de 2078
    Então a árvore do DFC contém "Rubrica Ilha A" e não contém "Rubrica Ilha B"
