# language: pt
Funcionalidade: Configuração unificada do cenário de previsão
  Spec `previsao` R1–R6: a configuração do cenário passa a viver numa tabela só,
  discriminada pela perna (`'C'` crédito / `'D'` débito) — o mesmo código do
  lançamento desde a F6.1b —, com catálogo de modelos declarando a perna
  aplicável, ajustes unificados e sinal único na projeção.

  # Ilha 2015 (2017 é da rede de previsão; 2019 da rede de lançamento;
  # 2022–2026 do seed; 2031–2038 das demais features).

  # ------------------------------------------------------------------ R1

  Cenário: Cenário com as duas pernas
    Dado um cenário de convergência "CEN_DUAS_PERNAS"
    Quando configuro a perna "C" com o modelo "MANUAL"
    E configuro a perna "D" com o modelo "MANUAL"
    Então o cenário tem 2 configurações
    E existe configuração da perna "C" e da perna "D"

  Cenário: Segunda configuração da mesma perna é rejeitada
    Dado um cenário de convergência "CEN_DUPLICADA"
    E a perna "C" configurada com o modelo "MANUAL"
    Quando configuro a perna "C" com o modelo "FORMULA"
    Então recebo erro de configuração mencionando "já"
    E o cenário tem 1 configurações

  Cenário: Cenário pode ter uma perna só
    Dado um cenário de convergência "CEN_UMA_PERNA"
    E a perna "D" configurada com o modelo "MANUAL"
    Quando executo a simulação do cenário
    Então a simulação devolve resultado
    E a projeção de receita está vazia

  # ------------------------------------------------------------------ R2

  Esquema do Cenário: Catálogo valida a perna aplicável
    Dado um cenário de convergência "CEN_CATALOGO_<modelo>_<perna>"
    Quando configuro a perna "<perna>" com o modelo "<modelo>"
    Então a configuração <resultado>

    Exemplos:
      | modelo         | perna | resultado     |
      | MANUAL         | C     | é criada      |
      | MANUAL         | D     | é criada      |
      | HOLT_WINTERS   | C     | é criada      |
      | HOLT_WINTERS   | D     | é rejeitada   |
      | LOA            | D     | é criada      |
      | LOA            | C     | é rejeitada   |
      | MEDIA_HISTORICA| C     | é rejeitada   |
      | INEXISTENTE    | C     | é rejeitada   |

  Cenário: Modelo fora da perna explica o motivo
    Dado um cenário de convergência "CEN_MOTIVO"
    Quando configuro a perna "C" com o modelo "LOA"
    Então recebo erro de configuração mencionando "perna"

  # ------------------------------------------------------------------ R3

  Cenário: Ajuste por perna
    Dado um cenário de convergência "CEN_AJUSTE"
    E a perna "C" configurada com o modelo "MANUAL"
    E a perna "D" configurada com o modelo "MANUAL"
    Quando registro um ajuste de "10.00" do tipo "P" em cada perna para o mesmo qualificador, ano e mês
    Então cada perna tem 1 ajuste

  Cenário: Ajuste repetido na mesma perna é rejeitado
    Dado um cenário de convergência "CEN_AJUSTE_DUP"
    E a perna "C" configurada com o modelo "MANUAL"
    E um ajuste de "10.00" do tipo "P" registrado na perna "C"
    Quando registro outro ajuste de "20.00" do tipo "V" na perna "C" para a mesma chave
    Então o registro do ajuste é rejeitado

  Cenário: Remover a configuração remove os ajustes
    Dado um cenário de convergência "CEN_CASCADE"
    E a perna "C" configurada com o modelo "MANUAL"
    E um ajuste de "10.00" do tipo "P" registrado na perna "C"
    Quando removo a configuração da perna "C"
    Então não há ajustes órfãos na ilha

  # ------------------------------------------------------------------ R4

  Cenário: Migração converte as pernas preservando modelo e ajustes
    Quando inspeciono os cenários migrados do seed
    Então todo cenário do seed tem configuração unificada
    E nenhuma configuração tem modelo vazio

  # ------------------------------------------------------------------ R5

  Cenário: Valores de projeção usam a perna do lançamento
    Dado um cenário de convergência "CEN_PROJECAO" com versão publicada nas duas pernas
    Quando leio os valores da versão publicada
    Então os tipos gravados são "C" e "D"
    E nenhum valor tem o tipo antigo "R"

  # ------------------------------------------------------------------ R6

  Cenário: Motor de despesa devolve magnitude
    Dado um cenário de convergência "CEN_SINAL" com a perna "D" no modelo "MANUAL" e ajustes
    Quando executo a simulação do cenário
    Então todos os valores projetados de despesa são positivos

  Cenário: Sinal aplicado na leitura da projeção
    Dado um cenário de convergência "CEN_LEITURA" com versão publicada nas duas pernas
    Quando resolvo a projeção para o fluxo de caixa
    Então os valores da perna "D" aparecem negativos
    E os valores da perna "C" aparecem positivos
