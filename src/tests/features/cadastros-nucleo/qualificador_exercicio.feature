# language: pt
Funcionalidade: Qualificador por exercício e identidade estável
  Spec `cadastros-nucleo` R25–R27 (change qualificador-exercicio-identidade,
  F10.1): todo qualificador pertence a um exercício (`num_ano_exercicio`),
  a unicidade do código é por (exercício, código) entre ativos, pai e filho
  vivem no mesmo exercício, e a identidade estável (`cod_rubrica_raiz`)
  nasce uma vez e sobrevive a renome, renumeração e reapontamento.

  Ramo "7.4" — fora das raízes 1/2, para não entrar nas varreduras de
  relatório de outros testes. Ilhas de exercício 2070/2071/2072 (padrão do
  roadmap F10.x: anos-ilha ≥ 2070).

  Cenário: Mesmo código convive em exercícios diferentes
    Dado o qualificador "7.4" chamado "Bloco Setenta" no exercício 2070
    Quando crio o qualificador "7.4" chamado "Bloco Setenta B" no exercício 2071
    Então o qualificador "7.4" existe nos exercícios 2070 e 2071

  Cenário: Código duplicado no mesmo exercício é recusado
    Dado o qualificador "7.4" chamado "Bloco Setenta" no exercício 2070
    Quando tento criar o qualificador "7.4" chamado "Bloco Repetido" no exercício 2070
    Então a operação é recusada com mensagem contendo "código"

  Cenário: Pai de outro exercício é recusado ao criar
    Dado o qualificador "7.4" chamado "Bloco Setenta" no exercício 2070
    Quando tento criar o qualificador "7.4.1" chamado "Filho Fora" no exercício 2071 sob o "7.4" de 2070
    Então a operação é recusada com mensagem contendo "exercício"

  Cenário: Pai de outro exercício é recusado ao reapontar
    Dado o qualificador "7.4" chamado "Bloco Setenta" no exercício 2070
    E o qualificador "7.4" chamado "Bloco Setenta B" no exercício 2071
    E o qualificador "7.4.1" chamado "Filho Do B" no exercício 2071 sob o "7.4" de 2071
    Quando tento reapontar o "7.4.1" de 2071 para o pai "7.4" de 2070
    Então a operação é recusada com mensagem contendo "exercício"

  Cenário: Lançamento casa o exercício do qualificador quando há plano no ano
    Dado o qualificador "7.4" chamado "Bloco Setenta" no exercício 2070
    E o qualificador "7.4" chamado "Bloco Setenta B" no exercício 2071
    Quando tento gravar um lançamento datado de 2071 no qualificador "7.4" de 2070
    Então a operação é recusada com mensagem contendo "exercício"

  Cenário: Sem plano no exercício do registro, a escrita segue como hoje
    Dado o qualificador "7.4" chamado "Bloco Setenta" no exercício 2070
    Quando gravo um lançamento datado de 2072 no qualificador "7.4" de 2070
    Então o lançamento é gravado com sucesso

  Cenário: Raiz nasce igual ao próprio seq
    Quando crio o qualificador "7.4" chamado "Bloco Setenta" no exercício 2070
    Então a raiz do "7.4" de 2070 é o seu próprio seq

  Cenário: Renumeração com cascata não toca a raiz
    Dado o qualificador "7.4" chamado "Bloco Setenta" no exercício 2070
    E o qualificador "7.4.1" chamado "Filho Renumeravel" no exercício 2070 sob o "7.4" de 2070
    Quando renumero com confirmação o "7.4" de 2070 para "7.5"
    Então as raízes da subárvore "7.5" de 2070 permanecem as originais

  Cenário: Reapontar pai não toca a raiz
    Dado o qualificador "7.4" chamado "Bloco Setenta" no exercício 2070
    E o qualificador "7.6" chamado "Bloco Alternativo" no exercício 2070
    E o qualificador "7.4.1" chamado "Filho Movel" no exercício 2070 sob o "7.4" de 2070
    Quando reaponto com confirmação o "7.4.1" de 2070 para o pai "7.6" com código "7.6.1"
    Então a raiz do "7.6.1" de 2070 é a original do "7.4.1"
