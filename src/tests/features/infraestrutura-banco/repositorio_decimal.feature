# language: pt
Funcionalidade: Decimal na borda do repositório, soft-delete e auditoria
  Spec infraestrutura-banco R14 (change decimal-e-soft-delete-nos-repositorios)

  Dinheiro sai do repositório como Decimal (float é decisão do consumidor);
  comparativo vivo filtra soft-delete; editar/inativar carimba auditoria;
  repositório não conhece o usuário logado nem HTTP. Ilha 2072.

  Contexto:
    Dado um qualificador folha do repositório "1.72.1"

  Cenário: Agregação monetária sai como Decimal
    Dado um lançamento ativo de 1234.56 em 2072
    Quando consulto o total de créditos de 2072 no repositório
    Então o total é Decimal de valor 1234.56

  Cenário: Pagamento excluído fora do comparativo
    Dado um pagamento ativo de 100.00 e um excluído de 900.00 em junho de 2072
    Quando consulto o comparativo de pagamentos por qualificador de 2072
    Então o comparativo soma 100.00

  Cenário: Editar lançamento carimba auditoria
    Dado um lançamento manual de 50.00 em 2072
    Quando edito o valor do lançamento para 75.00
    Então o lançamento tem data e autor de alteração preenchidos

  Cenário: Repositório sem acoplamento a autenticação
    Quando inspeciono os imports dos repositórios
    Então nenhum repositório importa da camada de autenticação
