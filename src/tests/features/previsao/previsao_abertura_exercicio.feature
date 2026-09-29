# language: pt
Funcionalidade: Previsão de despesa pela porta avulsa e previsão através da abertura de exercício
  Change corrigir-previsao-despesa-e-abertura-exercicio — spec previsao R20/R21
  e cadastros-nucleo R29.

  A série de treino chega aos modelos em MAGNITUDE pela origem única, nas três
  portas (a avulsa projetava despesa ZERO). Abrir um exercício não muda o que
  um cenário projeta: fórmula da biblioteca e setor acompanham a cópia, a
  configuração dos cenários afetados é re-apontada pela raiz e a leitura da
  projeção publicada antes da abertura é traduzida para o plano do ano.
  Ilha: exercícios 2111–2114, receita "1.86", despesa "2.86".

  Cenário: Média histórica de despesa pela rota avulsa
    Dado a rubrica de despesa "2.86" com saída de "1000.00" em todos os meses de 2111 a 2113
    Quando calculo a projeção "MEDIA_HISTORICA" de 2114 pela rota avulsa para "2.86"
    Então os doze meses projetados valem "1000.00"

  Cenário: A série de treino da origem única é magnitude
    Dado a rubrica de despesa "2.86" com saída de "1000.00" em todos os meses de 2111 a 2113
    Quando leio a série de treino do ano-base 2114 com janela de 3 anos para "2.86"
    Então a série tem 36 pontos, todos positivos

  Cenário: Marcação de método acompanha a abertura
    Dado o plano de 2113 com a folha "1.86.1" sob o bloco "1.86" e realizado de "100.00" no ano
    E um cenário "CEN_AB_MARCA" de 2114
    E a marcação "1.86.1" com valor fixo anual "1200.00"
    Quando o exercício 2114 é aberto a partir de 2113
    E executo o cenário
    Então a folha "1.86.1" do plano de 2114 projeta "1200.00" no ano

  Cenário: Ajuste manual acompanha a abertura
    Dado o plano de 2113 com a folha "2.86.1" sob o bloco "2.86" e realizado de "100.00" no ano
    E um cenário "CEN_AB_AJUSTE" de 2114 com despesa manual e ajuste de "500.00" em janeiro para "2.86.1"
    Quando o exercício 2114 é aberto a partir de 2113
    Então o ajuste do cenário aponta para a folha "2.86.1" do plano de 2114

  Cenário: Cenário do próprio ano de origem não é tocado
    Dado o plano de 2113 com a folha "1.86.1" sob o bloco "1.86" e realizado de "100.00" no ano
    E um cenário "CEN_AB_ORIGEM" de 2113
    E a marcação "1.86.1" com valor fixo anual "1200.00"
    Quando o exercício 2114 é aberto a partir de 2113
    Então a marcação do cenário continua na folha "1.86.1" do plano de 2113

  Cenário: Versão publicada antes da abertura aparece no relatório do ano
    Dado o plano de 2113 com a folha "1.86.1" sob o bloco "1.86" e realizado de "100.00" no ano
    E um cenário "CEN_AB_VERSAO" de 2114
    E a marcação "1.86.1" com valor fixo anual "1200.00"
    E o cenário tem uma versão publicada
    Quando o exercício 2114 é aberto a partir de 2113
    E leio a projeção de receita do cenário para 2114 pela porta dos relatórios
    Então a folha "1.86.1" do plano de 2114 soma "1200.00" na leitura
    E a versão publicada continua gravada na folha "1.86.1" do plano de 2113

  Cenário: Fórmula da biblioteca é copiada por valor
    Dado o plano de 2113 com a folha "1.86.1" sob o bloco "1.86" e realizado de "100.00" no ano
    E a fórmula de biblioteca "base * 1.10" para a folha "1.86.1" do plano de 2113
    Quando o exercício 2114 é aberto a partir de 2113
    Então a folha "1.86.1" do plano de 2114 tem a fórmula de biblioteca "base * 1.10"
    E alterar a fórmula de 2114 para "base * 1.20" mantém "base * 1.10" em 2113

  Cenário: Setor de previsão próprio é copiado
    Dado o plano de 2113 com a folha "1.86.1" sob o bloco "1.86" e realizado de "100.00" no ano
    E o bloco "1.86" do plano de 2113 pertence ao setor "BDDAB"
    Quando o exercício 2114 é aberto a partir de 2113
    Então o bloco "1.86" do plano de 2114 pertence ao setor "BDDAB"
