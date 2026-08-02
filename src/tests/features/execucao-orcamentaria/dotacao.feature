# language: pt
Funcionalidade: Dotação e créditos adicionais (F8.1)
  Como Tesouro, quero o autorizado vivo — dotação inicial + créditos como
  eventos imutáveis — e o teto da liberação seguindo a dotação atualizada.

  Contexto:
    Dado que estou autenticado como administrador

  Cenário: Crédito suplementar soma na dotação atualizada
    Dado um qualificador folha de despesa "2.9.61" com dotação inicial de 12000.00 em 2047
    Quando registro um crédito "S" de 3000.00 na dotação do qualificador "2.9.61" de 2047 com o ato "lei-01"
    Então a dotação atualizada do qualificador "2.9.61" em 2047 é 15000.00

  Cenário: Redução subtrai e o histórico permanece
    Quando registro um crédito "R" de 1000.00 na dotação do qualificador "2.9.61" de 2047 com o ato "decreto-02"
    Então a dotação atualizada do qualificador "2.9.61" em 2047 é 14000.00
    E a dotação do qualificador "2.9.61" em 2047 tem 2 eventos de crédito

  Cenário: Redução além da atualizada é recusada
    Quando registro um crédito "R" de 20000.00 na dotação do qualificador "2.9.61" de 2047 com o ato "decreto-03"
    Então a operação de dotação é rejeitada com a mensagem "Redução acima da dotação atualizada — a dotação não pode ficar negativa"

  Cenário: Crédito sem ato é recusado
    Quando registro um crédito "S" de 500.00 na dotação do qualificador "2.9.61" de 2047 sem ato
    Então a operação de dotação é rejeitada com a mensagem "Referência do ato (lei/decreto) é obrigatória"

  Cenário: Dentro da dotação e acima da LOA confirma sem exigência extra
    Dado um órgão "70008" chamado "Secretaria do Orçamento"
    E a fonte "1.500" cadastrada na vigência 2047 como "livre"
    E um qualificador folha de despesa "2.9.62" com LOA de 1000.00 no ano 2047
    E um qualificador folha de despesa "2.9.62" com dotação inicial de 5000.00 em 2047
    E uma liberação em rascunho de 3000.00 em "2047-05-10" no órgão "70008", qualificador "2.9.62" e fonte "1.500" da vigência 2047
    Quando confirmo essa liberação sem confirmação explícita do teto
    Então essa liberação está confirmada sem exigência extra

  Cenário: Acima da dotação atualizada exige confirmação consciente
    Dado um órgão "70008" chamado "Secretaria do Orçamento"
    E uma liberação em rascunho de 3000.00 em "2047-06-10" no órgão "70008", qualificador "2.9.62" e fonte "1.500" da vigência 2047
    Quando confirmo essa liberação sem confirmação explícita do teto
    Então a operação de dotação é rejeitada com a mensagem "Liberação excede o autorizado do exercício em R$ 1000.00 — confirme explicitamente para prosseguir"
