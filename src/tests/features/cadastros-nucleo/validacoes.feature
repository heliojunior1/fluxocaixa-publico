# language: pt
Funcionalidade: Validações dos cadastros do núcleo
  Como tesouraria, quero que dados inválidos sejam rejeitados com mensagem
  clara na tela — nunca com erro genérico do servidor.

  Contexto:
    Dado que estou autenticado como administrador

  Cenário: Lançamento com valor zero é rejeitado com mensagem na tela
    Dado um qualificador folha ativo "9.1.1" chamado "Rubrica de Teste Folha"
    Quando crio um lançamento de valor "0" no qualificador "9.1.1"
    Então vejo a mensagem "O valor do lançamento deve ser positivo"
    E nenhum lançamento novo existe no qualificador "9.1.1"

  Cenário: Lançamento em qualificador pai é rejeitado
    Dado um qualificador "9.2" chamado "Rubrica Pai de Teste" com o filho ativo "9.2.1" chamado "Rubrica Filha de Teste"
    Quando crio um lançamento de valor "100.00" no qualificador "9.2"
    Então vejo a mensagem "Lançamentos só podem ser feitos em qualificadores folha"
    E nenhum lançamento novo existe no qualificador "9.2"

  Cenário: Lançamento em qualificador inativo é rejeitado
    Dado um qualificador folha inativo "9.3.9" chamado "Rubrica Inativa de Teste"
    Quando crio um lançamento de valor "100.00" no qualificador "9.3.9"
    Então vejo a mensagem "Qualificador inexistente ou inativo"

  Cenário: Data do lançamento é imutável na edição
    Dado um qualificador folha ativo "9.4.1" chamado "Rubrica Data Imutável"
    E um lançamento Manual de valor "500.00" em "2026-07-10" no qualificador "9.4.1"
    Quando edito esse lançamento alterando a data para "2026-07-11"
    Então vejo a mensagem "A data do lançamento não pode ser alterada"
    E o lançamento permanece com a data "2026-07-10"

  Cenário: Lançamento de origem Automático é intocável
    Dado um qualificador folha ativo "9.5.1" chamado "Rubrica Origem Teste"
    E um lançamento de origem "Automático" de valor "700.00" no qualificador "9.5.1"
    Quando edito esse lançamento alterando o valor para "999.00"
    Então vejo a mensagem "não podem ser alterados ou excluídos"
    Quando excluo esse lançamento
    Então vejo a mensagem "não podem ser alterados ou excluídos"
    E o lançamento permanece ativo com valor "700.00"

  Esquema do Cenário: Qualificador inválido é rejeitado
    Dado um qualificador "9.6" chamado "Pai Para Esquema" com o filho ativo "9.6.1" chamado "Filho Para Esquema"
    Quando cadastro um qualificador com código "<codigo>", descrição "<descricao>" e pai "<pai>"
    Então vejo a mensagem "<mensagem>"

    Exemplos:
      | codigo | descricao            | pai  | mensagem                                                       |
      | 1.a.2  | Código Inválido      | -    | Código do qualificador deve conter apenas números separados por pontos |
      | 3.1    | Filho Fora do Pai    | 9.6  | O código do filho deve começar com o código do pai (9.6.)      |
      | 9.6.1  | Descrição Nova       | 9.6  | Já existe um qualificador com este código                      |
      | 9.9.9  | Filho Para Esquema   | -    | Já existe um qualificador com esta descrição                   |

  Cenário: Não inativa qualificador com filhos ativos
    Dado um qualificador "9.7" chamado "Pai Com Filho Ativo" com o filho ativo "9.7.1" chamado "Filho Ativo de Teste"
    Quando excluo o qualificador "9.7"
    Então vejo a mensagem "Qualificador possui filhos ativos"
    E o qualificador "9.7" permanece ativo

  Cenário: Exclusão de folha com lançamentos exige confirmação
    Dado um qualificador folha ativo "9.8.1" chamado "Folha Com Lançamentos"
    E um lançamento Manual de valor "300.00" em "2026-07-01" no qualificador "9.8.1"
    Quando excluo o qualificador "9.8.1"
    Então vejo a mensagem "confirme a exclusão"
    E o qualificador "9.8.1" permanece ativo
    Quando excluo o qualificador "9.8.1" com confirmação
    Então o qualificador "9.8.1" está inativo
