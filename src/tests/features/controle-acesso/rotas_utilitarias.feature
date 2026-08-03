# language: pt
Funcionalidade: Rotas utilitárias de banco blindadas
  Spec controle-acesso R6 + infraestrutura-banco R8
  (change blindar-rotas-administrativas-banco)

  `/init-db` e `/recreate-db` acionam `seed_data()`, que remove FISICAMENTE
  lançamentos, qualificadores, pagamentos e órgãos. Expostas em GET, eram
  acionáveis por navegação de terceiro: `SameSite=lax` envia o cookie de sessão
  em GET top-level, e a aplicação não tem CSRF.

  A spec anterior exigia `APP_ENV=dev` só de `/recreate-db` — mas as duas
  chamam o mesmo seed destrutivo, então a assimetria deixava desprotegida
  justamente a rota que ninguém achava perigosa.

  Contexto:
    Dado um usuário ativo "admin.banco" com senha "Segredo-Forte-1"
    E que "admin.banco" tem a permissão de administrar o banco
    E estou autenticado como "admin.banco" com senha "Segredo-Forte-1"
    E existe um lançamento fictício de 1234.56

  Cenário: init-db não responde mais a GET
    Dado que o ambiente é de desenvolvimento
    Quando acesso "/init-db" por GET
    Então recebo status 405
    E o lançamento fictício continua no banco

  Cenário: recreate-db não responde mais a GET
    Dado que o ambiente é de desenvolvimento
    Quando acesso "/recreate-db" por GET
    Então recebo status 405
    E o lançamento fictício continua no banco

  Cenário: init-db bloqueado fora de desenvolvimento
    Dado que o ambiente não é de desenvolvimento
    Quando aciono "/init-db" por POST confirmado
    Então recebo status 403
    E o lançamento fictício continua no banco

  Cenário: init-db exige confirmação explícita
    Dado que o ambiente é de desenvolvimento
    Quando aciono "/init-db" por POST sem confirmação
    Então a operação é recusada
    E o lançamento fictício continua no banco

  # O erro de negócio da recusa acima vira flash + redirect. O destino do
  # redirect caía no `Referer`, que é cabeçalho do cliente e forjável — mesma
  # família do open redirect em `next` (change corrigir-open-redirect-destino).
  Cenário: Erro de negócio não redireciona para Referer externo
    Dado que o ambiente é de desenvolvimento
    Quando aciono "/init-db" por POST sem confirmação vindo de "https://exemplo-externo.test/isca"
    Então o redirecionamento aponta para a própria aplicação

  Cenário: Falha de inicialização não vaza detalhe interno
    Dado que o ambiente é de desenvolvimento
    E que a inicialização do banco vai falhar com "coluna flc_segredo.txt_hash inexistente"
    Quando aciono "/init-db" por POST confirmado
    Então a resposta não contém "flc_segredo"
