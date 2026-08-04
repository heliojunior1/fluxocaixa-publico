# language: pt
Funcionalidade: Ajuste mensal rateado pelos períodos do mês
  Spec previsao R15 (change ajuste-cenario-por-periodicidade)

  O ajuste é preenchido por MÊS; em quinzenal/semanal o mês tem 2/4-5
  períodos, e o valor cheio era emitido em CADA período — R$ 120 mil/mês
  viravam R$ 240 mil. A soma dos períodos do mês tem de igualar o valor
  mensal. Ilha 2069 (ano-ref 2068).

  Cenário: Ajuste de valor em cenário quinzenal reparte pelo mês
    Dado um ajuste de valor de 120000.00 no mês 1 para o qualificador de ajuste
    Quando executo o cenário manual quinzenal de 2069 com 4 períodos
    Então a soma dos períodos do mês 1 é 120000.00

  Cenário: Ajuste percentual em cenário quinzenal reparte pelo mês
    Dado realizado de 1000.00 em janeiro de 2068 no qualificador de ajuste
    E um ajuste percentual de 10 no mês 1 para o qualificador de ajuste
    Quando executo o cenário manual quinzenal de 2069 com 4 períodos
    Então a soma dos períodos do mês 1 é 1100.00

  Cenário: Cenário mensal permanece idêntico
    Dado um ajuste de valor de 500.00 no mês 1 para o qualificador de ajuste
    Quando executo o cenário manual mensal de 2069 com 12 períodos
    Então a soma dos períodos do mês 1 é 500.00
