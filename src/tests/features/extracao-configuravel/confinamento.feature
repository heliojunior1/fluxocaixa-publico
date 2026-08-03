# language: pt
Funcionalidade: Confinamento de destino dos conectores
  Spec extracao-configuravel R23 (change confinar-conectores-extracao)

  O cadastro de fonte é parametrizável pelo usuário — é o princípio de produto.
  O que faltava era delimitar o que o parâmetro pode ALCANÇAR.

  O `diretorio` recusava apenas `..`, então caminho absoluto passava:
  `diretorio=/etc` + `padrao_nome=passwd` lia arquivo do servidor e devolvia o
  conteúdo no detalhe da execução — inclusive `/proc/self/environ`, que guarda
  as credenciais `${VAR}` dos próprios conectores.

  Os destinos de rede aceitavam qualquer host, incluindo o endereço de
  metadados de nuvem, com origem dentro da rede do provedor.

  Contexto:
    Dado que estou autenticado como administrador
    E um sistema de origem "SIS_C" cadastrado
    E uma raiz de extração configurada

  Cenário: Diretório dentro da raiz é aceito
    Quando cadastro a fonte local "Fonte Confinada OK" com diretório dentro da raiz
    Então a fonte "Fonte Confinada OK" existe

  Cenário: Diretório absoluto fora da raiz é recusado
    Quando cadastro a fonte local "Fonte Fora" com o diretório "/etc"
    Então o cadastro é recusado citando a raiz de extração
    E a fonte "Fonte Fora" não existe

  Cenário: Symlink apontando para fora da raiz é recusado
    Dado um link simbólico dentro da raiz apontando para fora dela
    Quando cadastro a fonte local "Fonte Symlink" com o diretório do link
    Então o cadastro é recusado citando a raiz de extração
    E a fonte "Fonte Symlink" não existe

  Cenário: Host de metadados de nuvem é recusado
    Quando cadastro a fonte de API "Fonte Metadados" apontando para "http://169.254.169.254/latest/"
    Então o cadastro é recusado citando destino interno
    E a fonte "Fonte Metadados" não existe

  Cenário: Host de loopback é recusado
    Quando cadastro a fonte de API "Fonte Loopback" apontando para "http://127.0.0.1:8000/api"
    Então o cadastro é recusado citando destino interno
    E a fonte "Fonte Loopback" não existe

  Cenário: Host interno explicitamente permitido é aceito
    Dado que o host "10.0.0.5" está declarado como permitido
    Quando cadastro a fonte de API "Fonte Interna OK" apontando para "http://10.0.0.5/api"
    Então a fonte "Fonte Interna OK" existe

  Cenário: Banco SQLite fora da raiz é recusado
    Quando cadastro a fonte SQL "Fonte SQLite Fora" apontando para um arquivo fora da raiz
    Então o cadastro é recusado citando a raiz de extração
    E a fonte "Fonte SQLite Fora" não existe
