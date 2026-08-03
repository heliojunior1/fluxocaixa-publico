# language: pt
Funcionalidade: Configuração insegura impede o boot
  Spec infraestrutura-banco R10 + controle-acesso R3
  (change hardening-configuracao-producao)

  O padrão dos achados era o mesmo: os defaults falhavam no sentido INSEGURO, e
  a configuração segura dependia de alguém lembrar de setar uma variável.
  Cookie sem `Secure` por default, `SECRET_KEY` ausente apenas advertida, e um
  `.env.example` que se anunciava "para produção" omitindo toda a segurança.

  Cenário: Demonstração sobre dados reais não sobe
    Dado o ambiente com "DEMO_MODE" igual a "true"
    E o ambiente com "SEED_DEMO_DATA" igual a "false"
    Quando valido a configuração
    Então o boot é recusado citando "SEED_DEMO_DATA"

  Cenário: Demonstração em produção não sobe
    Dado o ambiente com "DEMO_MODE" igual a "true"
    E o ambiente com "APP_ENV" igual a "prod"
    Quando valido a configuração
    Então o boot é recusado citando "DEMO_MODE"

  Cenário: Produção sem chave de sessão não sobe
    Dado o ambiente com "APP_ENV" igual a "prod"
    Quando valido a configuração
    Então o boot é recusado citando "SECRET_KEY"

  Cenário: Chave de exemplo não é aceita em produção
    Dado o ambiente com "APP_ENV" igual a "prod"
    E o ambiente com "SECRET_KEY" igual a "your-secret-key-here"
    Quando valido a configuração
    Então o boot é recusado citando "SECRET_KEY"

  Cenário: Configuração de demonstração legítima sobe
    Dado o ambiente com "DEMO_MODE" igual a "true"
    E o ambiente com "SEED_DEMO_DATA" igual a "true"
    Quando valido a configuração
    Então o boot é permitido

  Cenário: Cookie de sessão é seguro por default
    Quando inspeciono o cookie de sessão em ambiente não declarado
    Então o cookie exige conexão segura

  Cenário: Desenvolvimento dispensa a conexão segura
    Quando inspeciono o cookie de sessão em ambiente de desenvolvimento
    Então o cookie não exige conexão segura
