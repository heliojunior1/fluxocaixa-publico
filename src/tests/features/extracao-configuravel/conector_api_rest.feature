# language: pt
Funcionalidade: Conector de API REST e resolvedor de mapeamento JSON
  Spec extracao-configuravel R19 e R20 (change conector-api-rest)

  Contexto:
    Dado que estou autenticado como administrador
    E um sistema de origem "SIS_X" cadastrado
    E o conector "API_REST" registrado
    E as contas de API cadastradas

  # --- R20: resolvedor de mapeamento ---

  Cenário: Mapeamento de item em campos destino
    Quando mapeio o item de fundo "9101" com saldo bruto "1850432.10"
    Então a linha mapeada tem fundo "9101" e saldo "1850432.10"

  Cenário: lista_path ausente trata a resposta como um item
    Quando mapeio uma resposta de saldo único sem lista_path
    Então o mapeamento produz 1 linhas e 0 erros

  Cenário: Caminho inexistente vira erro de linha
    Quando mapeio um item sem o campo de código do fundo
    Então o mapeamento produz 0 linhas e 1 erros

  # --- R19: conector API REST ---

  Cenário: Conta com fundos vira uma linha por item
    Dado uma fonte "API BB" que devolve 2 fundos para a conta "12345"
    Quando executo a fonte "API BB" para o dia "2026-07-10"
    Então a execução de API registra status "SUCESSO" com 2 inseridas e 0 com erro

  Cenário: Conta sem fundos é pulada
    Dado uma fonte "API Vazia" cuja conta "37001" não tem fundos
    Quando executo a fonte "API Vazia" para o dia "2026-07-10"
    Então a execução de API registra status "SEM_DADOS" com 0 inseridas e 0 com erro

  Cenário: 401 renova o token uma vez
    Dado uma fonte "API 401" que responde 401 na primeira chamada e 200 após renovar
    Quando executo a fonte "API 401" para o dia "2026-07-10"
    Então a execução de API registra status "SUCESSO" com 2 inseridas e 0 com erro
    E o token foi renovado uma vez

  Cenário: 429 aplica backoff e depois sucede
    Dado uma fonte "API 429" que responde 429 e depois 200
    Quando executo a fonte "API 429" para o dia "2026-07-10"
    Então a execução de API registra status "SUCESSO" com 2 inseridas e 0 com erro

  Cenário: Erro numa conta é pontual
    Dado uma fonte "API Parcial" com a conta "12345" ok e a conta "9999" respondendo 500
    Quando executo a fonte "API Parcial" para o dia "2026-07-10"
    Então a execução de API registra status "PARCIAL" com 2 inseridas e 1 com erro

  Cenário: Snapshot único em backfill
    Dado uma fonte "API Backfill" que devolve 2 fundos para a conta "12345"
    Quando executo a fonte "API Backfill" de "2026-07-08" a "2026-07-10"
    Então a execução de API registra status "SUCESSO" com 2 inseridas e 0 com erro
    E os saldos gravados têm data "2026-07-10"
    E o detalhe da execução de API menciona "sem histórico"
