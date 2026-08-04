# language: pt
Funcionalidade: Índices da tabela de fatos e filtros de período sargáveis
  Spec infraestrutura-banco R12 (change indices-e-filtros-sargaveis)

  flc_lancamento é a tabela de fatos e não tinha NENHUM índice secundário;
  e os filtros por extract('year') == ano impedem o planejador de usá-los.
  Faixa de datas no filtro, extract só em projeção/residual.
  Ilha de datas 2064 (bissexto).

  Cenário: Banco migrado possui os índices da tabela de fatos
    Quando inspeciono os índices de flc_lancamento
    Então os quatro índices declarados existem

  Cenário: Total do ano inclui as bordas do calendário
    Dado um qualificador folha de índice
    E lançamentos ativos de 100.00 em 01/01, 15/06 e 31/12 de 2064
    E um lançamento ativo de 100.00 em 31/12 de 2063
    Quando consulto o total de créditos do ano 2064
    Então o total é 300.00

  Cenário: Total de fevereiro bissexto inclui o dia 29
    Dado um qualificador folha de índice
    E um lançamento ativo de 100.00 em 29/02 de 2064
    Quando consulto o total de créditos de fevereiro de 2064
    Então o total é 100.00

  Cenário: Filtro de ano não usa função sobre a coluna
    Quando compilo a consulta de total por tipo e ano
    Então o SQL filtra por faixa de datas e não contém extract no WHERE
