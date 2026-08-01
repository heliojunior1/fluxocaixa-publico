# language: pt
Funcionalidade: Ciclo de vida da conta bancária (cadastro, alteração, inativação)
  Como tesouraria, quero gerir contas bancárias em tela, com a tripla
  banco/agência/conta protegida quando houver histórico vinculado.
  Todos os identificadores são fictícios (repositório público).

  Contexto:
    Dado que estou autenticado como administrador

  Cenário: Cadastro manual bem-sucedido
    Quando cadastro a conta bancária "001/0001/12345-6" com descrição "Conta Movimento"
    Então a conta "001/0001/12345-6" existe ativa com descrição "Conta Movimento"
    E a auditoria da conta "001/0001/12345-6" registra o usuário da sessão

  Cenário: Tripla duplicada é rejeitada
    Dado uma conta bancária cadastrada "001/0001/22222-2"
    Quando cadastro a conta bancária "001/0001/22222-2" com descrição "Duplicada"
    Então a operação de conta é rejeitada com a mensagem "Já existe uma conta bancária com este banco, agência e conta."
    E existe exatamente 1 conta "001/0001/22222-2"

  Cenário: Código do banco obrigatório
    Quando cadastro a conta bancária "/0001/12345-6" com descrição "Sem banco"
    Então a operação de conta é rejeitada com a mensagem "O campo código do banco é obrigatório."

  Cenário: Agência obrigatória
    Quando cadastro a conta bancária "001//12345-6" com descrição "Sem agência"
    Então a operação de conta é rejeitada com a mensagem "O campo agência é obrigatório."

  Cenário: Número da conta obrigatório
    Quando cadastro a conta bancária "001/0001/" com descrição "Sem conta"
    Então a operação de conta é rejeitada com a mensagem "O campo número da conta é obrigatório."

  Cenário: Identificadores são normalizados com trim
    Quando cadastro a conta bancária " 001 / 0001 / 33333-3 " com descrição "Com espaços"
    Então a conta "001/0001/33333-3" existe ativa com descrição "Com espaços"

  Cenário: Descrição é sempre editável
    Dado uma conta bancária cadastrada "001/0001/44444-4"
    E um lançamento vinculado à conta "001/0001/44444-4"
    Quando altero a descrição da conta "001/0001/44444-4" para "Conta Arrecadação"
    Então a conta "001/0001/44444-4" existe ativa com descrição "Conta Arrecadação"
    E a auditoria de alteração da conta "001/0001/44444-4" registra o usuário da sessão

  Cenário: Tripla imutável com lançamento vinculado
    Dado uma conta bancária cadastrada "001/0001/55555-5"
    E um lançamento vinculado à conta "001/0001/55555-5"
    Quando altero a tripla da conta "001/0001/55555-5" para "001/0001/99999-9"
    Então a operação de conta é rejeitada com a mensagem "A conta possui saldos ou lançamentos vinculados; banco, agência e conta não podem ser alterados."
    E a conta "001/0001/55555-5" continua existindo

  Cenário: Tripla imutável com saldo vinculado
    Dado uma conta bancária cadastrada "001/0001/66666-6"
    E um saldo ativo na conta "001/0001/66666-6" em "2026-07-10"
    Quando altero a tripla da conta "001/0001/66666-6" para "104/0002/66666-6"
    Então a operação de conta é rejeitada com a mensagem "A conta possui saldos ou lançamentos vinculados; banco, agência e conta não podem ser alterados."

  Cenário: Tripla editável sem vínculos
    Dado uma conta bancária cadastrada "001/0001/77777-7"
    Quando altero a tripla da conta "001/0001/77777-7" para "104/0002/77777-7"
    Então a conta "104/0002/77777-7" continua existindo

  Cenário: Tripla nova não pode colidir
    Dado uma conta bancária cadastrada "001/0001/88888-8"
    E uma conta bancária cadastrada "001/0001/98888-8"
    Quando altero a tripla da conta "001/0001/88888-8" para "001/0001/98888-8"
    Então a operação de conta é rejeitada com a mensagem "Já existe uma conta bancária com este banco, agência e conta."
    E a conta "001/0001/88888-8" continua existindo

  Cenário: Inativação bloqueada por saldo ativo
    Dado uma conta bancária cadastrada "104/0002/11111-1"
    E um saldo ativo na conta "104/0002/11111-1" em "2026-07-10"
    Quando inativo a conta "104/0002/11111-1"
    Então a operação de conta é rejeitada com a mensagem "Conta possui saldos ativos e não pode ser inativada."
    E a conta "104/0002/11111-1" permanece ativa

  Cenário: Inativação com apenas lançamentos históricos
    Dado uma conta bancária cadastrada "104/0002/22222-2"
    E um lançamento vinculado à conta "104/0002/22222-2"
    Quando inativo a conta "104/0002/22222-2"
    Então a conta "104/0002/22222-2" está inativa
    E o lançamento da conta "104/0002/22222-2" permanece ativo

  Cenário: Conta inativada some do combo de contas ativas
    Dado uma conta bancária cadastrada "104/0002/33333-3"
    Quando inativo a conta "104/0002/33333-3"
    Então a conta "104/0002/33333-3" não aparece entre as contas ativas

  Cenário: Reativação de conta inativa
    Dado uma conta bancária cadastrada "104/0002/44444-4"
    E a conta "104/0002/44444-4" foi inativada
    Quando reativo a conta "104/0002/44444-4"
    Então a conta "104/0002/44444-4" permanece ativa
    E a conta "104/0002/44444-4" aparece entre as contas ativas

  Cenário: Reativar conta ativa é rejeitado
    Dado uma conta bancária cadastrada "104/0002/55555-5"
    Quando reativo a conta "104/0002/55555-5"
    Então a operação de conta é rejeitada com a mensagem "Conta já está ativa."

  Cenário: Listagem default traz só ativas
    Dado uma conta bancária cadastrada "237/0003/11111-1"
    E uma conta bancária cadastrada "237/0003/22222-2"
    E a conta "237/0003/22222-2" foi inativada
    Quando listo as contas bancárias com status "ativas"
    Então a lista de contas contém "237/0003/11111-1"
    E a lista de contas não contém "237/0003/22222-2"

  Cenário: Filtro por status "todas" inclui inativas
    Dado uma conta bancária cadastrada "237/0003/33333-3"
    E a conta "237/0003/33333-3" foi inativada
    Quando listo as contas bancárias com status "todas"
    Então a lista de contas contém "237/0003/33333-3"

  Cenário: Filtro por número da conta
    Dado uma conta bancária cadastrada "237/0003/44444-4"
    E uma conta bancária cadastrada "237/0003/55555-5"
    Quando listo as contas bancárias filtrando pelo número "44444-4"
    Então a lista de contas contém "237/0003/44444-4"
    E a lista de contas não contém "237/0003/55555-5"

  Cenário: Perfil OPERADOR não cadastra conta bancária
    Dado um usuário autenticado com o perfil "OPERADOR"
    Quando o operador tenta cadastrar uma conta bancária pela rota
    Então o operador recebe status 403
