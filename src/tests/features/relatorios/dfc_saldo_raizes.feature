# language: pt
Funcionalidade: Saldo inicial distingue zero de ausência e raízes por tipo
  Spec relatorios R22 (change dfc-saldo-inicial-e-raizes-por-tipo)

  "Saldo zero registrado" e "sem registro" são coisas diferentes: o fallback
  de carry só vale para a ausência. E as raízes do DFC são resolvidas por
  tipo_fluxo — árvore sem raiz resolvível é ERRO explícito, nunca totais
  zerados com cara de relatório. Ilha 2071.

  Cenário: Saldo zero registrado na véspera é respeitado
    Dado uma conta da ilha com saldo registrado de 100.00 em 25/06/2071
    E saldo registrado de 0.00 em 30/06/2071
    Quando calculo o DFC de julho de 2071
    Então o saldo inicial do DFC é 0.00

  Cenário: Ausência de registro devolve nulo, não zero
    Dado uma conta da ilha com saldo registrado de 100.00 em 25/06/2071
    Quando consulto o saldo total de 28/06/2071
    Então o saldo total é nulo

  Cenário: Árvore sem raiz de receita falha explícito
    Dado que a árvore de qualificadores só tem raiz de despesa
    Quando calculo o DFC de junho de 2071
    Então recebo erro de negócio do DFC citando a raiz ausente
