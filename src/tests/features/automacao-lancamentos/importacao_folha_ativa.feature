# language: pt
Funcionalidade: Importação de lançamentos exige folha ativa e recusa ambiguidade
  Spec automacao-lancamentos R18 (change importacao-lancamento-folha-ativa)

  A planilha aplica as MESMAS garantias da porta manual: só folha ativa
  recebe lançamento (o DFC depende do invariante "lançamento só em folha"),
  e descrição compartilhada por duas rubricas é ERRO explícito citando os
  códigos — nunca "o último vence" em silêncio. Ilha 2070.

  Cenário: Linha com qualificador inativo é recusada
    Dado um qualificador folha inativo "1.71.9" descrito como "Rubrica Inativa Q10"
    Quando importo uma planilha com uma linha para "Rubrica Inativa Q10"
    Então a importação recusa a linha citando "não encontrado"
    E nenhum lançamento de 2070 foi gravado

  Cenário: Linha com nó-pai é recusada
    Dado um qualificador pai "1.71" descrito como "Bloco Pai Q10" com filho ativo "1.71.1"
    Quando importo uma planilha com uma linha para "Bloco Pai Q10"
    Então a importação recusa a linha citando "folha"
    E nenhum lançamento de 2070 foi gravado

  Cenário: Descrição ambígua é recusada citando os conflitos
    Dado duas rubricas ativas "1.71.2" e "1.71.3" descritas como "Rubrica Ambígua Q10"
    Quando importo uma planilha com uma linha para "Rubrica Ambígua Q10"
    Então a importação recusa a linha como ambígua citando "1.71.2" e "1.71.3"
    E nenhum lançamento de 2070 foi gravado

  Cenário: Linha válida em folha ativa grava com origem Importado
    Dado um qualificador folha ativo "1.71.4" descrito como "Rubrica Única Q10"
    Quando importo uma planilha com uma linha para "Rubrica Única Q10"
    Então um lançamento de 2070 foi gravado com origem "Importado"
