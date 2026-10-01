# language: pt
Funcionalidade: Correspondência de rubricas entre exercícios (De/Para)
  Spec previsao R30–R33 (change correspondencia-rubricas-entre-exercicios)

  Fusão e desdobramento ficam no De/Para (a raiz segue só para a
  continuidade 1:1). A série de previsão do destino recebe a das origens
  antes da vigência: fusão soma; desdobramento reconstrói pela origem (se
  reconciliar), rateia (estimado) ou fica PENDENTE — e só o grupo inteiro
  dos destinos recebe a origem. Grupo pendente é projetado uma vez, sem
  rubrica. Todo gesto é evento; a versão do De/Para vai para a projeção.
  Ilhas 2082–2084, ramos de qualificador "1.82" e "2.82".

  # ------------------------------------------------------------ cadastro

  Cenário: Fusão cadastrada com ato
    Dado as rubricas "1.82.1" e "1.82.2" no plano de 2083 e "1.82.9" no plano de 2084
    Quando cadastro a fusão de "1.82.1" e "1.82.2" em "1.82.9" vigente em 2084
    Então a correspondência fica ativa
    E a versão do De/Para avança

  Cenário: Origem que continua ativa é recusada
    Dado as rubricas "1.82.1" e "1.82.2" no plano de 2083 e "1.82.9" no plano de 2084
    E a rubrica "1.82.1" também no plano de 2084 com a mesma identidade
    Quando cadastro a fusão de "1.82.1" e "1.82.2" em "1.82.9" vigente em 2084
    Então recebo erro de negócio citando "continua ativa"

  Cenário: Destino com a identidade da origem é recusado
    Dado as rubricas "1.82.1" e "1.82.2" no plano de 2083
    E a rubrica "1.82.9" no plano de 2084 herdando a identidade de "1.82.1"
    Quando cadastro a fusão de "1.82.1" e "1.82.2" em "1.82.9" vigente em 2084
    Então recebo erro de negócio citando "dupla contagem"

  Cenário: Natureza diferente é recusada
    Dado as rubricas "1.82.1" e "2.82.1" no plano de 2083 e "1.82.9" no plano de 2084
    Quando cadastro a fusão de "1.82.1" e "2.82.1" em "1.82.9" vigente em 2084
    Então recebo erro de negócio citando "natureza"

  Cenário: Rateio que não soma 100 é recusado
    Dado o desdobramento de "1.82.1" de 2083 em "1.82.3" e "1.82.4" vigente em 2084
    Quando defino o rateio "30" e "60"
    Então recebo erro de negócio citando "100"

  Cenário: Versão antiga continua reconstruível
    Dado o desdobramento de "1.82.1" de 2083 em "1.82.3" e "1.82.4" vigente em 2084
    E o rateio "30" e "70" registrado
    Quando defino o rateio "40" e "60"
    Então o De/Para na versão registrada mostra o rateio "30" e "70"
    E o De/Para atual mostra o rateio "40" e "60"

  # --------------------------------------------------------------- série

  Cenário: Fusão soma as origens
    Dado as rubricas "1.82.1" e "1.82.2" no plano de 2083 e "1.82.9" no plano de 2084
    E "1.82.1" com 100.00 por mês em 2083
    E "1.82.2" com 300.00 por mês em 2083
    E a fusão de "1.82.1" e "1.82.2" em "1.82.9" vigente em 2084
    Quando obtenho a série de 2083 de "1.82.9"
    Então cada mês da série vale 400.00
    E nenhum mês da série é estimado

  Cenário: Desdobramento reconstruído pela origem
    Dado "1.82.1" de 2083 com lançamentos automáticos de 70.00 com natureza "A82" e 30.00 com natureza "B82" por mês em 2083
    E o desdobramento de "1.82.1" de 2083 em "1.82.3" e "1.82.4" vigente em 2084 com as regras "Natureza = 'A82'" e "Natureza = 'B82'"
    Quando obtenho a série de 2083 de "1.82.3"
    Então cada mês da série vale 70.00
    E nenhum mês da série é estimado

  Cenário: Reconstrução que não reconcilia cai para o rateio
    Dado "1.82.1" de 2083 com lançamentos automáticos de 70.00 com natureza "A82" e 30.00 com natureza "B82" por mês em 2083
    E um lançamento manual de 10.00 em "1.82.1" de 2083 em março de 2083
    E o desdobramento de "1.82.1" de 2083 em "1.82.3" e "1.82.4" vigente em 2084 com as regras "Natureza = 'A82'" e "Natureza = 'B82'"
    E o rateio "70" e "30" registrado
    Quando obtenho a série de 2083 de "1.82.3"
    Então o mês 3 da série vale 77.00
    E o mês 1 da série vale 70.00
    E todos os meses da série são estimados

  Cenário: Desdobramento com rateio é estimado
    Dado "1.82.1" de 2083 com 1000.00 por mês em 2083
    E o desdobramento de "1.82.1" de 2083 em "1.82.3" e "1.82.4" vigente em 2084
    E o rateio "30" e "70" registrado
    Quando obtenho a série de 2083 de "1.82.3"
    Então cada mês da série vale 300.00
    E todos os meses da série são estimados

  Cenário: Desdobramento pendente não inventa a divisão
    Dado "1.82.1" de 2083 com 1000.00 por mês em 2083
    E o desdobramento de "1.82.1" de 2083 em "1.82.3" e "1.82.4" vigente em 2084
    Quando obtenho a série de 2083 de "1.82.3"
    Então a série é vazia
    E a pendência da série é declarada
    Quando obtenho a série conjunta de 2083 de "1.82.3" e "1.82.4"
    Então cada mês da série vale 1000.00

  Cenário: Correspondências encadeadas
    Dado "1.82.1" de 2082 com 1000.00 por mês em 2082
    E o desdobramento de "1.82.1" de 2082 em "1.82.3" e "1.82.4" vigente em 2083
    E o rateio "40" e "60" registrado
    E "1.82.3" de 2083 com 50.00 por mês em 2083
    E "1.82.5" de 2083 com 200.00 por mês em 2083
    E a rubrica "1.82.9" no plano de 2084
    E a fusão de "1.82.3" e "1.82.5" em "1.82.9" vigente em 2084
    Quando obtenho a série de 2082 de "1.82.9"
    Então cada mês da série vale 400.00
    Quando obtenho a série de 2083 de "1.82.9"
    Então cada mês da série vale 250.00

  # ------------------------------------------------- projeção pendente

  Cenário: Bloco com desdobramento pendente projeta o grupo
    Dado "1.82.1" de 2083 com 1000.00 por mês em 2083
    E o bloco "1.82" de 2084 com as folhas "1.82.3" e "1.82.4"
    E o desdobramento de "1.82.1" de 2083 em "1.82.3" e "1.82.4" vigente em 2084
    E um cenário de 2084 com o bloco "1.82" marcado com média histórica
    Quando executo a simulação do cenário
    Então a receita tem uma linha de grupo de 1000.00 por mês sem rubrica
    E "1.82.3" e "1.82.4" ficam com distribuição pendente

  Cenário: Método que não alcança o grupo inteiro vira lacuna
    Dado "1.82.1" de 2083 com 1000.00 por mês em 2083
    E o bloco "1.82" de 2084 com as folhas "1.82.3" e "1.82.4"
    E o desdobramento de "1.82.1" de 2083 em "1.82.3" e "1.82.4" vigente em 2084
    E um cenário de 2084 com a folha "1.82.3" marcada com média histórica
    Quando executo a simulação do cenário
    Então "1.82.3" fica em lacuna citando "1.82.4"

  Cenário: Publicar com distribuição pendente exige confirmação
    Dado "1.82.1" de 2083 com 1000.00 por mês em 2083
    E o bloco "1.82" de 2084 com as folhas "1.82.3" e "1.82.4"
    E o desdobramento de "1.82.1" de 2083 em "1.82.3" e "1.82.4" vigente em 2084
    E um cenário de 2084 com o bloco "1.82" marcado com média histórica
    Quando publico uma versão do cenário sem confirmar
    Então recebo erro de negócio citando "distribuição pendente"

  Cenário: Sugestão de rateio pelo realizado
    Dado o desdobramento de "1.82.1" de 2083 em "1.82.3" e "1.82.4" vigente em 2084
    E "1.82.3" de 2084 com 300.00 por mês em 2084
    E "1.82.4" de 2084 com 700.00 por mês em 2084
    Quando peço a sugestão de rateio
    Então a sugestão é "30.0000" para "1.82.3" e "70.0000" para "1.82.4"
    E o desdobramento continua sem rateio

  # ------------------------------------------------------------- versão

  Cenário: Versão salva guarda a versão do De/Para
    Dado "1.82.1" de 2083 com 1000.00 por mês em 2083
    E o bloco "1.82" de 2084 com as folhas "1.82.3" e "1.82.4"
    E o desdobramento de "1.82.1" de 2083 em "1.82.3" e "1.82.4" vigente em 2084
    E um cenário de 2084 com o bloco "1.82" marcado com média histórica
    Quando salvo uma versão do cenário
    Então o resumo da versão salva registra a versão atual do De/Para
    Quando defino o rateio "50" e "50"
    Então o resumo da versão salva continua com a versão anterior do De/Para
