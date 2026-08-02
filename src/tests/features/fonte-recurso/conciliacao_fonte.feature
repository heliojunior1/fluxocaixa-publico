# language: pt
Funcionalidade: Conciliação operacional × contábil por fonte (F9.4)
  Como Tesouro, quero os dois números lado a lado — quando batem (ou a
  diferença é explicada), o sistema deixa de ser controle paralelo.

  Contexto:
    Dado que estou autenticado como administrador

  Cenário: Carga contábil registrada
    Dado a fonte "1.502" cadastrada na vigência 2057 como "vinculada"
    Quando importo disponibilidade contábil de 5000.00 para a fonte "1.502" na data "2057-06-30"
    Então a disponibilidade contábil da fonte "1.502" da vigência 2057 em "2057-06-30" é 5000.00

  Cenário: Revisão inativa a anterior
    Quando importo disponibilidade contábil de 5500.00 para a fonte "1.502" na data "2057-06-30"
    Então a disponibilidade contábil da fonte "1.502" da vigência 2057 em "2057-06-30" é 5500.00
    E existe 1 carga inativa da fonte "1.502" da vigência 2057 em "2057-06-30"

  Cenário: Fonte desconhecida nasce pendente
    Quando importo disponibilidade contábil de 100.00 para a fonte "9.777" na data "2057-06-30"
    Então a fonte "9.777" da vigência 2057 existe vinculada e pendente de revisão

  Cenário: Diferença a explicar e sem contábil neutro
    Quando concilio a data "2057-06-30"
    Então a conciliação da fonte "1.502" da vigência 2057 mostra situação "A_EXPLICAR" com diferença -5500.00
    E a conciliação da fonte "9.777" da vigência 2057 mostra situação "A_EXPLICAR" com diferença -100.00

  Cenário: Conciliada quando bate
    Quando importo disponibilidade contábil de 0.00 para a fonte "1.502" na data "2057-06-30"
    E concilio a data "2057-06-30"
    Então a conciliação da fonte "1.502" da vigência 2057 mostra situação "CONCILIADA" com diferença 0.00
