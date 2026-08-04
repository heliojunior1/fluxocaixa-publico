# language: pt
Funcionalidade: Entrada inválida nunca vira erro de servidor
  Spec infraestrutura-banco R15 (change validacao-de-entrada-na-web)

  Parâmetro/campo inválido é erro de NEGÓCIO (flash/400 com o nome do
  campo), nunca 500 — `?page=abc` não é defeito do servidor. Erro interno
  de endpoint JSON sai genérico: str(e) de exceção arbitrária vaza caminho,
  SQL e schema.

  Cenário: Paginação inválida não é erro de servidor
    Quando requisito a tela de lançamentos com page "abc"
    Então a resposta não é erro de servidor

  Cenário: Data inválida no filtro não é erro de servidor
    Quando requisito a conferência com fim "banana"
    Então a resposta não é erro de servidor

  Cenário: Parâmetro obrigatório ausente no drill-down não é 500
    Quando requisito os eventos do DFC sem o parâmetro seq
    Então a resposta não é erro de servidor

  Cenário: Erro interno de endpoint JSON não vaza detalhes
    Dado que a execução do backtest falhará com "segredo-interno-xyz"
    Quando executo o backtest pela API
    Então a resposta é 500 com mensagem genérica
    E "segredo-interno-xyz" não aparece no corpo
