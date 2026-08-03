# language: pt
Funcionalidade: Proteção CSRF em requisições mutantes
  Spec controle-acesso R12 (change protecao-csrf-global)

  A aplicação não tinha nada: nem token, nem verificação de origem. O único
  obstáculo era o `SameSite=lax` do cookie de sessão — que não bloqueia GET
  top-level, não é aplicado consistentemente por navegadores legados e
  webviews, e era a ÚNICA barreira de todos os POSTs destrutivos.

  Contexto:
    Dado que estou autenticado como administrador
    E existe um lançamento fictício de 1234.56

  Cenário: POST sem token é recusado
    Quando envio a exclusão do lançamento sem o token
    Então recebo status 403
    E o lançamento continua ativo

  Cenário: POST com token de outra sessão é recusado
    Quando envio a exclusão do lançamento com o token de outra sessão
    Então recebo status 403
    E o lançamento continua ativo

  Cenário: Token por cabeçalho é aceito
    Quando envio a exclusão do lançamento com o token no cabeçalho
    Então a exclusão é aplicada

  Cenário: Origem divergente é recusada mesmo com token válido
    Quando envio a exclusão do lançamento com token válido e origem externa
    Então recebo status 403
    E o lançamento continua ativo

  Cenário: Sessão autenticada sem token falha fechado
    Quando a sessão perde o token e envio a exclusão do lançamento
    Então recebo status 403
    E o lançamento continua ativo
