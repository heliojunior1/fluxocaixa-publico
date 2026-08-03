# language: pt
Funcionalidade: Cabeçalhos de segurança e origem dos assets
  Spec controle-acesso R11 (change headers-seguranca-http)

  A aplicação registrava apenas o SessionMiddleware — nenhum cabeçalho de
  segurança. Faltavam CSP (defesa em profundidade que teria contido o XSS
  mesmo com o escape ausente), proteção contra enquadramento (a aplicação tem
  ações destrutivas de um clique), `nosniff` e `Referrer-Policy`.

  E os quatro assets de terceiro vinham de CDN sem `integrity`, com o Lucide
  em `@latest`: comprometimento de terceiro executaria código em toda sessão
  autenticada de um sistema de tesouraria pública.

  Contexto:
    Dado que estou autenticado como administrador

  Cenário: Resposta HTML traz os cabeçalhos de segurança
    Quando abro uma tela do sistema
    Então a resposta tem o cabeçalho "Content-Security-Policy"
    E a resposta tem o cabeçalho "X-Content-Type-Options" com "nosniff"
    E a resposta tem o cabeçalho "Referrer-Policy"

  Cenário: Enquadramento por outra origem é negado
    Quando abro uma tela do sistema
    Então a política de conteúdo nega enquadramento por outra origem

  Cenário: HSTS apenas em produção
    Dado que o ambiente é de produção
    Quando abro uma tela do sistema
    Então a resposta tem o cabeçalho "Strict-Transport-Security"

  Cenário: HSTS ausente fora de produção
    Dado que o ambiente não é de produção
    Quando abro uma tela do sistema
    Então a resposta não tem o cabeçalho "Strict-Transport-Security"

  Cenário: Nenhum asset vem de origem externa
    Quando inspeciono o template base
    Então nenhum recurso é carregado de origem externa
