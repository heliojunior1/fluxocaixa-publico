# language: pt
Funcionalidade: Tipo de instrumento financeiro e liquidez
  Como tesouraria, quero classificar cada compartimento de saldo pelo
  instrumento (fundo, CDB, poupança, Tesouro, conta movimento) e declarar a
  liquidez, para que a disponibilidade operacional some só o que é líquido —
  CDB com carência é patrimônio do caixa, não "posso pagar amanhã".
  Specs: saldo-por-fundo R22/R8/R9, fonte-recurso R5, desembolso R9.
  Ilha 2042 (fontes na vigência 2042, saldos em datas de 2042).

  Contexto:
    Dado que estou autenticado como administrador

  Cenário: Tipos de instrumento seedados como domínio
    Então os tipos de instrumento "FUNDO", "CONTA_MOVIMENTO", "CDB", "POUPANCA" e "TESOURO" existem ativos

  Cenário: Cadastro manual sem tipo explícito nasce FUNDO líquido
    Quando cadastro o fundo "9420" chamado "Fundo Exemplo Tipo Default"
    Então o instrumento "9420" tem tipo "FUNDO" e liquidez imediata "S"

  Cenário: Cadastro de CDB com carência e vencimento
    Quando cadastro o instrumento "9421" chamado "CDB Exemplo 2 Anos" com tipo "CDB", liquidez "N" e vencimento "2077-12-31"
    Então o instrumento "9421" tem tipo "CDB" e liquidez imediata "N"
    E o instrumento "9421" tem vencimento "2077-12-31"

  Cenário: Tipo de instrumento inexistente é rejeitado
    Quando cadastro o instrumento "9422" chamado "Instrumento Inválido" com o tipo inexistente
    Então a operação de instrumento é rejeitada com a mensagem "Tipo de instrumento inexistente ou inativo"

  Cenário: Fundo GERAL é conta movimento
    Dado o fundo padrão "GERAL" garantido
    Então o instrumento "GERAL" tem tipo "CONTA_MOVIMENTO" e liquidez imediata "S"

  Cenário: Auto-cadastrado por importação nasce FUNDO líquido
    Quando o upsert interno cria o instrumento desconhecido "9423"
    Então o instrumento "9423" tem tipo "FUNDO" e liquidez imediata "S"

  Cenário: Marcar carência em instrumento existente
    Dado um fundo manual "9424" chamado "Aplicação Que Vira CDB"
    Quando altero o instrumento "9424" para tipo "CDB", liquidez "N" e vencimento "2078-06-30"
    Então o instrumento "9424" tem tipo "CDB" e liquidez imediata "N"
    E o instrumento "9424" tem vencimento "2078-06-30"

  Cenário: Grupo separa o líquido do aplicado com carência
    Dado a fonte de instrumentos "1.742" cadastrada na vigência 2042 como "livre"
    E uma conta de instrumentos "001/0001/94201-1"
    E um instrumento líquido "9431" na fonte "1.742" da vigência 2042 com saldo de 1000.00 nessa conta em "2042-05-10"
    E um instrumento "9432" tipo "CDB" sem liquidez imediata na fonte "1.742" da vigência 2042 com saldo de 500.00 nessa conta em "2042-05-10"
    Então o grupo "L" em "2042-05-10" tem 1000.00 líquidos e 500.00 com carência

  Cenário: Soma de líquido e carência fecha com o agregado
    Dado a fonte de instrumentos "1.743" cadastrada na vigência 2042 como "vinculada"
    E uma conta de instrumentos "001/0001/94202-2"
    E um instrumento líquido "9433" na fonte "1.743" da vigência 2042 com saldo de 300.00 nessa conta em "2042-06-10"
    E um instrumento "9434" tipo "TESOURO" sem liquidez imediata na fonte "1.743" da vigência 2042 com saldo de 200.00 nessa conta em "2042-06-10"
    Então a soma de líquido e carência dos grupos em "2042-06-10" é igual ao agregado da conta de instrumentos em "2042-06-10"

  Cenário: Conciliação por fonte usa o patrimônio cheio
    Dado a fonte de instrumentos "1.744" cadastrada na vigência 2042 como "vinculada"
    E uma conta de instrumentos "001/0001/94203-3"
    E um instrumento líquido "9435" na fonte "1.744" da vigência 2042 com saldo de 1000.00 nessa conta em "2042-07-10"
    E um instrumento "9436" tipo "CDB" sem liquidez imediata na fonte "1.744" da vigência 2042 com saldo de 500.00 nessa conta em "2042-07-10"
    Então o saldo operacional da fonte "1.744" da vigência 2042 considera 1500.00

  Cenário: Saldo inicial da curva de simulação parte só do líquido
    Dado a fonte de instrumentos "1.745" cadastrada na vigência 2042 como "vinculada"
    E uma conta de instrumentos "001/0001/94204-4"
    E um cenário publicado vazio "SIM-LIQ-2042" para 2042
    E um instrumento líquido "9437" na fonte "1.745" da vigência 2042 com saldo de 1000.00 nessa conta em "2042-03-10"
    Quando simulo o grupo "V" para 2042 com o cenário "SIM-LIQ-2042" e registro a referência
    E acrescento o instrumento "9438" tipo "CDB" sem liquidez imediata na fonte "1.745" da vigência 2042 com saldo de 500.00 nessa conta em "2042-03-10"
    E simulo novamente o grupo "V" para 2042 com o cenário "SIM-LIQ-2042"
    Então o saldo inicial da simulação não se moveu
    E a carência informada pela simulação aumentou em 500.00
