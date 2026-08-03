# language: pt
Funcionalidade: Limite e validação do arquivo enviado
  Spec importacao-arquivos R6 (change limites-e-validacao-de-upload)

  Os oito endpoints de importação liam o arquivo INTEIRO em memória antes de
  qualquer verificação. O `MAX_LINHAS` existente roda DEPOIS do parse completo
  — inútil contra este cenário. Como produção roda `--workers 1`, um arquivo de
  alguns GB derrubava a aplicação inteira, não só a requisição.

  O padrão certo já existia no projeto (`web/extracao.py`), num endpoint só.

  Contexto:
    Dado que estou autenticado como administrador

  Cenário: Arquivo acima do limite é recusado
    Quando envio para importação um arquivo maior que o limite
    Então a importação é recusada citando o limite
    E nenhuma pré-visualização é criada

  Cenário: Arquivo dentro do limite é processado
    Quando envio para importação um arquivo válido dentro do limite
    Então a pré-visualização é criada

  Cenário: Extensão não suportada é recusada
    Quando envio para importação um arquivo com extensão "pdf"
    Então a importação é recusada citando os formatos aceitos
