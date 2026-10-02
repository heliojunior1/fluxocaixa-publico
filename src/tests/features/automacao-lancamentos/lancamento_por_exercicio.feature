# language: pt
Funcionalidade: Lançamento automático por exercício
  Spec automacao-lancamentos R19–R21 e extracao-configuravel R24–R25
  (change exercicio-aberto-fechado)

  Cada linha extraída carrega o SEU exercício (não o ano da janela) e vai
  para o mapeamento e as rubricas daquele exercício; o lançamento nasce com a
  data do movimento. Exercício fechado não extrai nem processa; reextrair a
  mesma janela substitui, nunca acumula.
  Ilhas 2141/2142, ramo "1.84", sistema "SIS84".

  Contexto:
    Dado os planos de 2141 e 2142 com a rubrica "1.84.1"
    E os mapeamentos de 2141 e 2142 do sistema "SIS84" com o item "Natureza = 'A84'" em "1.84.1"

  Cenário: Item com rubrica de outro exercício é recusado
    Quando crio o mapeamento de 2142 do sistema "SIS84B" com item em "1.84.1" de 2141
    Então recebo erro de negócio citando "exercício"

  Cenário: Virada de ano separa as linhas
    Dado a fonte "Fonte BDD84" do sistema "SIS84" com linhas de natureza "A84" em 2141-12-31 de 100.00 e em 2142-01-02 de 200.00
    Quando executo a fonte "Fonte BDD84" na janela de 2141-12-30 a 2142-01-03
    Então a linha de 2141-12-31 está na staging no exercício 2141
    E a linha de 2142-01-02 está na staging no exercício 2142
    E a linha de 2141-12-31 virou lançamento na rubrica "1.84.1" de 2141
    E a linha de 2142-01-02 virou lançamento na rubrica "1.84.1" de 2142

  Cenário: Linha de exercício fechado é descartada
    Dado o exercício 2141 fechado
    E a fonte "Fonte BDD84" do sistema "SIS84" com linhas de natureza "A84" em 2141-12-31 de 100.00 e em 2142-01-02 de 200.00
    Quando executo a fonte "Fonte BDD84" na janela de 2141-12-30 a 2142-01-03
    Então a staging da fonte "Fonte BDD84" tem 1 linha
    E a última execução da fonte "Fonte BDD84" cita "fechado"

  Cenário: Exercício fechado não processa
    Dado uma linha pendente na staging de 2141 com natureza "A84"
    E o exercício 2141 fechado
    Quando processo o sistema "SIS84"
    Então nenhum lançamento foi gerado na rubrica "1.84.1" de 2141

  Cenário: Consulta por exercício roda para cada exercício aberto
    Dado a fonte por exercício "Fonte ANO84" do sistema "SIS84"
    Quando executo a fonte "Fonte ANO84" na janela de 2142-01-02 a 2142-01-03
    Então a consulta rodou para os exercícios 2141 e 2142

  Cenário: Reextrair não duplica
    Dado a fonte "Fonte BDD84" do sistema "SIS84" com linhas de natureza "A84" em 2142-01-02 de 200.00 e em 2142-01-03 de 300.00
    E a fonte "Fonte BDD84" executada na janela de 2142-01-01 a 2142-01-31
    Quando executo a fonte "Fonte BDD84" na janela de 2142-01-01 a 2142-01-31
    Então a staging da fonte "Fonte BDD84" tem 2 linhas
    E cada linha da fonte "Fonte BDD84" tem um único lançamento

  Cenário: Linha parada aparece no aviso
    Dado uma linha pendente na staging de 2141 com natureza "Z84" incluída há 10 dias
    Quando consulto as pendências da staging
    Então o exercício 2141 aparece com 1 linha pendente do sistema "SIS84"
