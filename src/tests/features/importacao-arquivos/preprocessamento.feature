# language: pt
Funcionalidade: Pré-processamento de importações de arquivo
  Como tesouraria, quero revisar o que será importado (linha a linha) antes de
  gravar — nunca descobrir erros depois que metade do arquivo já entrou.

  Contexto:
    Dado que estou autenticado como administrador
    E uma conta de importação "104/0001/PP-1"

  Cenário: Preview não grava nada
    Quando gero um preview de saldos com o conteúdo:
      | Data;Conta;Valor              |
      | 2025-06-01;104/0001/PP-1;1000 |
    Então o preview tem 1 linha ok e 0 com erro
    E nenhum saldo por fundo foi gravado

  Cenário: Confirmar grava exatamente as linhas válidas
    Quando gero um preview de saldos com o conteúdo:
      | Data;Conta;Valor                 |
      | 2025-06-02;104/0001/PP-1;1000    |
      | 2025-06-02;999/9999/NAO-EX;2000  |
    Então o preview tem 1 linha ok e 1 com erro
    Quando confirmo o preview
    Então o resultado informa 1 inserida
    E existe 1 saldo ativo na conta "104/0001/PP-1" no fundo "GERAL"

  Cenário: Cancelar descarta o staging
    Quando gero um preview de saldos com o conteúdo:
      | Data;Conta;Valor              |
      | 2025-06-03;104/0001/PP-1;1000 |
    E cancelo o preview
    Então confirmar o mesmo preview é rejeitado por expiração
    E nenhum saldo por fundo foi gravado

  Cenário: Token de outra sessão é rejeitado
    Quando gero um preview de saldos com o conteúdo:
      | Data;Conta;Valor              |
      | 2025-06-04;104/0001/PP-1;1000 |
    Então confirmar o preview em outra sessão é rejeitado

  Cenário: Layout novo importa posição por fundo
    Dado um fundo de importação "PPF01"
    Quando gero um preview de saldos com o conteúdo:
      | Data;Banco;Agencia;Conta;CodFundo;Aplicacoes;Resgates;Saldo |
      | 2025-06-05;104;0001;PP-1;PPF01;100,00;50,00;9000,00         |
    Então o preview tem 1 linha ok e 0 com erro
    Quando confirmo o preview
    Então existe 1 saldo ativo na conta "104/0001/PP-1" no fundo "PPF01" com aplicacoes "100.00"

  Cenário: Cabeçalho desconhecido rejeita o arquivo
    Quando gero um preview de saldos com o conteúdo:
      | Foo;Bar;Baz    |
      | 1;2;3          |
    Então o preview do arquivo é rejeitado com layout inválido

  Cenário: Substituição de saldo ativo é sinalizada como aviso
    Dado um saldo ativo de "5000" na conta "104/0001/PP-1" fundo "GERAL" em "2025-06-06"
    Quando gero um preview de saldos com o conteúdo:
      | Data;Conta;Valor              |
      | 2025-06-06;104/0001/PP-1;7000 |
    Então o preview tem 1 linha com aviso de substituição

  Cenário: Fundo inexistente é sinalizado como aviso de auto-cadastro
    Quando gero um preview de saldos com o conteúdo:
      | Data;Banco;Agencia;Conta;CodFundo;Saldo |
      | 2025-06-07;104;0001;PP-1;7877;3000,00   |
    Então o preview tem 1 linha com aviso de auto-cadastro
    Quando confirmo o preview
    Então o fundo "7877" existe pendente de revisão

  Cenário: Lançamento com qualificador inexistente é apontado no preview
    Quando gero um preview de lançamentos com o conteúdo:
      | Data;Qualificador;Tipo;Valor (R$)          |
      | 2025-06-10;QUALIFICADOR QUE NAO EXISTE;Entrada;100 |
    Então o preview de lançamentos tem 0 linha ok e 1 com erro

  Cenário: LOA existente vira aviso de atualização
    Dado uma LOA de "500000" para o ano 2026 e qualificador folha "PP.LOA.1"
    Quando gero um preview de LOA para o ano 2026 com o conteúdo:
      | num_qualificador;valor |
      | PP.LOA.1;900000        |
    Então o preview de LOA tem 1 linha com aviso de atualização
    Quando confirmo o preview
    Então a LOA de 2026 para "PP.LOA.1" vale "900000.00"
