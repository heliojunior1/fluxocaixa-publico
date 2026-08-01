# language: pt
Funcionalidade: Ciclo de vida do fundo (cadastro, aprovação, inativação)
  Como tesouraria, quero gerir fundos manualmente e revisar os
  auto-cadastrados pelas importações, com integridade preservada.

  Contexto:
    Dado que estou autenticado como administrador

  Cenário: Cadastro manual bem-sucedido
    Quando cadastro o fundo "5462" com descrição "FUNDO EXEMPLO FI PLUS"
    Então o fundo "5462" existe ativo, aprovado, com origem "MANUAL" e sem sistema
    E a auditoria do fundo "5462" registra o usuário da sessão

  Cenário: Código duplicado é rejeitado
    Dado um fundo manual "5401" chamado "FUNDO EXEMPLO"
    Quando cadastro o fundo "5401" com descrição "Outro nome"
    Então a operação de fundo é rejeitada com a mensagem "Já existe um fundo com este código"

  Cenário: Código fora do tamanho é rejeitado
    Quando cadastro o fundo "12" com descrição "Curto demais"
    Então a operação de fundo é rejeitada com a mensagem "Código do fundo deve ter entre 4 e 10 caracteres"

  Cenário: Descrição obrigatória
    Quando cadastro o fundo "5402" com descrição ""
    Então a operação de fundo é rejeitada com a mensagem "Descrição do fundo é obrigatória"

  Cenário: Alteração de descrição
    Dado um fundo manual "5410" chamado "FUNDO EXEMPLO"
    Quando altero a descrição do fundo "5410" para "FUNDO EXEMPLO FI PLUS"
    Então o fundo "5410" tem descrição "FUNDO EXEMPLO FI PLUS"

  Cenário: Tentativa de alterar o código é rejeitada
    Dado um fundo manual "5411" chamado "FUNDO EXEMPLO"
    Quando tento alterar o código do fundo "5411" para "9999"
    Então a operação de fundo é rejeitada com a mensagem "O código do fundo não pode ser alterado"

  Cenário: Aprovação simples preserva origem e data
    Dado um sistema de origem "SIS_X" cadastrado
    E um fundo pendente "7001" auto-cadastrado pelo sistema "SIS_X"
    Quando aprovo o fundo "7001" sem alterar a descrição
    Então o fundo "7001" não está mais pendente
    E o fundo "7001" mantém origem "AUTOMATIZADO", sistema "SIS_X" e a data de auto-cadastro

  Cenário: Aprovação ajustando a descrição
    Dado um sistema de origem "SIS_X" cadastrado
    E um fundo pendente "7002" auto-cadastrado pelo sistema "SIS_X"
    Quando aprovo o fundo "7002" com a descrição "FUNDO EXEMPLO FI PLUS"
    Então o fundo "7002" não está mais pendente
    E o fundo "7002" tem descrição "FUNDO EXEMPLO FI PLUS"

  Cenário: Aprovar fundo não pendente é rejeitado
    Dado um fundo manual "5412" chamado "FUNDO EXEMPLO"
    Quando aprovo o fundo "5412" sem alterar a descrição
    Então a operação de fundo é rejeitada com a mensagem "Fundo não está pendente de revisão"

  Cenário: Inativação bloqueada por saldo ativo
    Dado uma conta de fundo "088/0001/1-1"
    E um fundo manual "5420" chamado "FUNDO EXEMPLO"
    E um saldo ativo do fundo "5420" nessa conta em "2026-07-10"
    Quando inativo o fundo "5420"
    Então a operação de fundo é rejeitada com a mensagem "Fundo possui saldos ativos e não pode ser inativado"
    E o fundo "5420" permanece ativo

  Cenário: Inativação sem saldo ativo
    Dado um fundo manual "5421" chamado "FUNDO EXEMPLO"
    Quando inativo o fundo "5421"
    Então o fundo "5421" está inativo

  Cenário: Filtro por pendentes de revisão
    Dado um sistema de origem "SIS_X" cadastrado
    E um fundo manual "1234" chamado "Fundo Aprovado A"
    E um fundo pendente "7003" auto-cadastrado pelo sistema "SIS_X"
    Quando listo os fundos filtrando por pendentes
    Então a lista de fundos contém "7003"
    E a lista de fundos não contém "1234"

  Cenário: Upsert cria fundo pendente na primeira aparição
    Dado um sistema de origem "SIS_X" cadastrado
    Quando o upsert de fundo é chamado para "7777" com sistema "SIS_X"
    Então o fundo "7777" existe pendente, com origem "AUTOMATIZADO", sistema "SIS_X" e data de auto-cadastro

  Cenário: Upsert é idempotente na reentrada
    Dado um sistema de origem "SIS_X" cadastrado
    E o upsert de fundo já criou "7778" pelo sistema "SIS_X"
    Quando o upsert de fundo é chamado para "7778" com sistema "SIS_X" e outra descrição
    Então existe exatamente 1 fundo com código "7778"
    E o fundo "7778" continua pendente

  Cenário: Upsert não altera fundo já aprovado
    Dado um fundo manual "5430" chamado "FUNDO EXEMPLO"
    E um sistema de origem "SIS_X" cadastrado
    Quando o upsert de fundo é chamado para "5430" com sistema "SIS_X"
    Então o fundo "5430" continua aprovado, com origem "MANUAL" e sem sistema

  Cenário: Perfil OPERADOR não cadastra fundo
    Dado um usuário autenticado com o perfil "OPERADOR"
    Quando o operador tenta cadastrar um fundo pela rota
    Então o operador recebe status 403
