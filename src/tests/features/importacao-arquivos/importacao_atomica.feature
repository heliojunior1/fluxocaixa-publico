# language: pt
Funcionalidade: Importação com contexto no token e lote atômico
  Spec importacao-arquivos R7/R8 (change importacao-atomica-sem-estado-global)

  O contexto (ano/data) viaja NO TOKEN do preview — nunca em atributo de
  classe compartilhado, onde dois usuários concorrentes se atropelavam e a
  carga entrava no ano errado em silêncio. Lote de execução/dotação é
  atômico: qualquer erro desfaz o lote inteiro. Ilha 2067/2068.

  Cenário: Dois previews concorrentes gravam cada um no seu ano
    Dado um qualificador folha de importação "1.69.1"
    E um preview de LOA para o ano 2067 com valor 1111.00
    E um segundo preview de LOA para o ano 2068 com valor 2222.00
    Quando confirmo o primeiro preview
    Então a LOA de 2067 para "1.69.1" vale 1111.00
    E não existe LOA de 2068 para "1.69.1"

  Cenário: Adapters sem estado de classe
    Quando inspeciono as classes dos adapters registrados
    Então nenhum adapter guarda contexto em atributo de classe

  Cenário: Erro no meio da planilha desfaz o lote inteiro
    Dado um órgão de importação 70020 e um qualificador folha de despesa "2.69.1"
    E um preview de execução 2067 com um empenho válido e uma liquidação de pai inexistente
    Quando confirmo o preview de execução
    Então nenhum documento de execução de 2067 foi gravado
    E o resultado reporta o erro da liquidação

  Cenário: Planilha sem erros grava tudo de uma vez
    Dado um órgão de importação 70020 e um qualificador folha de despesa "2.69.1"
    E um preview de execução 2067 com um empenho e sua liquidação encadeada
    Quando confirmo o preview de execução
    Então os 2 documentos de execução de 2067 foram gravados
    E o resultado reporta zero erros
