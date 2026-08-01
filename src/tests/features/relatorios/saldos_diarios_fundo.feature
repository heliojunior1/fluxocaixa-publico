# language: pt
Funcionalidade: Relatório de saldos diários por fundo
  Evolução do relatório de saldos diários para o modelo de saldo por fundo
  (spec relatorios R14–R16): saldo inicial derivado (LAG histórico),
  rendimento do dia, origem consolidada, saldo registrado, divergência vs
  saldo registrado do dia seguinte, modo Agregado × Por fundo com filtro por
  conta e série de evolução de 30 dias preservada.

  # Isolamento: ilha de datas 2037 (2031–2036 são de KPIs/DFC; seed demo em
  # 2022–2026) e contas fictícias próprias. Ataque na camada de serviço
  # (get_saldos_diarios_data); a página é coberta pelo E2E.

  # ------------------------------------------------------------------ R14

  Cenário: Saldo inicial derivado, rendimento e origem consolidada
    Dado uma conta diária "001/0001/SD-1" com saldo por fundo de "1000.00" em "2037-07-10"
    E a conta diária "001/0001/SD-1" com saldo por fundo de "1012.34" em "2037-07-15"
    Quando consulto os saldos diários de "2037-07-15" no modo "agregado"
    Então a linha da conta "001/0001/SD-1" tem saldo inicial "1000.00"
    E a linha da conta "001/0001/SD-1" tem rendimento do dia "12.34"
    E a linha da conta "001/0001/SD-1" tem saldo registrado "1012.34"
    E a linha da conta "001/0001/SD-1" tem origem consolidada "Manual"

  Cenário: Divergência vs saldo registrado do dia seguinte
    Dado uma conta diária "001/0001/SD-2" com saldo por fundo de "1450.00" em "2037-08-09"
    E um lançamento de entrada de "50.00" para a conta "001/0001/SD-2" em "2037-08-10"
    E a conta diária "001/0001/SD-2" com saldo por fundo de "1480.00" em "2037-08-11"
    Quando consulto os saldos diários de "2037-08-10" no modo "agregado"
    Então a linha da conta "001/0001/SD-2" tem saldo final calculado "1500.00"
    E a linha da conta "001/0001/SD-2" tem divergência "-20.00"

  Cenário: Sem saldo registrado no dia seguinte não há divergência
    Dado uma conta diária "001/0001/SD-3" com saldo por fundo de "700.00" em "2037-07-15"
    Quando consulto os saldos diários de "2037-07-15" no modo "agregado"
    Então a linha da conta "001/0001/SD-3" tem divergência nula

  Cenário: Conta sem dia anterior com saldo não tem saldo inicial
    Dado uma conta diária "001/0001/SD-4" com saldo por fundo de "900.00" em "2037-09-15"
    Quando consulto os saldos diários de "2037-09-15" no modo "agregado"
    Então a linha da conta "001/0001/SD-4" tem saldo inicial nulo

  # ------------------------------------------------------------------ R15

  Cenário: Linha por fundo com rendimento calculado
    Dado uma conta diária "104/0001/SD-5" com saldo do fundo "9903" de "100.00" em "2037-07-14"
    E a conta diária "104/0001/SD-5" com saldo do fundo "9903" de "112.34" em "2037-07-15"
    Quando consulto os saldos diários de "2037-07-15" no modo "fundo"
    Então a linha do fundo "9903" da conta "104/0001/SD-5" tem saldo inicial "100.00"
    E a linha do fundo "9903" da conta "104/0001/SD-5" tem rendimento "12.34"
    E a linha do fundo "9903" da conta "104/0001/SD-5" tem saldo "112.34"

  Cenário: Fundo sem saldo na data não gera linha
    Dado uma conta diária "104/0001/SD-6" com saldo do fundo "9904" de "300.00" em "2037-10-14"
    Quando consulto os saldos diários de "2037-10-15" no modo "fundo"
    Então não há linha do fundo "9904" para a conta "104/0001/SD-6"

  Cenário: Totais coincidem entre os modos
    Dado uma conta diária "104/0001/SD-7" com saldo do fundo "9905" de "300.00" em "2037-11-15"
    E a conta diária "104/0001/SD-7" com saldo do fundo "9906" de "200.00" em "2037-11-15"
    Quando consulto os saldos diários de "2037-11-15" no modo "fundo" filtrando pela conta "104/0001/SD-7"
    Então o total de saldo do modo fundo é "500.00"
    Quando consulto os saldos diários de "2037-11-15" no modo "agregado" filtrando pela conta "104/0001/SD-7"
    Então a linha da conta "104/0001/SD-7" tem saldo registrado "500.00"

  # ------------------------------------------------------------------ R16

  Cenário: Filtro por conta nos dois modos
    Dado uma conta diária "001/0001/SD-8" com saldo por fundo de "800.00" em "2037-12-15"
    E uma conta diária "104/0001/SD-9" com saldo por fundo de "600.00" em "2037-12-15"
    Quando consulto os saldos diários de "2037-12-15" no modo "agregado" filtrando pela conta "001/0001/SD-8"
    Então apenas a conta "001/0001/SD-8" aparece nas linhas
    Quando consulto os saldos diários de "2037-12-15" no modo "fundo" filtrando pela conta "001/0001/SD-8"
    Então todas as linhas por fundo são da conta "001/0001/SD-8"

  Cenário: Evolução de 30 dias presente em qualquer modo
    Dado uma conta diária "001/0001/SD-1" com saldo por fundo de "1000.00" em "2037-07-10"
    Quando consulto os saldos diários de "2037-07-15" no modo "fundo"
    Então a série de evolução tem 30 pontos terminando em "2037-07-15"
