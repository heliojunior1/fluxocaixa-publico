# language: pt
Funcionalidade: Liberação ancorada no liquidado não pago (F8.4)
  Como Tesouro, quero a liberação enxergando o "devido" — acima do estoque
  ou em fonte divergente é decisão consciente, nunca silenciosa.

  Contexto:
    Dado que estou autenticado como administrador
    E um órgão "70012" chamado "Secretaria do Devido"
    E um qualificador folha de despesa "2.9.91"
    E a fonte "1.500" cadastrada na vigência 2056 como "livre"

  Cenário: Dentro do liquidado confirma sem exigência extra
    Dado um empenho "2056NE001" de 1000.00 em 2056 no órgão "70012" e qualificador "2.9.91" com a fonte "1.501"
    E a liquidação "2056NL001" de 800.00 em 2056 vinculada a "2056NE001"
    E uma liberação em rascunho de 500.00 em "2056-05-10" no órgão "70012", qualificador "2.9.91" e fonte "1.501" da vigência 2056
    Quando confirmo essa liberação sem confirmação explícita
    Então essa liberação está confirmada sem exigência extra

  Cenário: Acima do liquidado exige confirmação consciente
    Dado uma liberação em rascunho de 900.00 em "2056-06-10" no órgão "70012", qualificador "2.9.91" e fonte "1.501" da vigência 2056
    Quando confirmo essa liberação sem confirmação explícita
    Então a operação de liquidado é rejeitada com a mensagem "Liberação excede o liquidado não pago do órgão em R$ 100.00 — confirme explicitamente para prosseguir"
    Quando confirmo essa liberação com confirmação explícita
    Então essa liberação está confirmada e o evento registra "Liquidado não pago excedido em R$ 100.00"

  Cenário: Fonte divergente do liquidado exige confirmação consciente
    Dado uma liberação em rascunho de 100.00 em "2056-07-10" no órgão "70012", qualificador "2.9.91" e fonte "1.500" da vigência 2056
    Quando confirmo essa liberação sem confirmação explícita
    Então a operação de liquidado é rejeitada com a mensagem "Fonte da liberação diverge das fontes do liquidado não pago do órgão — confirme explicitamente para prosseguir"

  Cenário: Órgão sem execução importada não muda
    Dado um órgão "70013" chamado "Secretaria Sem Funil"
    E uma liberação em rascunho de 5000.00 em "2056-08-10" no órgão "70013", qualificador "2.9.91" e fonte "1.500" da vigência 2056
    Quando confirmo essa liberação sem confirmação explícita
    Então essa liberação está confirmada sem exigência extra
