# language: pt
Funcionalidade: Relatório de KPIs
  Dashboard gerencial com seis blocos (spec relatorios R1–R8): saldos com
  quebra dinâmica por banco e variação D-1, receita × despesa do período,
  evolução mensal de 12 meses, saldo por conta, composição top-5 + "outras"
  e defasagem da extração com semáforo por destino.

  # Isolamento: os cenários usam ilhas de datas em 2031–2033 (o seed demo
  # grava em 2022–2026) e contas/qualificadores fictícios próprios.

  # ------------------------------------------------------------------ R1

  Cenário: Página acessível com permissão
    Quando acesso a página do relatório de KPIs
    Então a página de KPIs responde com sucesso

  Cenário: Acesso sem permissão é negado
    Dado um usuário autenticado com perfil "EXTRACAO"
    Quando esse usuário acessa a página do relatório de KPIs
    Então o acesso aos KPIs é negado

  Cenário: Período invertido é rejeitado
    Quando solicito os dados de KPIs com início "2031-07-10" e fim "2031-07-01"
    Então recebo erro de negócio nos KPIs mencionando "posterior"

  # ------------------------------------------------------------------ R2

  Cenário: Consolidado e quebra por banco dinâmica
    Dado uma conta KPI "001/0001/11111-1" com saldo de "1000.00" em "2031-07-15"
    E uma conta KPI "104/0001/22222-2" com saldo de "500.00" em "2031-07-15"
    Quando solicito os KPIs com data de referência "2031-07-15"
    Então o saldo consolidado é "1500.00"
    E a quebra por banco lista "001" com "1000.00"
    E a quebra por banco lista "104" com "500.00"

  Cenário: Variação D-1 usa o último dia anterior com saldo
    Dado uma conta KPI "001/0001/33333-3" com saldo de "900.00" em "2031-08-10"
    E a conta KPI "001/0001/33333-3" com saldo de "1000.00" em "2031-08-15"
    Quando solicito os KPIs com data de referência "2031-08-15"
    Então a variação do consolidado vs D-1 é "100.00"
    E a linha da conta "001/0001/33333-3" mostra delta "100.00"

  Cenário: Primeiro dia de saldo não tem variação
    Dado uma conta KPI "001/0001/44444-4" com saldo de "800.00" em "2031-09-15"
    Quando solicito os KPIs com data de referência "2031-09-15"
    Então a variação do consolidado vs D-1 é nula
    E a linha da conta "001/0001/44444-4" mostra delta nulo

  Cenário: Rendimento de fundos do período
    Dado uma conta KPI "001/0001/55555-5" com saldo de "100.00" em "2031-10-14"
    E a conta KPI "001/0001/55555-5" com saldo de "112.34" em "2031-10-15"
    Quando solicito os KPIs com data de referência "2031-10-15" e período de "2031-10-15" a "2031-10-15"
    Então o rendimento do período é "12.34"

  # ------------------------------------------------------------------ R3

  Cenário: Receita, despesa, resultado e percentual do período
    Dado um lançamento de "Entrada" de "2000.00" em "2031-11-10"
    E um lançamento de "Saída" de "-500.00" em "2031-11-12"
    Quando solicito os KPIs do período "2031-11-01" a "2031-11-30"
    Então a receita do período é "2000.00"
    E a despesa do período é "500.00"
    E o resultado do período é "1500.00"
    E o percentual despesa sobre receita é "25.00"

  Cenário: Receita zero não divide
    Dado um lançamento de "Saída" de "-300.00" em "2031-12-10"
    Quando solicito os KPIs do período "2031-12-01" a "2031-12-31"
    Então a despesa do período é "300.00"
    E o percentual despesa sobre receita é nulo

  # ------------------------------------------------------------------ R4

  Cenário: Evolução tem doze pontos e marca só o mês parcial
    Dado um lançamento de "Entrada" de "10.00" em "2031-06-10"
    E um lançamento de "Entrada" de "20.00" em "2031-08-10"
    E um lançamento de "Entrada" de "30.00" em "2032-07-10"
    Quando solicito os KPIs com data de referência "2032-07-15"
    Então a evolução tem 12 pontos de "2031-08" a "2032-07"
    E apenas o ponto "2032-07" está marcado como parcial
    E o ponto da evolução "2031-08" tem receita "20.00"

  Cenário: Mês sem movimento aparece zerado na evolução
    Quando solicito os KPIs com data de referência "2032-07-15"
    Então o ponto da evolução "2032-03" tem receita "0.00"
    E o ponto da evolução "2032-03" tem despesa "0.00"

  # ------------------------------------------------------------------ R5

  Cenário: Saldo por conta com percentual do total
    Dado uma conta KPI "001/0001/66666-6" com saldo de "750.00" em "2033-01-15"
    E uma conta KPI "104/0001/77777-7" com saldo de "250.00" em "2033-01-15"
    Quando solicito os KPIs com data de referência "2033-01-15"
    Então a linha da conta "001/0001/66666-6" mostra percentual "75.00"
    E a linha da conta "104/0001/77777-7" mostra percentual "25.00"

  Cenário: Delta por conta
    Dado uma conta KPI "001/0001/88888-8" com saldo de "250.00" em "2033-02-10"
    E a conta KPI "001/0001/88888-8" com saldo de "300.00" em "2033-02-15"
    Quando solicito os KPIs com data de referência "2033-02-15"
    Então a linha da conta "001/0001/88888-8" mostra delta "50.00"

  # ------------------------------------------------------------------ R6

  Cenário: Top-5 receitas com "outras"
    Dado lançamentos de entrada nos qualificadores "1.92.1,1.92.2,1.92.3,1.92.4,1.92.5,1.92.6,1.92.7" com valores "700,600,500,400,300,200,100" em "2033-03-10"
    Quando solicito os KPIs do período "2033-03-01" a "2033-03-31"
    Então o top de receitas tem 5 itens
    E o primeiro item do top de receitas vale "700.00"
    E as outras receitas somam "300.00"

  Cenário: Menos de cinco qualificadores de despesa
    Dado um lançamento de "Saída" de "-80.00" no qualificador folha "2.90.1" em "2033-04-10"
    E um lançamento de "Saída" de "-20.00" no qualificador folha "2.90.2" em "2033-04-10"
    Quando solicito os KPIs do período "2033-04-01" a "2033-04-30"
    Então o top de despesas tem 2 itens
    E as outras despesas somam "0.00"

  Cenário: Item de composição traz o qualificador pai
    Dado um lançamento de "Entrada" de "50.00" no qualificador folha "1.91.1" em "2033-05-10"
    Quando solicito os KPIs do período "2033-05-01" a "2033-05-31"
    Então o item do top de receitas do qualificador "1.91.1" tem pai "1.91"

  # ------------------------------------------------------------------ R7

  Esquema do Cenário: Limites do semáforo de defasagem
    Dado nenhuma fonte ou execução de extração remanescente
    E uma fonte ativa de destino "SALDO_FUNDO" com execução "SUCESSO" há "<horas>" horas
    Quando solicito os KPIs
    Então o semáforo de defasagem de saldo é "<estado>"

    Exemplos:
      | horas | estado   |
      | 24    | OK       |
      | 25    | AMARELO  |
      | 48    | AMARELO  |
      | 49    | VERMELHO |

  Cenário: SEM_DADOS renova o semáforo
    Dado nenhuma fonte ou execução de extração remanescente
    E uma fonte ativa de destino "LANCAMENTO" com execução "SEM_DADOS" há "2" horas
    Quando solicito os KPIs
    Então o semáforo de defasagem de lançamento é "OK"

  Cenário: ERRO não renova o semáforo
    Dado nenhuma fonte ou execução de extração remanescente
    E uma fonte ativa de destino "SALDO_FUNDO" com execução "SUCESSO" há "30" horas
    E a mesma fonte com execução "ERRO" há "1" horas
    Quando solicito os KPIs
    Então o semáforo de defasagem de saldo é "AMARELO"

  Cenário: Destino sem fonte ativa é neutro
    Dado nenhuma fonte ou execução de extração remanescente
    E uma fonte ativa de destino "SALDO_FUNDO" com execução "SUCESSO" há "2" horas
    Quando solicito os KPIs
    Então o semáforo de defasagem de lançamento é "SEM_FONTE"
    E o semáforo de defasagem de saldo é "OK"

  Cenário: Fonte ativa sem execução elegível é VERMELHO
    Dado nenhuma fonte ou execução de extração remanescente
    E uma fonte ativa de destino "SALDO_FUNDO" sem execuções
    Quando solicito os KPIs
    Então o semáforo de defasagem de saldo é "VERMELHO"

  # ------------------------------------------------------------------ R8

  Cenário: Lançamento automático sem conta entra nos totais
    Dado um lançamento automático sem conta de "100.00" em "2033-06-10"
    Quando solicito os KPIs do período "2033-06-01" a "2033-06-30"
    Então a receita do período é "100.00"
    E o recorte sem conta não está sinalizado

  Cenário: Filtro de banco exclui lançamento sem conta e sinaliza o recorte
    Dado um lançamento automático sem conta de "100.00" em "2033-06-10"
    Quando solicito os KPIs do período "2033-06-01" a "2033-06-30" filtrando pelo banco "001"
    Então a receita do período é "0.00"
    E o recorte sem conta está sinalizado
