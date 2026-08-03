# language: pt
Funcionalidade: Autenticação e proteção de rotas
  Como tesouraria, quero que somente usuários autenticados acessem o sistema,
  com senhas protegidas por hash e troca obrigatória no primeiro acesso.

  Cenário: Login com credenciais válidas
    Dado um usuário ativo "maria" com senha "Segredo-Forte-1"
    Quando envio login "maria" com senha "Segredo-Forte-1"
    Então sou redirecionado para "/"
    E a sessão está estabelecida

  Cenário: Login com senha incorreta
    Dado um usuário ativo "maria" com senha "Segredo-Forte-1"
    Quando envio login "maria" com senha "senha-errada"
    Então permaneço na tela de login com a mensagem "Usuário ou senha inválidos"

  Cenário: Usuário inativo não autentica
    Dado um usuário inativo "antigo" com senha "Segredo-Forte-1"
    Quando envio login "antigo" com senha "Segredo-Forte-1"
    Então permaneço na tela de login com a mensagem "Usuário ou senha inválidos"

  Cenário: Rota protegida sem sessão redireciona ao login
    Quando acesso "/saldos" sem estar autenticado
    Então recebo redirect para "/login?next=/saldos"

  Cenário: Após login sou levado ao destino original
    Dado um usuário ativo "maria" com senha "Segredo-Forte-1"
    Quando envio login "maria" com senha "Segredo-Forte-1" com destino "/saldos"
    Então sou redirecionado para "/saldos"

  # Open redirect: o destino vem do cliente e o phishing pós-login usa o
  # domínio confiável como trampolim. A guarda antiga listava prefixos
  # proibidos e barra invertida não estava na lista — navegadores normalizam
  # "\" para "/" em esquemas especiais, então /\host vira //host vira https://host.
  Cenário: Destino com barra dupla não sai do domínio
    Dado um usuário ativo "maria" com senha "Segredo-Forte-1"
    Quando envio login "maria" com senha "Segredo-Forte-1" com destino "//exemplo-externo.test"
    Então sou redirecionado para "/"

  Cenário: Destino com barra invertida não sai do domínio
    Dado um usuário ativo "maria" com senha "Segredo-Forte-1"
    Quando envio login "maria" com senha "Segredo-Forte-1" com destino "/\exemplo-externo.test"
    Então sou redirecionado para "/"

  Cenário: Destino com esquema absoluto não sai do domínio
    Dado um usuário ativo "maria" com senha "Segredo-Forte-1"
    Quando envio login "maria" com senha "Segredo-Forte-1" com destino "https://exemplo-externo.test/painel"
    Então sou redirecionado para "/"

  Cenário: Documentação OpenAPI exige login
    Quando acesso "/docs" sem estar autenticado
    Então recebo redirect para "/login?next=/docs"

  Cenário: Arquivos estáticos permanecem públicos
    Quando acesso "/static/img/fluxocaixa.png" sem estar autenticado
    Então o recurso é servido com sucesso

  Cenário: Cookie de sessão adulterado é rejeitado
    Quando acesso "/saldos" com um cookie de sessão adulterado
    Então recebo redirect para "/login?next=/saldos"

  Cenário: Logout encerra a sessão
    Dado um usuário ativo "maria" com senha "Segredo-Forte-1"
    E estou autenticado como "maria" com senha "Segredo-Forte-1"
    Quando aciono o logout
    E acesso "/saldos" na mesma sessão
    Então recebo redirect para "/login?next=/saldos"

  Cenário: Primeiro login exige troca de senha
    Dado um usuário "novato" com senha inicial "Provisoria-1" e troca de senha pendente
    E estou autenticado como "novato" com senha "Provisoria-1"
    Quando acesso "/saldos" na mesma sessão
    Então recebo redirect para "/trocar-senha"

  Cenário: Troca de senha libera a navegação
    Dado um usuário "novato" com senha inicial "Provisoria-1" e troca de senha pendente
    E estou autenticado como "novato" com senha "Provisoria-1"
    Quando troco a senha de "Provisoria-1" para "Nova-Senha-Forte-1"
    E acesso "/saldos" na mesma sessão
    Então o recurso é servido com sucesso

  Esquema do Cenário: Nova senha inválida é rejeitada
    Dado um usuário "novato" com senha inicial "Provisoria-1" e troca de senha pendente
    E estou autenticado como "novato" com senha "Provisoria-1"
    Quando troco a senha de "Provisoria-1" para "<nova_senha>"
    Então a troca é rejeitada com a mensagem "<mensagem>"

    Exemplos:
      | nova_senha   | mensagem                                  |
      | curta1       | A nova senha deve ter ao menos 12 caracteres |
      | Provisoria-1 | A nova senha deve ser diferente da atual  |

  Cenário: Reinício não sobrescreve a senha do admin
    Dado o hash de senha atual do admin registrado
    Quando o seed de domínio executa novamente
    Então o hash da senha do admin permanece o mesmo

  Cenário: Senha armazenada como hash bcrypt
    Dado um usuário ativo "maria" com senha "Segredo-Forte-1"
    Então o hash da senha de "maria" começa com "$2"
    E o hash da senha de "maria" é diferente de "Segredo-Forte-1"

  Cenário: recreate-db bloqueado fora de desenvolvimento
    Dado um usuário ativo "maria" com senha "Segredo-Forte-1"
    E estou autenticado como "maria" com senha "Segredo-Forte-1"
    E o ambiente não é de desenvolvimento
    Quando aciono "/recreate-db" por POST na mesma sessão
    Então recebo status 403

  Regra: Modo de demonstração pública (DEMO_MODE)

    O modo demo abre a instância a visitantes. Os três comportamentos abaixo
    são indissociáveis: sem a senha imutável, o primeiro visitante que trocasse
    a senha trancaria o acesso de todos os seguintes.

    Cenário: Sem modo demo a tela de login não expõe credenciais
      Dado que o modo demonstração está desligado
      Quando acesso a tela de login
      Então a tela de login não traz o aviso de demonstração

    Cenário: Em modo demo a tela de login informa as credenciais
      Dado que o modo demonstração está ligado
      Quando acesso a tela de login
      Então a tela de login traz o aviso de demonstração

    # Como o admin nasce em cada modo é verificado em
    # tests/integration/test_seeds.py, que dá boot num banco isolado: aqui o
    # admin é compartilhado pelos cenários e apagá-lo derruba os demais.

    Cenário: Em modo demo a troca de senha é recusada
      Dado um usuário ativo "maria" com senha "Segredo-Forte-1"
      E estou autenticado como "maria" com senha "Segredo-Forte-1"
      E que o modo demonstração está ligado
      Quando troco a senha de "Segredo-Forte-1" para "Nova-Senha-9"
      Então a troca é rejeitada com a mensagem "Ambiente de demonstração"
      E a senha de "maria" continua valendo "Segredo-Forte-1"
