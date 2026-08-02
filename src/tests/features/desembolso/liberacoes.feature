# language: pt
Funcionalidade: Liberações do desembolso (retrovisor)
  Como Tesouro, quero registrar liberações com fonte e natureza da obrigação,
  com transições rastreadas por eventos imutáveis e o saldo liberado pendente
  sempre derivado — nunca persistido.

  Contexto:
    Dado que estou autenticado como administrador
    E um órgão "70001" chamado "Secretaria de Teste"
    E a fonte "1.570" cadastrada na vigência 2038 como "livre"

  Cenário: Criação válida nasce rascunho com evento de criação
    Dado um qualificador folha de despesa "2.7.1"
    Quando crio uma liberação de 1234.56 em "2038-06-10" para o órgão "70001", qualificador "2.7.1" e fonte "1.570" da vigência 2038
    Então a liberação existe em rascunho com natureza "D"
    E a liberação tem um evento "CRIACAO"

  Cenário: Qualificador de receita é recusado
    Dado um qualificador folha de receita "1.7.9"
    Quando tento criar uma liberação em "2038-06-10" no qualificador "1.7.9" com a fonte "1.570" da vigência 2038
    Então a operação de liberação é rejeitada com a mensagem "Liberação exige qualificador de despesa"

  Cenário: Fonte é obrigatória e sem default
    Dado um qualificador folha de despesa "2.7.2"
    Quando tento criar uma liberação em "2038-06-10" no qualificador "2.7.2" sem fonte
    Então a operação de liberação é rejeitada com a mensagem "Fonte de recursos é obrigatória na liberação"

  Cenário: Valor não positivo é recusado
    Dado um qualificador folha de despesa "2.7.3"
    Quando tento criar uma liberação de valor 0.00 em "2038-06-10" no qualificador "2.7.3" com a fonte "1.570" da vigência 2038
    Então a operação de liberação é rejeitada com a mensagem "Valor da liberação deve ser positivo"

  Cenário: Confirmação grava evento e muda o estado
    Dado um qualificador folha de despesa "2.7.4"
    E uma liberação em rascunho de 1000.00 em "2038-06-11" no qualificador "2.7.4" com a fonte "1.570" da vigência 2038
    Quando confirmo essa liberação
    Então a situação dessa liberação é "C"
    E a liberação tem um evento "CONFIRMACAO"

  Cenário: Cancelar confirmada exige confirmação explícita
    Dado um qualificador folha de despesa "2.7.5"
    E uma liberação confirmada de 500.00 em "2038-06-12" no qualificador "2.7.5" com a fonte "1.570" da vigência 2038
    Quando cancelo essa liberação sem confirmação explícita
    Então a operação de liberação é rejeitada com a mensagem "Cancelar liberação confirmada exige confirmação explícita"
    E a situação dessa liberação é "C"

  Cenário: Cancelamento com apropriação é vetado
    Dado um qualificador folha de despesa "2.7.6"
    E uma liberação confirmada de 800.00 em "2038-06-13" no qualificador "2.7.6" com a fonte "1.570" da vigência 2038
    E uma apropriação de 300.00 nessa liberação
    Quando cancelo essa liberação com confirmação explícita
    Então a operação de liberação é rejeitada com a mensagem "Liberação possui apropriações — estorne-as antes de cancelar"

  Cenário: Rascunho não entra no pendente
    Dado um qualificador folha de despesa "2.7.7"
    E uma liberação confirmada de 1000.00 em "2038-06-15" no qualificador "2.7.7" com a fonte "1.570" da vigência 2038
    E uma liberação em rascunho de 500.00 em "2038-06-15" no qualificador "2.7.7" com a fonte "1.570" da vigência 2038
    Então o pendente do qualificador "2.7.7" é 1000.00

  Cenário: Apropriação e estorno movem o pendente
    Dado um qualificador folha de despesa "2.7.8"
    E uma liberação confirmada de 1000.00 em "2038-06-16" no qualificador "2.7.8" com a fonte "1.570" da vigência 2038
    E uma apropriação de 300.00 nessa liberação
    E um estorno de 100.00 nessa liberação
    Então o pendente do qualificador "2.7.8" é 800.00

  Cenário: Pendente recortado por fonte
    Dado a fonte "1.571" cadastrada na vigência 2038 como "vinculada"
    E um qualificador folha de despesa "2.7.9"
    E uma liberação confirmada de 400.00 em "2038-06-17" no qualificador "2.7.9" com a fonte "1.570" da vigência 2038
    E uma liberação confirmada de 250.00 em "2038-06-17" no qualificador "2.7.9" com a fonte "1.571" da vigência 2038
    Então o pendente da fonte "1.571" da vigência 2038 é 250.00

  Cenário: Liberação aparece no dia certo da visão semanal
    Dado um qualificador folha de despesa "2.7.10"
    E uma liberação confirmada de 777.00 em "2038-07-07" no qualificador "2.7.10" com a fonte "1.570" da vigência 2038
    Quando consulto a visão semanal de "2038-07-05"
    Então o total do dia "2038-07-07" na semana é 777.00

  Cenário: Órgão com liberação não inativa
    Dado um qualificador folha de despesa "2.7.11"
    E uma liberação confirmada de 100.00 em "2038-06-18" no qualificador "2.7.11" com a fonte "1.570" da vigência 2038
    Quando tento inativar o órgão "70001"
    Então a operação de liberação é rejeitada com a mensagem "Órgão possui liberações ativas e não pode ser inativado"

  Cenário: Confirmar exige permissão própria
    Dado um qualificador folha de despesa "2.7.12"
    E uma liberação em rascunho de 50.00 em "2038-06-19" no qualificador "2.7.12" com a fonte "1.570" da vigência 2038
    E um usuário do desembolso autenticado com o perfil "OPERADOR"
    Quando esse usuário tenta confirmar essa liberação pela rota
    Então a confirmação é negada com status 403
