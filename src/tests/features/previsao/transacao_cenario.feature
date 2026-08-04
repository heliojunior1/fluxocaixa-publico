# language: pt
Funcionalidade: Transação única na escrita de cenário e recomendações
  Spec previsao R13 (change transacao-unica-cenario-e-backtest)

  Criar/atualizar cenário é tudo-ou-nada: falha na config não deixa cenário
  órfão; falha nos ajustes não perde os anteriores. A regravação das
  recomendações do backtest desfaz a limpeza em caso de falha. Ilha 2069.

  Cenário: Falha na configuração não deixa cenário órfão
    Quando tento criar o cenário "CEN_Q09_ORFAO" com modelo LOA na perna de receita
    Então recebo erro de negócio de cenário
    E nenhum cenário "CEN_Q09_ORFAO" foi persistido

  Cenário: Falha nos ajustes preserva os anteriores
    Dado um cenário MANUAL "CEN_Q09_AJUSTES" com um ajuste gravado
    Quando atualizo o cenário com um ajuste de qualificador inexistente
    Então recebo erro de negócio de cenário
    E o ajuste anterior permanece intacto

  Cenário: Falha no backtest não apaga as recomendações
    Dado uma recomendação de backtest gravada para o qualificador da ilha
    Quando a regravação das recomendações falha no meio
    Então a recomendação anterior permanece após a falha
    E um commit posterior de outra operação não a apaga
