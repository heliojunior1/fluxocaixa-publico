# language: pt
Funcionalidade: Derivação de (ano, período) por periodicidade
  Spec `previsao` R7–R10: origem única do par (ano, período), com as quatro
  periodicidades funcionando de verdade — inclusive QUINZENAL e SEMANAL, que a
  tela oferecia e o backend tratava como MENSAL.

  As datas das viradas ISO abaixo são reais, não ilustrativas: 29/12/2025
  pertence à semana 1 de 2026, e 01/01/2021 à semana 53 de 2020.

  # ------------------------------------------------------------------ R7

  Esquema do Cenário: Data resolve para (ano, período)
    Quando resolvo a data "<data>" com periodicidade "<periodicidade>"
    Então o período resolvido é ano <ano> e período <periodo>

    Exemplos: anual e mensal
      | data       | periodicidade | ano  | periodo |
      | 2026-03-20 | ANUAL         | 2026 | 1       |
      | 2026-03-20 | MENSAL        | 2026 | 3       |
      | 2026-01-01 | MENSAL        | 2026 | 1       |
      | 2026-12-31 | MENSAL        | 2026 | 12      |

    Exemplos: quinzenal — vira no dia 16
      | data       | periodicidade | ano  | periodo |
      | 2026-01-01 | QUINZENAL     | 2026 | 1       |
      | 2026-01-15 | QUINZENAL     | 2026 | 1       |
      | 2026-01-16 | QUINZENAL     | 2026 | 2       |
      | 2026-03-15 | QUINZENAL     | 2026 | 5       |
      | 2026-03-16 | QUINZENAL     | 2026 | 6       |
      | 2026-12-31 | QUINZENAL     | 2026 | 24      |

    Exemplos: semanal — ano ISO, não civil
      | data       | periodicidade | ano  | periodo |
      | 2026-01-05 | SEMANAL       | 2026 | 2       |
      | 2025-12-29 | SEMANAL       | 2026 | 1       |
      | 2025-12-31 | SEMANAL       | 2026 | 1       |
      | 2021-01-01 | SEMANAL       | 2020 | 53      |
      | 2020-12-31 | SEMANAL       | 2020 | 53      |

  Cenário: Periodicidade desconhecida é rejeitada
    Quando resolvo a data "2026-03-20" com periodicidade "DECENAL"
    Então recebo erro de período mencionando "periodicidade"

  # ------------------------------------------------------------------ R8

  Esquema do Cenário: Mês do período
    Quando peço o mês do período <periodo> de <ano> com periodicidade "<periodicidade>"
    Então o mês é <mes>

    Exemplos:
      | periodicidade | ano  | periodo | mes |
      | MENSAL        | 2026 | 7       | 7   |
      | QUINZENAL     | 2026 | 5       | 3   |
      | QUINZENAL     | 2026 | 6       | 3   |
      | QUINZENAL     | 2026 | 7       | 4   |
      | SEMANAL       | 2026 | 1       | 1   |
      | SEMANAL       | 2020 | 53      | 12  |

  Cenário: Mês da semana ISO vem da quinta-feira
    # A semana 1 de 2026 começa em 29/12/2025 e termina em 04/01/2026 —
    # atravessa a virada. A quinta-feira é 01/01/2026, então o mês é janeiro.
    Quando peço o mês do período 1 de 2026 com periodicidade "SEMANAL"
    Então o mês é 1

  Esquema do Cenário: Faixa válida do período
    Quando valido o período <periodo> com periodicidade "<periodicidade>"
    Então a validação <resultado>

    Exemplos:
      | periodicidade | periodo | resultado   |
      | ANUAL         | 1       | passa       |
      | ANUAL         | 2       | é rejeitada |
      | MENSAL        | 12      | passa       |
      | MENSAL        | 13      | é rejeitada |
      | QUINZENAL     | 24      | passa       |
      | QUINZENAL     | 25      | é rejeitada |
      | SEMANAL       | 53      | passa       |
      | SEMANAL       | 54      | é rejeitada |
      | MENSAL        | 0       | é rejeitada |

  # ------------------------------------------------------------------ R9

  Cenário: Cenário semanal projeta semanas
    Dado um cenário de período "CEN_SEMANAL" com periodicidade "SEMANAL" e 8 períodos
    Quando executo a simulação de período
    Então a projeção tem 8 pontos
    E os pontos estão espaçados de 7 dias

  Cenário: Cenário quinzenal projeta quinzenas
    Dado um cenário de período "CEN_QUINZENAL" com periodicidade "QUINZENAL" e 4 períodos
    Quando executo a simulação de período
    Então a projeção tem 4 pontos
    E os pontos caem dois em cada mês

  Cenário: Cenário mensal continua mensal
    Dado um cenário de período "CEN_MENSAL" com periodicidade "MENSAL" e 12 períodos
    Quando executo a simulação de período
    Então a projeção tem 12 pontos
    E os pontos estão espaçados de um mês

  # ------------------------------------------------------------------ R10

  Cenário: Projeção grava o período
    Dado um cenário de período "CEN_GRAVA" com periodicidade "QUINZENAL" e 4 períodos
    Quando salvo a projeção como versão
    Então os valores gravados têm período entre 1 e 24

  Cenário: Realizado casa pelo período da data do lançamento
    Dado um cenário de período "CEN_REALIZADO" com periodicidade "QUINZENAL" e 4 períodos
    E um lançamento realizado em "2015-01-20" no qualificador do cenário
    Quando apuro os realizados da versão
    Então o realizado foi somado na quinzena 2
