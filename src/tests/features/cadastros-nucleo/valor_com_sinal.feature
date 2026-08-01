# language: pt
Funcionalidade: Origem única do valor com sinal
  Costura `valor_com_sinal` (spec cadastros-nucleo R6–R8): único ponto do
  sistema que sabe como o sinal do lançamento é derivado. Hoje equivale a
  `val_lancamento` (identidade); na F6.1b passa a aplicar o sinal a partir do
  tipo, e só a implementação da costura muda.

  Acompanham a costura a auditoria de coerência sinal × tipo (R7) e a rede de
  caracterização que congela os números dos relatórios (R8).

  # Massa em ilha de datas 2039 (2022–2037 já usadas pelo seed e pelas outras
  # features), com contas e qualificadores próprios.

  # ------------------------------------------------------------------ R6

  Cenário: Agregações passam pela costura
    Quando varro os repositórios e os serviços de relatório em busca de leitura crua
    Então nenhuma referência a "val_lancamento" aparece fora da allow-list

  Cenário: Soma netada pela costura reproduz o total do relatório
    Dado uma receita de "1000.00" e uma despesa de "-300.00" na ilha de caracterização
    Quando somo o valor com sinal do período da ilha
    Então a soma é "700.00"
    E a soma coincide com o total de receita menos despesa do DFC do período

  Cenário: Somas por conta preservam os valores
    Dado uma conta de caracterização com entrada de "500.00" e saída de "-200.00" no mesmo dia
    Quando consulto as somas de entradas e de saídas da conta no dia
    Então a soma de entradas é "500.00"
    E a soma de saídas é "200.00"

  Cenário: Nenhum código numérico de tipo permanece hardcoded
    Dado um cenário de projeção com versão publicada e realizado a apurar na ilha
    Quando atualizo os realizados da versão a partir dos lançamentos
    Então o realizado de receita foi gravado
    E o realizado de despesa foi gravado

  # ------------------------------------------------------------------ R7

  Cenário: Receita com valor negativo é apontada
    Dado um lançamento de receita com valor "-150.00" na ilha de caracterização
    Quando executo a auditoria de coerência
    Então o lançamento consta na auditoria com motivo "RECEITA_NEGATIVA"

  Cenário: Despesa com valor positivo é apontada
    # No modelo 'C'/'D' isso é um débito com valor negativo: -(-250) = +250
    Dado um lançamento de despesa com valor "-250.00" na ilha de caracterização
    Quando executo a auditoria de coerência
    Então o lançamento consta na auditoria com motivo "DESPESA_POSITIVA"

  Cenário: Lançamento coerente não aparece
    Dado apenas lançamentos coerentes na ilha de caracterização
    Quando executo a auditoria de coerência restrita à ilha
    Então a auditoria da ilha não retorna nenhum lançamento

  Cenário: Auditoria não altera dado
    Dado um lançamento de receita com valor "-150.00" na ilha de caracterização
    Quando executo a auditoria de coerência
    Então o valor, o tipo e a situação do lançamento permanecem inalterados

  # ------------------------------------------------------------------ R8

  Cenário: Snapshot cobre os relatórios listados
    Quando coleto o snapshot de caracterização
    Então há snapshot para cada relatório coberto

  Cenário: Execuções repetidas produzem o mesmo snapshot
    Quando coleto o snapshot de caracterização duas vezes
    Então os dois snapshots são idênticos

  Cenário: Divergência de número reprova
    Dado o snapshot de caracterização coletado
    Quando um valor de um relatório coberto muda
    Então a comparação com o snapshot acusa o relatório e o campo divergentes

  Cenário: Massa é coerente e cobre as formas estruturais
    # Linha anômala muda de tipo na migração por construção, e aí todo
    # relatório que separa receita de despesa POR TIPO redistribui entre as
    # colunas — a golden ficaria com asterisco. A semântica das anômalas é
    # fixada pelo BDD tipo_lancamento_cd.feature.
    Quando inspeciono a massa da caracterização
    Então todo lançamento da massa tem valor positivo e tipo "C" ou "D"
    E há lançamento de crédito e lançamento de débito
    E há lançamento sem conta vinculada
    E há lançamento de origem "Automático"
