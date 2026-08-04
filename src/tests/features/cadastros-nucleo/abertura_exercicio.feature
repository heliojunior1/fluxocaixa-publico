# language: pt
Funcionalidade: Abertura de exercício por cópia explícita
  Spec `cadastros-nucleo` R29 (change abertura-exercicio, F10.3): o exercício
  novo nasce como CÓPIA por valor do plano do anterior — só ativos, pai
  remapeado, marcação própria de categoria fiscal e raiz propagadas —, por
  ato explícito, confirmado e atômico. Segunda abertura é recusada; valores
  (LOA) nunca acompanham a estrutura.

  Ramo "7.9", ilhas 2084/2085.

  Contexto:
    Dado o plano de origem no exercício 2084 com bloco "7.9" marcado "SAUDE", folha "7.9.1" e a folha inativa "7.9.2"

  Cenário: Cópia preserva hierarquia, categoria própria e raiz
    Quando abro com confirmação o exercício 2085 a partir de 2084
    Então o plano de 2085 tem "7.9" e "7.9.1" com pai remapeado
    E a marcação própria "SAUDE" do "7.9" de 2085 é preservada
    E as raízes do plano de 2085 são as mesmas do plano de 2084

  Cenário: Inativa não é copiada e o histórico fica intacto
    Quando abro com confirmação o exercício 2085 a partir de 2084
    Então o plano de 2085 não contém "7.9.2"
    E a folha inativa "7.9.2" de 2084 permanece inativa

  Cenário: Segunda abertura para o mesmo ano é recusada
    Quando abro com confirmação o exercício 2085 a partir de 2084
    E tento abrir o exercício 2085 a partir de 2084
    Então a abertura é recusada com mensagem contendo "já possui"

  Cenário: Sem confirmação, nada acontece
    Quando tento abrir sem confirmação o exercício 2085 a partir de 2084
    Então a abertura é recusada com mensagem contendo "confirme"
    E o exercício 2085 não tem plano

  Cenário: Valores não acompanham a estrutura
    Dado uma LOA de 1234.56 para a folha "7.9.1" de 2084
    Quando abro com confirmação o exercício 2085 a partir de 2084
    Então não existe LOA para o exercício 2085
