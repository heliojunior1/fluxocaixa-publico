# language: pt
Funcionalidade: Exercício aberto e fechado
  Spec cadastros-nucleo R31–R32 (change exercicio-aberto-fechado)

  O exercício tem situação (aberto/fechado) num livro de eventos. Fechado
  trava a escrita do ano: plano e mapeamento só leitura, nenhum lançamento
  com data no ano. Abrir o ano novo copia também os mapeamentos, com os
  itens re-apontados para o plano novo.
  Ilhas 2141/2142, ramo "1.84", sistema "SIS84".

  Cenário: Fechar exige confirmação
    Dado o plano de 2141 com a rubrica "1.84.1"
    Quando fecho o exercício 2141 com motivo "Encerramento BDD" sem confirmar
    Então recebo erro de negócio citando "confirme"
    E o exercício 2141 continua aberto

  Cenário: Fechar avisa as linhas pendentes da staging
    Dado o plano de 2141 com a rubrica "1.84.1"
    E uma linha pendente na staging de 2141 com natureza "A84"
    Quando fecho o exercício 2141 com motivo "Encerramento BDD" sem confirmar
    Então recebo erro de negócio citando "1 linha"

  Cenário: Exercício fechado recusa lançamento
    Dado o plano de 2141 com a rubrica "1.84.1"
    E o exercício 2141 fechado
    Quando lanço 1234.56 em "1.84.1" com data 2141-05-10
    Então recebo erro de negócio citando "fechado"

  Cenário: Plano fechado é só leitura
    Dado o plano de 2141 com a rubrica "1.84.1"
    E o exercício 2141 fechado
    Quando altero a descrição de "1.84.1" de 2141
    Então recebo erro de negócio citando "fechado"

  Cenário: Reabrir devolve a escrita
    Dado o plano de 2141 com a rubrica "1.84.1"
    E o exercício 2141 fechado
    Quando reabro o exercício 2141 com motivo "Ajuste tardio BDD"
    E lanço 1234.56 em "1.84.1" com data 2141-05-10
    Então o lançamento é aceito
    E o histórico do exercício 2141 tem "FECHAMENTO" e "REABERTURA"

  Cenário: Mapeamento nasce pronto no ano novo
    Dado o plano de 2141 com a rubrica "1.84.1"
    E o mapeamento de 2141 do sistema "SIS84" com o item "Natureza = 'A84'" em "1.84.1"
    Quando abro o exercício 2142 a partir de 2141
    Então existe o mapeamento de 2142 do sistema "SIS84"
    E o item do mapeamento de 2142 aponta para "1.84.1" do plano de 2142 com a regra "Natureza = 'A84'"
    E o histórico do exercício 2142 tem "ABERTURA"
