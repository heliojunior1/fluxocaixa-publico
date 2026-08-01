# language: pt
Funcionalidade: Movimento próprio de nó-pai no DFC
  Spec `relatorios` R20: um qualificador que tem filhos ativos E movimento
  próprio — lançamentos seus, ou projeção endereçada a ele — passa a mostrar
  essa parcela como LINHA FILHA, e o total do nó é a soma dos filhos.

  Enquanto o movimento fica só em folha, nada muda: árvore bem formada não
  ganha linha alguma. A F6.4 é que passou a permitir o outro estado por
  caminho suportado.

  ⚠️ Os cenários do caminho PROJETADO usam o **ano corrente com mês anterior**,
  não uma ilha no passado: `_recompor_pais` só roda quando há mês ABERTO
  (`if meses_abertos:`), então num ano todo fechado o vazamento não se
  manifesta e o teste passaria por vacuidade. Mesmo motivo pelo qual a F5.2 usa
  o ano corrente — e pelo qual `dfc_projetado` fica fora da golden.

  Ramo "2.6" sob a raiz de despesa.

  Cenário: Realizado próprio de nó-pai não some na estratégia Projetado
    # Vazamento 1: `_recompor_pais` SUBSTITUI o pai pela soma dos filhos, em
    # TODAS as colunas — inclusive as dos meses já fechados.
    Dado o qualificador "2.6" com o filho "2.6.1"
    E lançamentos próprios de "800.00" em "2.6" no mês anterior ao corrente
    E lançamentos de "300.00" em "2.6.1" no mês anterior ao corrente
    E um cenário publicado para o ano corrente
    Quando consulto o DFC do ano corrente na estratégia "realizado"
    E consulto o DFC do ano corrente na estratégia "projetado"
    Então o nó "2.6" exibe o mesmo valor no mês anterior nas duas estratégias

  Cenário: A parcela própria aparece como linha e o pai é a soma dos filhos
    Dado o qualificador "2.6" com o filho "2.6.1"
    E lançamentos próprios de "800.00" em "2.6" no mês anterior ao corrente
    E lançamentos de "300.00" em "2.6.1" no mês anterior ao corrente
    Quando consulto o DFC do ano corrente na estratégia "realizado"
    Então o nó "2.6" tem uma linha de movimento próprio
    E o total do nó "2.6" é a soma dos seus filhos

  Cenário: Projeção endereçada a nó que virou pai não some
    # Vazamento 2: a projeção existe no mapa e `_projetar_folhas` nunca a lê,
    # porque o nó deixou de ser folha DEPOIS que a versão foi publicada.
    Dado o qualificador folha "2.6" sem filhos
    E um cenário publicado projetando "500.00" para "2.6" no mês corrente
    E que "2.6" ganha o filho "2.6.1" depois da publicação
    Quando consulto o DFC do ano corrente na estratégia "projetado"
    Então o nó "2.6" exibe "500.00" na coluna do mês corrente

  Cenário: Árvore bem formada não ganha linha alguma
    Dado o qualificador "2.6" com o filho "2.6.1"
    E lançamentos de "300.00" em "2.6.1" no mês anterior ao corrente
    Quando consulto o DFC do ano corrente na estratégia "realizado"
    Então o nó "2.6" não tem linha de movimento próprio

  Cenário: Folha não recebe a linha
    Dado o qualificador folha "2.6" sem filhos
    E lançamentos próprios de "800.00" em "2.6" no mês anterior ao corrente
    Quando consulto o DFC do ano corrente na estratégia "realizado"
    Então o nó "2.6" não tem linha de movimento próprio

  Cenário: Detalhamento da linha traz só o movimento próprio
    Dado o qualificador "2.6" com o filho "2.6.1"
    E lançamentos próprios de "800.00" em "2.6" no mês anterior ao corrente
    E lançamentos de "300.00" em "2.6.1" no mês anterior ao corrente
    Quando abro o detalhamento da linha de movimento próprio de "2.6"
    Então vejo apenas lançamentos que somam "800.00"
