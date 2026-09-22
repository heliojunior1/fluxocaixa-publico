# language: pt
Funcionalidade: Previsão por qualificador — método por rubrica, cópia e propostas setoriais
  docs/previsao-metodo-por-qualificador.md (RN01–RN29)

  Um cenário pode projetar TODOS os qualificadores sozinho, misturando métodos
  por rubrica: a marcação fica em qualquer nó, as folhas herdam e a mais próxima
  vence. Setores são opcionais: publicam propostas que outro cenário fixa num nó.
  Ilha: plano do exercício 2097, receita "1.88", despesa "2.88", realizado em
  2094–2096.

  Contexto:
    Dado o plano da ilha com realizado de 2096
      | codigo   | pai    | realizado |
      | 1.88     |        |           |
      | 1.88.1   | 1.88   |           |
      | 1.88.1.1 | 1.88.1 | 300.00    |
      | 1.88.1.2 | 1.88.1 | 100.00    |
      | 1.88.2   | 1.88   | 50.00     |
      | 1.88.3   | 1.88   | 20.00     |
      | 2.88     |        |           |
      | 2.88.1   | 2.88   | 80.00     |

  Cenário: Marcação no bloco herda para as folhas e a da folha vence
    Dado um cenário "CEN_MQ_HERANCA" sem padrão de receita
    E a marcação "1.88.1" com valor fixo anual "1200.00"
    E a marcação "1.88.1.2" com percentual "10"
    Então a folha "1.88.1.1" resolve "VALOR_FIXO" herdado de "1.88.1"
    E a folha "1.88.1.2" resolve "PERCENTUAL" próprio

  Cenário: Valor fixo no bloco é distribuído pela participação histórica
    Dado um cenário "CEN_MQ_DISTRIBUI" sem padrão de receita
    E a marcação "1.88.1" com valor fixo anual "1200.00"
    Quando executo o cenário
    Então a folha "1.88.1.1" projeta "900.00" no ano
    E a folha "1.88.1.2" projeta "300.00" no ano
    E as projeções da folha "1.88.1.1" registram o método "VALOR_FIXO" calculado em "1.88.1"

  Cenário: Rubrica sem método é lacuna; sem projeção declarada não é
    Dado um cenário "CEN_MQ_COBERTURA" sem padrão de receita
    E a marcação "1.88.1" com valor fixo anual "1200.00"
    E a marcação "1.88.2" sem projeção pelo motivo "rubrica extinta"
    Quando calculo a cobertura
    Então a folha "1.88.3" é lacuna na cobertura
    E a folha "1.88.2" aparece como sem projeção declarada
    E a cobertura aponta 1 lacuna

  Cenário: Publicar com lacuna exige confirmação
    Dado um cenário "CEN_MQ_PUBLICA" sem padrão de receita
    E a marcação "1.88.1" com valor fixo anual "1200.00"
    Quando tento publicar uma versão sem confirmar
    Então recebo o erro de previsão "sem projeção"
    E consigo publicar confirmando e a versão registra as lacunas

  Cenário: Método incompatível com a perna é recusado
    Dado um cenário "CEN_MQ_PERNA" sem padrão de receita
    Quando tento marcar "1.88.2" com o método LOA
    Então recebo o erro de previsão "não se aplica a receita"

  Cenário: Duplicar cria cópia independente e sem versões
    Dado um cenário "CEN_MQ_ORIGEM" sem padrão de receita
    E a marcação "1.88.1" com valor fixo anual "1200.00"
    E a fórmula própria "base * 2" para a folha "1.88.2"
    E o cenário tem uma versão publicada
    Quando duplico o cenário como "CEN_MQ_COPIA"
    E altero na cópia a marcação "1.88.1" para valor fixo anual "600.00"
    E altero na cópia a fórmula própria da folha "1.88.2" para "base * 3"
    Então a origem mantém "1.88.1" com valor fixo anual "1200.00"
    E a origem mantém a fórmula própria "base * 2" para "1.88.2"
    E a cópia não tem versões e aponta a origem

  Cenário: Fórmula própria do cenário vence a da biblioteca
    Dado a fórmula de biblioteca "base * 10" para a folha "1.88.2"
    E um cenário "CEN_MQ_FORMULA" sem padrão de receita
    E a marcação "1.88.2" com fórmula
    E a fórmula própria "base * 2" para a folha "1.88.2"
    Quando executo o cenário
    Então a folha "1.88.2" projeta "100.00" no ano

  Cenário: Cenário setorial só marca o recorte do setor
    Dado o setor "BDDMQ" com recorte "1.88.2"
    E um cenário "CEN_MQ_SETORIAL" do setor "BDDMQ"
    Quando tento marcar "1.88.3" com valor fixo anual "10.00"
    Então recebo o erro de previsão "fora do recorte"

  Cenário: Proposta do setor é fixada por versão no cenário consumidor
    Dado o setor "BDDMQ" com recorte "1.88.2"
    E um cenário "CEN_MQ_SETOR_IPVA" do setor "BDDMQ"
    E a marcação "1.88.2" com valor fixo anual "240.00"
    E o cenário setorial publica a proposta "v1"
    E um cenário "CEN_MQ_CONSOLIDADO" sem padrão de receita
    E a marcação "1.88.1" com valor fixo anual "1200.00"
    E a marcação "1.88.2" com a proposta "v1" do cenário "CEN_MQ_SETOR_IPVA"
    Quando o setor publica a proposta "v2" com valor fixo anual "480.00"
    E executo o cenário "CEN_MQ_CONSOLIDADO"
    Então a proposta "v1" está enviada
    E a folha "1.88.2" projeta "240.00" no ano
    E devolver a proposta "v1" é recusado porque está fixada

  Cenário: Duas propostas não podem cobrir as mesmas folhas
    Dado o setor "BDDMQ" com recorte "1.88"
    E um cenário "CEN_MQ_SETOR_TODO" do setor "BDDMQ"
    E a marcação "1.88" com valor fixo anual "100.00"
    E o cenário setorial publica a proposta "v1"
    E um cenário "CEN_MQ_CONFLITO" sem padrão de receita
    E a marcação "1.88" com a proposta "v1" do cenário "CEN_MQ_SETOR_TODO"
    Quando tento marcar "1.88.2" com a proposta "v1" do cenário "CEN_MQ_SETOR_TODO"
    Então recebo o erro de previsão "Conflito de propostas"

  Cenário: Modelo agregado da perna sai distribuído por folha
    Dado um cenário "CEN_MQ_AGREGADO" com média de crescimento na receita para "1.88.1.1" e "1.88.1.2"
    Quando executo o cenário
    Então a projeção detalhada traz as folhas "1.88.1.1" e "1.88.1.2" somando o total da perna

  Cenário: Relatório de previsão de receita lê a versão publicada
    Dado um cenário "CEN_MQ_RELATORIO" sem padrão de receita
    E a marcação "1.88.1" com valor fixo anual "1200.00"
    E o cenário tem uma versão publicada
    E altero a marcação "1.88.1" para valor fixo anual "99999.00"
    Quando consulto a previsão de receita de 2097 para "1.88.1.1"
    Então a previsão anual é "900.00" vinda da versão publicada

  Cenário: Alterar a biblioteca afeta só quem usa a fórmula por referência
    Dado a fórmula de biblioteca "base * 10" para a folha "1.88.2"
    E um cenário "CEN_MQ_REFERENCIA" sem padrão de receita
    E a marcação "1.88.2" com fórmula
    E um cenário "CEN_MQ_PROPRIA" sem padrão de receita
    E a marcação "1.88.2" com fórmula
    E a fórmula própria "base * 2" para a folha "1.88.2"
    Então os cenários afetados pela fórmula da biblioteca de "1.88.2" são "CEN_MQ_REFERENCIA"
