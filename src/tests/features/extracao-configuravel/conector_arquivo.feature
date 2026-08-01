# language: pt
Funcionalidade: Conector de arquivo e motor de parser dirigido por layout
  Spec extracao-configuravel R2/R3 (delta) e R14–R16 (change conector-ftp-arquivo)

  Contexto:
    Dado que estou autenticado como administrador
    E um sistema de origem "SIS_X" cadastrado
    E o conector "FTP_ARQUIVO" registrado

  # --- R14: motor de parser ---

  Cenário: Layout oficial de referência parseia corretamente
    Dado o arquivo de exemplo "extrato_ok.csv" com o layout de extrato
    Quando parseio o arquivo pelo layout
    Então obtenho 2 linhas e 0 erros de linha
    E a primeira linha tem saldo "1234.56" e fundo "9999"

  Cenário: Header divergente rejeita o arquivo inteiro
    Dado o arquivo de exemplo "extrato_header_ruim.csv" com o layout de extrato
    Quando parseio o arquivo pelo layout
    Então o parse rejeita o arquivo inteiro

  Cenário: Linha malformada é erro pontual
    Dado o arquivo de exemplo "extrato_linha_ruim.csv" com o layout de extrato
    Quando parseio o arquivo pelo layout
    Então obtenho 1 linhas e 1 erros de linha
    E algum erro de linha aponta a linha 3

  Cenário: BOM é consumido de forma transparente
    Dado o arquivo de exemplo "extrato_ok.csv" com o layout de extrato
    Quando parseio o arquivo pelo layout
    Então o primeiro campo de dados não contém caractere de BOM

  # --- R16: transformações declarativas ---

  Cenário: Normalização de número de conta
    Dado o arquivo de exemplo "extrato_ok.csv" com o layout de extrato
    Quando parseio o arquivo pelo layout
    Então a primeira linha tem número de conta "123456"

  Cenário: Extração de código do fundo antes do hífen
    Dado o arquivo de exemplo "extrato_ok.csv" com o layout de extrato
    Quando parseio o arquivo pelo layout
    Então a primeira linha tem fundo "9999" e descrição "FUNDO ALFA"

  Cenário: Descrição sem código numérico vira erro de linha
    Dado o arquivo de exemplo "extrato_sem_hifen.csv" com o layout de extrato
    Quando parseio o arquivo pelo layout
    Então obtenho 0 linhas e 1 erros de linha

  Cenário: Transformação desconhecida é rejeitada no cadastro
    Quando cadastro uma fonte de arquivo com transformação de layout "inexistente"
    Então o cadastro de arquivo é rejeitado

  Cenário: Padrão de nome com traversal é rejeitado
    Quando cadastro uma fonte de arquivo com padrão de nome "../{:%Y%m%d}.csv"
    Então o cadastro de arquivo é rejeitado

  # --- R3 + R15: execução integrada via PASTA_LOCAL ---

  Cenário: Pasta local com arquivo do dia extrai as linhas
    Dado uma conta de arquivo "104/0001/123456"
    E uma conta de arquivo "104/0001/987654"
    E uma fonte de arquivo "Saldos Caixa" com o arquivo "extrato_ok.csv" para o dia "2026-07-10"
    Quando executo a fonte de arquivo "Saldos Caixa" para o dia "2026-07-10"
    Então a execução de arquivo registra status "SUCESSO" com 2 inseridas e 0 com erro

  Cenário: Erro de parse do conector conta como erro de linha
    Dado uma conta de arquivo "104/0001/123456"
    E uma fonte de arquivo "Saldos Parciais" com o arquivo "extrato_linha_ruim.csv" para o dia "2026-07-10"
    Quando executo a fonte de arquivo "Saldos Parciais" para o dia "2026-07-10"
    Então a execução de arquivo registra status "PARCIAL" com 1 inseridas e 1 com erro

  Cenário: Arquivo ausente no dia é pulado sem falha
    Dado uma fonte de arquivo "Saldos Vazios" sem arquivo para o dia "2026-07-11"
    Quando executo a fonte de arquivo "Saldos Vazios" para o dia "2026-07-11"
    Então a execução de arquivo registra status "SEM_DADOS" com 0 inseridas e 0 com erro

  Cenário: Backfill multi-dia com dias ausentes
    Dado uma conta de arquivo "104/0001/123456"
    E uma conta de arquivo "104/0001/987654"
    E uma fonte de arquivo "Saldos Backfill" com o arquivo "extrato_ok.csv" para o dia "2026-07-10"
    Quando executo a fonte de arquivo "Saldos Backfill" de "2026-07-09" a "2026-07-11"
    Então a execução de arquivo registra status "SUCESSO" com 2 inseridas e 0 com erro
