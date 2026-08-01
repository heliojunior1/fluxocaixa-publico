# language: pt
Funcionalidade: Folha dinâmica em qualquer nível
  Spec `cadastros-nucleo` R12–R14: folha é o nó sem filhos ativos, em qualquer
  profundidade, com UMA origem para a resposta; transformar folha com
  lançamentos em pai exige confirmação; ajuste de cenário só aponta para folha.

  A cadeia de teste nasce em "1.7" de propósito, sob a raiz de RECEITA: as
  consultas de folha do repositório são recortadas por código começando em "1",
  e uma raiz inventada não passaria por elas — o teste ficaria verde sem
  exercitar o que a feature muda.

  # ------------------------------------------------------------------ R12

  Esquema do Cenário: Folha recebe lançamento em qualquer profundidade
    Dado uma cadeia de qualificadores com <nivel> níveis a partir de "1.7"
    Quando crio um lançamento na ponta da cadeia
    Então o lançamento é aceito

    Exemplos:
      | nivel |
      | 1     |
      | 2     |
      | 3     |
      | 4     |
      | 5     |
      | 6     |

  Cenário: Nó com filho ativo não é folha, mesmo no quinto nível
    Dado uma cadeia de qualificadores com 6 níveis a partir de "1.7"
    Quando crio um lançamento no penúltimo nó da cadeia
    Então vejo o erro "Lançamentos só podem ser feitos em qualificadores folha"

  Cenário: Nó cujos filhos foram todos inativados volta a ser folha
    Dado uma cadeia de qualificadores com 3 níveis a partir de "1.7"
    Quando inativo a ponta da cadeia
    E crio um lançamento no penúltimo nó da cadeia
    Então o lançamento é aceito

  Cenário: Filho com código fora do prefixo do pai não esconde o pai da lista
    # Estado que o R3 impede criar hoje, mas que dado legado tem e que a
    # reapontação de pai produz: o filho não casa com o prefixo do pai. A
    # listagem por prefixo classificava o pai como folha; a validação não.
    Dado um qualificador "1.7.4" chamado "Pai Com Filho Fora Do Prefixo"
    E um filho legado "2.7.4.1" apontado para "1.7.4"
    Quando confronto as folhas listadas com a validação de lançamento
    Então todo qualificador não listado é recusado por ela
    E toda folha listada é aceita pela validação

  Cenário: A lista de folhas e a validação de lançamento concordam
    Dado uma cadeia de qualificadores com 6 níveis a partir de "1.7"
    E um qualificador "1.7.9" chamado "Ramo Irmao" com o filho "1.7.9.1"
    Quando confronto as folhas listadas com a validação de lançamento
    Então toda folha listada é aceita pela validação
    E todo qualificador não listado é recusado por ela

  Cenário: O código comporta 6 níveis com três dígitos por segmento
    # ⚠️ Só o round-trip do valor NÃO prova nada: SQLite não impõe tamanho de
    # VARCHAR e grava calado. Quem recusa é o PostgreSQL. Por isso a asserção
    # é sobre a CAPACIDADE DECLARADA da coluna, não sobre o que o SQLite fez.
    Quando cadastro a cadeia até o código "1.100.200.300.400.500"
    Então o código gravado é "1.100.200.300.400.500"
    E a coluna do código comporta "1.100.200.300.400.500"

  # ------------------------------------------------------------------ R13

  Cenário: Criar filho sob folha com lançamentos, sem confirmar
    Dado uma folha "1.7.1" chamada "Folha Com Lancamento" com lançamentos ativos
    Quando cadastro o filho "1.7.1.1" sob ela sem confirmar
    Então vejo o erro "confirme"
    E o qualificador "1.7.1.1" não existe
    E o qualificador "1.7.1" continua sendo folha

  Cenário: Criar filho sob folha com lançamentos, confirmando
    Dado uma folha "1.7.1" chamada "Folha Com Lancamento" com lançamentos ativos
    Quando cadastro o filho "1.7.1.1" sob ela confirmando
    Então o qualificador "1.7.1.1" existe
    E o qualificador "1.7.1" deixa de ser folha

  Cenário: Reapontar um qualificador para uma folha com lançamentos
    Dado uma folha "1.7.1" chamada "Folha Com Lancamento" com lançamentos ativos
    E um qualificador "1.7.2" chamado "Rubrica Solta" sem pai definido
    Quando reaponto "1.7.2" para ser filho de "1.7.1" sem confirmar
    Então vejo o erro "confirme"
    E o qualificador "1.7.1" continua sendo folha

  Cenário: Folha sem lançamentos não pede confirmação
    Dado uma folha "1.7.3" chamada "Folha Vazia" sem lançamentos
    Quando cadastro o filho "1.7.3.1" sob ela sem confirmar
    Então o qualificador "1.7.3.1" existe

  Cenário: Nó que já é pai não pede confirmação
    Dado uma cadeia de qualificadores com 2 níveis a partir de "1.7"
    Quando cadastro o filho "1.7.1.8" sob o primeiro nó da cadeia sem confirmar
    Então o qualificador "1.7.1.8" existe

  # ------------------------------------------------------------------ R14

  Cenário: Ajuste de cenário em qualificador pai é rejeitado
    Dado uma cadeia de qualificadores com 2 níveis a partir de "1.7"
    Quando salvo um cenário com ajuste manual no primeiro nó da cadeia
    Então vejo o erro "folha"
    E nenhum ajuste foi gravado

  Cenário: Ajuste de cenário em folha é aceito
    Dado uma cadeia de qualificadores com 2 níveis a partir de "1.7"
    Quando salvo um cenário com ajuste manual na ponta da cadeia
    Então o ajuste foi gravado
