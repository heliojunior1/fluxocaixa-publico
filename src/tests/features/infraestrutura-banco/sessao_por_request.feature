# language: pt
Funcionalidade: Ciclo de vida da sessão SQLAlchemy por requisição
  Spec infraestrutura-banco R13 (change sessao-sqlalchemy-por-request)

  O processo compartilhava UMA Session nunca fechada: o identity map devolvia
  estado carregado por requisições anteriores, e mudança externa no banco não
  aparecia. A sessão agora é removida ao fim de cada request.

  Cenário: Mudança externa aparece na requisição seguinte
    Dado um qualificador de sessão com descrição "DESCRICAO SESSAO ANTES"
    E que a página de qualificadores já foi aberta exibindo essa descrição
    Quando a descrição é alterada diretamente no banco para "DESCRICAO SESSAO DEPOIS"
    E abro a página de qualificadores de novo
    Então a página exibe "DESCRICAO SESSAO DEPOIS"
    E não exibe mais "DESCRICAO SESSAO ANTES"

  Cenário: Middleware de sessão registrado na aplicação
    Quando inspeciono a pilha de middlewares da aplicação
    Então o middleware de sessão-por-request está registrado
