# language: pt
Funcionalidade: Despacho de modelos no serviço e visualização sem execução
  Spec previsao R14 (change despacho-de-modelos-no-servico)

  O despacho modelo→janela/mínimo/motor vive no serviço (calcular_projecao),
  não em 160 linhas de rota; abrir a página de um cenário com versão
  publicada NÃO treina modelos. Ilha 2069.

  Cenário: Serviço calcula projeção determinística
    Dado um qualificador de despacho com 24 meses de histórico
    Quando chamo calcular_projecao com "MEDIA_HISTORICA" e 12 períodos
    Então recebo uma projeção com 12 períodos

  Cenário: Dados insuficientes é erro de negócio citando o mínimo
    Dado um qualificador de despacho sem histórico
    Quando chamo calcular_projecao com "HOLT_WINTERS" e 12 períodos
    Então recebo erro de negócio de despacho citando "mínimo"

  Cenário: Modelo não suportado é erro de negócio
    Quando chamo calcular_projecao com "MODELO_QUE_NAO_EXISTE" e 12 períodos
    Então recebo erro de negócio de despacho citando "não suportado"

  Cenário: Visualizar cenário com versão publicada não executa modelos
    Dado um cenário MANUAL de despacho com versão publicada
    E que executar a simulação passará a falhar
    Quando abro a página do cenário
    Então a página responde com sucesso
    E exibe a origem "versão publicada"
