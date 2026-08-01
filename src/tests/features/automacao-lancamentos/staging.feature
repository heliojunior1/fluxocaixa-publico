# language: pt
Funcionalidade: Staging genérica da automação de lançamentos
  Spec automacao-lancamentos R1–R4 (change staging-generica-etl)

  Contexto:
    Dado que estou autenticado como administrador
    E um sistema de origem "SIS_X" cadastrado
    E o conector "BANCO_SQL" registrado

  # --- R2: cadastro de fonte LANCAMENTO ---

  Cenário: Fonte LANCAMENTO válida é criada
    Quando cadastro a fonte de lançamento "Lanc ERP" com layout de staging válido
    Então a fonte "Lanc ERP" existe com destino "LANCAMENTO"

  Cenário: Fonte LANCAMENTO sem valor/data mapeados é rejeitada
    Quando cadastro a fonte de lançamento "Lanc Ruim" com layout sem val_saldo
    Então o cadastro de lançamento é rejeitado
    E a fonte "Lanc Ruim" não existe

  # --- R3: execução grava na staging ---

  Cenário: Carga de lançamentos popula a staging
    Dado um banco externo com 3 lançamentos em 10/07/2026
    E uma fonte de lançamento "Carga OK" apontando para esse banco
    Quando executo a fonte de lançamento "Carga OK" de "2026-07-10" a "2026-07-10"
    Então a execução de lançamento registra status "SUCESSO" com 3 gravadas e 0 com erro
    E a staging tem 3 linhas pendentes da fonte "Carga OK"
    E cada linha da staging guarda a linha crua em json_atributos

  Cenário: Linha inválida vira erro pontual
    Dado um banco externo com 2 lançamentos válidos e 1 com valor inválido em 10/07/2026
    E uma fonte de lançamento "Carga Parcial" apontando para esse banco
    Quando executo a fonte de lançamento "Carga Parcial" de "2026-07-10" a "2026-07-10"
    Então a execução de lançamento registra status "PARCIAL" com 2 gravadas e 1 com erro

  Cenário: Staging vazia não segue silenciosa
    Dado um banco externo sem lançamentos
    E uma fonte de lançamento "Carga Vazia" apontando para esse banco
    Quando executo a fonte de lançamento "Carga Vazia" de "2026-07-10" a "2026-07-10"
    Então a execução de lançamento registra status "SEM_DADOS" com 0 gravadas e 0 com erro
    E o detalhe da execução de lançamento menciona "nenhuma linha extraída"

  # --- R1/R4: status e reprocessamento ---

  Cenário: Marcar erro trunca a mensagem
    Dado uma linha pendente na staging
    Quando marco a linha da staging como erro com uma mensagem de 800 caracteres
    Então a linha da staging fica com status "2" e dsc_erro com no máximo 500 caracteres

  Cenário: Reprocessar execução zera o status
    Dado um banco externo com 3 lançamentos em 10/07/2026
    E uma fonte de lançamento "Carga Reproc" apontando para esse banco
    E que executei a fonte de lançamento "Carga Reproc" para o dia "2026-07-10"
    E que as linhas dessa execução estão com status "1" e "2"
    Quando reprocesso a execução da fonte "Carga Reproc"
    Então todas as linhas da execução voltam ao status "0" com dsc_erro vazio
