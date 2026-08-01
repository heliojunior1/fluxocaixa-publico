# language: pt
Funcionalidade: A hierarquia de qualificadores não admite ciclo
  Spec `cadastros-nucleo` R16: reapontar para si mesmo ou para um descendente é
  erro de negócio; e toda travessia da árvore termina mesmo se a hierarquia
  já estiver ciclada.

  ⚠️ A sonda da F6.7 mediu o estado real: `nivel` e `path_completo` davam
  `RecursionError` (500), mas `get_root` e `tipo_fluxo` **TRAVAVAM** — laço
  `while`, sem exceção. Como produção roda `gunicorn --workers 1`, uma
  requisição nesse estado derrubava o app inteiro.

  Ramo "7.3" — fora das raízes 1/2, para um ciclo aqui não entrar nas
  varreduras de relatório de outros testes. Contenção, não higiene.

  # ------------------------------------------------------------ guarda

  Cenário: Apontar para si mesmo é recusado
    Dado o qualificador "7.3" chamado "Bloco Ciclo"
    Quando reaponto "7.3" para ele próprio
    Então recebo erro de ciclo
    E o qualificador "7.3" continua sem pai

  Cenário: Apontar para um descendente é recusado
    Dado a cadeia "7.3" → "7.3.1" → "7.3.1.1"
    Quando reaponto "7.3" para o descendente "7.3.1.1"
    Então recebo erro de ciclo
    E o qualificador "7.3" continua sem pai

  Cenário: Apontar para um filho direto é recusado
    Dado a cadeia "7.3" → "7.3.1"
    Quando reaponto "7.3" para o descendente "7.3.1"
    Então recebo erro de ciclo

  Cenário: Reapontamento legítimo entre ramos continua permitido
    Dado o qualificador "7.3" chamado "Bloco Ciclo"
    E o qualificador "7.4" chamado "Bloco Destino"
    Quando reaponto "7.3" para o ramo "7.4" com o código "7.4.1"
    Então a mudança é aceita
    E o qualificador "7.4.1" tem pai "7.4"

  # ------------------------------------------------------------ terminação

  Cenário: Travessia de hierarquia já ciclada não trava
    # Ciclo montado direto no banco — é o caso que a guarda NÃO alcança:
    # dado legado, importação, escrita direta.
    Dado uma hierarquia já ciclada no ramo "7.3"
    Quando consulto o nível do nó ciclado
    Então recebo erro de ciclo sem travar
    Quando consulto o caminho completo do nó ciclado
    Então recebo erro de ciclo sem travar
    Quando consulto a raiz do nó ciclado
    Então recebo erro de ciclo sem travar
    Quando consulto o tipo de fluxo do nó ciclado
    Então recebo erro de ciclo sem travar
    Quando consulto a categoria fiscal do nó ciclado
    Então recebo erro de ciclo sem travar
    Quando consulto os descendentes do nó ciclado
    Então recebo erro de ciclo sem travar

  # ------------------------------------------------------------ cascata (R17)

  Cenário: Subárvore acompanha o novo código
    Dado a cadeia "7.3" → "7.3.1" → "7.3.1.1"
    E o qualificador "7.4" chamado "Bloco Destino"
    Quando reaponto "7.3" para o ramo "7.4" com o código "7.4.1" confirmando
    Então o qualificador "7.4.1.1" existe
    E o qualificador "7.4.1.1.1" existe
    E não existe mais qualificador começando por "7.3"

  Cenário: Sem confirmação, a cascata não acontece
    Dado a cadeia "7.3" → "7.3.1"
    E o qualificador "7.4" chamado "Bloco Destino"
    Quando reaponto "7.3" para o ramo "7.4" com o código "7.4.1"
    Então recebo erro pedindo confirmação da renomeação
    E o qualificador "7.3.1" ainda existe

  Cenário: Colisão na cascata recusa tudo
    Dado a cadeia "7.3" → "7.3.1"
    E o qualificador "7.4" chamado "Bloco Destino"
    E o qualificador "7.4.1.1" chamado "Ocupante" sob "7.4"
    Quando reaponto "7.3" para o ramo "7.4" com o código "7.4.1" confirmando
    Então recebo erro de código duplicado
    E o qualificador "7.3.1" ainda existe

  Cenário: Folha não exige confirmação de cascata
    Dado o qualificador "7.3" chamado "Folha Solta"
    E o qualificador "7.4" chamado "Bloco Destino"
    Quando reaponto "7.3" para o ramo "7.4" com o código "7.4.1"
    Então a mudança é aceita
