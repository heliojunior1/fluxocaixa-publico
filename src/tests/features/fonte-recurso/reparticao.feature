# language: pt
Funcionalidade: Repartição da projeção por grupo de fonte
  Como tesouraria, quero repartir qualificadores de receita por fonte —
  soma exata de 100, conjunto atômico — para a simulação separar o que é
  livre do que é vinculado; sem repartição, o valor vai ao não classificado.

  Contexto:
    Dado que estou autenticado como administrador
    E a fonte "1.590" cadastrada na vigência 2039 como "livre"
    E a fonte "1.690" cadastrada na vigência 2039 como "vinculada"

  Cenário: Conjunto que soma 100 é aceito
    Dado um qualificador folha de receita "1.8.11"
    Quando defino a repartição de "1.8.11" na vigência 2039 como 80.0 na fonte "1.590" e 20.0 na fonte "1.690"
    Então a repartição de "1.8.11" na vigência 2039 tem 2 fontes

  Cenário: Soma diferente de 100 é recusada
    Dado um qualificador folha de receita "1.8.12"
    Quando defino a repartição de "1.8.12" na vigência 2039 como 70.0 na fonte "1.590" e 20.0 na fonte "1.690"
    Então a operação de repartição é rejeitada com a mensagem "A soma dos percentuais da repartição deve ser exatamente 100"
    E a repartição de "1.8.12" na vigência 2039 tem 0 fontes

  Cenário: Qualificador de despesa é recusado
    Dado um qualificador folha de despesa "2.8.11"
    Quando defino a repartição de "2.8.11" na vigência 2039 como 100.0 na fonte "1.590"
    Então a operação de repartição é rejeitada com a mensagem "Repartição é de qualificador de receita"

  Cenário: Redefinir substitui o conjunto por inteiro
    Dado um qualificador folha de receita "1.8.13"
    E defino a repartição de "1.8.13" na vigência 2039 como 80.0 na fonte "1.590" e 20.0 na fonte "1.690"
    Quando defino a repartição de "1.8.13" na vigência 2039 como 100.0 na fonte "1.590"
    Então a repartição de "1.8.13" na vigência 2039 tem 1 fontes

  Cenário: Valor repartido pelos grupos
    Dado um qualificador folha de receita "1.8.14"
    E defino a repartição de "1.8.14" na vigência 2039 como 80.0 na fonte "1.590" e 20.0 na fonte "1.690"
    Quando reparto 1000.00 de "1.8.14" na vigência 2039
    Então o grupo "L" da repartição recebe 800.00
    E o grupo "V" da repartição recebe 200.00
    E o grupo "N" da repartição recebe 0.00

  Cenário: Sem repartição vai ao não classificado
    Dado um qualificador folha de receita "1.8.15"
    Quando reparto 500.00 de "1.8.15" na vigência 2039
    Então o grupo "N" da repartição recebe 500.00
    E o grupo "L" da repartição recebe 0.00

  Cenário: Sugestão vem do histórico estampado
    Dado um qualificador folha de receita "1.8.16"
    E um lançamento de 300.00 em "1.8.16" estampado na fonte "1.590" da vigência 2039
    E um lançamento de 100.00 em "1.8.16" estampado na fonte "1.690" da vigência 2039
    Quando consulto a sugestão do histórico de "1.8.16"
    Então a sugestão traz 75.00 para a fonte "1.590" da vigência 2039
    E a sugestão traz 25.00 para a fonte "1.690" da vigência 2039
