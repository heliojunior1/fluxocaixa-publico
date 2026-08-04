# language: pt
Funcionalidade: Unicidade da LOA e regra na camada de serviço
  Spec cadastros-nucleo R24 (change loa-unicidade-e-servico-proprio)

  No máximo UMA linha ativa de LOA por (ano, qualificador), garantida no
  BANCO (índice único parcial) — duplicata dobraria teto do autorizado,
  metas fiscais e previsto do desembolso. A regra vive em loa_service;
  serviço nunca importa da web. Ilha 2065.

  Contexto:
    Dado um qualificador folha da LOA

  Cenário: Gravar duas vezes atualiza em vez de duplicar
    Quando gravo a LOA de 1000.00 para o ano 2065
    E gravo a LOA de 2000.00 para o ano 2065
    Então existe um único registro ativo de 2065 com valor 2000.00

  Cenário: Duplo submit na tela não duplica
    Quando submeto o formulário da LOA com 1500.00 para o ano 2065 duas vezes
    Então existe um único registro ativo de 2065 com valor 1500.00

  Cenário: Escrita direta duplicada é recusada pelo banco
    Dado um registro ativo de LOA de 1000.00 para o ano 2065
    Quando insiro por fora do serviço uma segunda linha ativa para a mesma chave
    Então o banco recusa com violação de unicidade

  Cenário: Serviço não importa da web
    Quando inspeciono os imports dos módulos de serviço
    Então nenhum módulo de serviço importa da camada web
