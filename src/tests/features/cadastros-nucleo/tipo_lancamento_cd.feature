# language: pt
Funcionalidade: Tipo de lançamento 'C'/'D' com valor sempre positivo
  Convergência do tipo de lançamento (spec cadastros-nucleo R9–R11 e R2):
  `cod_tipo_lancamento` passa a ser 'C' (crédito/receita) ou 'D'
  (débito/despesa), `val_lancamento` é sempre positivo e o sinal do fluxo de
  caixa vem do tipo, pela costura `valor_com_sinal`.

  As descrições "Entrada"/"Saída" continuam existindo — convergiu o código, não
  o vocabulário da tesouraria.

  # Ilha de datas 2038 (2019 é da rede de caracterização; 2022–2037 do seed e
  # das demais features).

  # ------------------------------------------------------------------ R9

  Cenário: Domínio semeado com os códigos novos
    Quando consulto os tipos de lançamento cadastrados
    Então existe o tipo "C" com descrição "Entrada"
    E existe o tipo "D" com descrição "Saída"
    E resolver o tipo pela descrição "Entrada" devolve o código "C"
    E resolver o tipo pela descrição "Saída" devolve o código "D"

  Esquema do Cenário: Valor com sinal é preservado para cada forma de lançamento
    Dado um lançamento gravado com tipo "<tipo>" e valor "<valor>" na ilha de convergência
    Então o lançamento tem valor absoluto "<absoluto>"
    E o valor com sinal do lançamento é "<com_sinal>"

    Exemplos:
      | tipo | valor   | absoluto | com_sinal |
      | C    | 1000.00 | 1000.00  | 1000.00   |
      | D    | 300.00  | 300.00   | -300.00   |
      | D    | 150.00  | 150.00   | -150.00   |
      | C    | 250.00  | 250.00   | 250.00    |

  Cenário: Soma netada continua correta com valores positivos
    Dado um lançamento gravado com tipo "C" e valor "1000.00" na ilha de convergência
    E um lançamento gravado com tipo "D" e valor "300.00" na ilha de convergência
    Quando somo o valor com sinal da ilha de convergência
    Então a soma é "700.00"

  # ------------------------------------------------------------------ R2

  Cenário: Valor negativo é rejeitado
    Quando crio um lançamento de convergência com valor "-100.00"
    Então recebo erro de negócio de convergência mencionando "positivo"
    E nenhum lançamento é criado na ilha de convergência

  Cenário: Valor zero é rejeitado
    Quando crio um lançamento de convergência com valor "0.00"
    Então recebo erro de negócio de convergência
    E nenhum lançamento é criado na ilha de convergência

  Cenário: Valor positivo é aceito
    Quando crio um lançamento de convergência com valor "123.45"
    Então o lançamento é criado na ilha de convergência

  # ------------------------------------------------------------------ R10

  Cenário: Linha de despesa gera débito
    Dado um mapeamento de convergência do tipo despesa com uma linha de staging de "-500.00"
    Quando o processamento de convergência roda
    Então o lançamento gerado tem tipo "D" e valor "500.00"

  Cenário: Estorno em mapeamento de receita gera débito no qualificador de receita
    Dado um mapeamento de convergência do tipo receita com uma linha de staging de "-100.00"
    Quando o processamento de convergência roda
    Então o lançamento gerado tem tipo "D" e valor "100.00"
    E o lançamento gerado está no qualificador do mapeamento

  Cenário: Inversão de sinal é aplicada antes da derivação
    Dado um mapeamento de convergência do tipo despesa com inversão de sinal e uma linha de staging de "500.00"
    Quando o processamento de convergência roda
    Então o lançamento gerado tem tipo "D" e valor "500.00"

  # ------------------------------------------------------------------ R11

  Cenário: Importação aceita descrição e código
    Quando importo lançamentos de convergência com tipos "Saída" e "D"
    Então as duas linhas são aceitas como débito

  Cenário: Importação recusa o código numérico antigo
    Quando importo um lançamento de convergência com tipo "2"
    Então a importação de convergência reporta erro na linha

  Cenário: Importação recusa valor negativo
    Quando importo um lançamento de convergência com valor "-100.00"
    Então a importação de convergência reporta erro na linha

  Cenário: Modelo de planilha só tem valores positivos
    Quando baixo o modelo de importação de lançamentos
    Então todas as linhas de exemplo têm valor positivo
