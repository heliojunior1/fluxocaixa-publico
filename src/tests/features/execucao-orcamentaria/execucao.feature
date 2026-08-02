# language: pt
Funcionalidade: Execução orçamentária E/L/P (F8.2)
  Como Tesouro, quero a execução importada com eventos imutáveis, cadeia
  estrita e o liquidado não pago derivado — o "devido" do funil.

  Contexto:
    Dado que estou autenticado como administrador
    E um órgão "70009" chamado "Secretaria da Execução"
    E um qualificador folha de despesa "2.9.71"

  Cenário: Cadeia E→L com correntes derivados
    Dado um empenho "2050NE001" de 1000.00 em 2050 no órgão "70009" e qualificador "2.9.71"
    Quando registro a liquidação "2050NL001" de 800.00 em 2050 vinculada a "2050NE001"
    Então o corrente do documento "E" "2050NE001" de 2050 é 1000.00
    E o corrente do documento "L" "2050NL001" de 2050 é 800.00

  Cenário: Liquidação que estoura o empenho é recusada
    Quando registro a liquidação "2050NL002" de 300.00 em 2050 vinculada a "2050NE001"
    Então a operação de execução é rejeitada com a mensagem "Valor excede o saldo do documento-pai (disponível R$ 200.00)"

  Cenário: Anulação abaixo do consumido pelos filhos é recusada
    Quando registro uma anulação de 300.00 no documento "E" "2050NE001" de 2050
    Então a operação de execução é rejeitada com a mensagem "Anulação deixaria o documento abaixo do consumido pelos documentos-filho (R$ 800.00)"

  Cenário: Pagamento orçamentário direto no empenho é recusado
    Quando registro o pagamento "2050NP009" de 100.00 em 2050 vinculado ao empenho "2050NE001"
    Então a operação de execução é rejeitada com a mensagem "Pagamento orçamentário deve referenciar um(a) liquidação ativo(a)"

  Cenário: Liquidado não pago deriva da cadeia
    Dado o pagamento orçamentário "2050NP001" de 300.00 em 2050 vinculado à liquidação "2050NL001"
    Quando consulto o funil de 2050
    Então o liquidado não pago de 2050 é 500.00
    E o empenhado de 2050 é 1000.00

  Cenário: Fonte desconhecida na carga nasce vinculada e pendente
    Dado um empenho "2050NE002" de 200.00 em 2050 no órgão "70009" e qualificador "2.9.71" com a fonte "9.888"
    Então a fonte "9.888" da vigência 2050 existe vinculada e pendente de revisão
    E o documento "E" "2050NE002" de 2050 referencia a fonte "9.888" da vigência 2050

  Cenário: Liquidação sem fonte herda a do pai
    Quando registro a liquidação "2050NL003" de 100.00 em 2050 vinculada a "2050NE002"
    Então o documento "L" "2050NL003" de 2050 referencia a fonte "9.888" da vigência 2050
