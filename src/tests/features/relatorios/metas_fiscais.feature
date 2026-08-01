# language: pt
Funcionalidade: Metas fiscais por categoria explícita
  Spec `relatorios` R17–R19: as metas somam os qualificadores cuja CATEGORIA
  RESOLVIDA é a da meta — a descrição deixa de decidir. Limiares e base de
  cálculo vêm da categoria. Meta sem fonte de dado não é exibida como apurada.

  Ilha 2018, ramo "2.7" sob a raiz de despesa.

  # ------------------------------------------------------------------ R17

  Cenário: Descrição com a palavra não conta se não estiver marcada
    # Era assim que a heurística acertava por acidente — e errava do mesmo jeito.
    Dado a folha "2.7.1" chamada "Aplicação em Educação Básica" sem marcação
    E lançamentos de "10000.00" em "2.7.1" no ano
    Quando consulto as metas fiscais do ano
    Então a meta "Aplicação em Educação" tem percentual "0.0"

  Cenário: Marcação decide, mesmo sem a palavra na descrição
    Dado a folha "2.7.1" chamada "Ensino Fundamental" marcada como "EDUCACAO"
    E lançamentos de "10000.00" em "2.7.1" no ano
    Quando consulto as metas fiscais do ano
    Então a meta "Aplicação em Educação" tem percentual "100.0"

  Cenário: Folhas herdam a marcação do bloco
    # O caso que a heurística ZERAVA: bloco casaria a palavra, mas não é folha;
    # folhas são folhas, mas não casam a palavra.
    Dado o bloco "2.7" chamado "EDUCACAO" marcado como "EDUCACAO"
    E a folha "2.7.1" chamada "Ensino Fundamental" sem marcação sob "2.7"
    E a folha "2.7.2" chamada "Merenda Escolar" sem marcação sob "2.7"
    E lançamentos de "6000.00" em "2.7.1" no ano
    E lançamentos de "4000.00" em "2.7.2" no ano
    Quando consulto as metas fiscais do ano
    Então a meta "Aplicação em Educação" tem percentual "100.0"

  Cenário: Qualificador sem categoria não entra em meta alguma
    Dado a folha "2.7.1" chamada "Despesa Diversa" sem marcação
    E lançamentos de "10000.00" em "2.7.1" no ano
    Quando consulto as metas fiscais do ano
    Então nenhuma meta de aplicação tem percentual acima de zero

  # ------------------------------------------------------------------ R18

  Cenário: Piso alterado muda o veredito
    Dado a folha "2.7.1" chamada "Atenção Básica" marcada como "SAUDE"
    E lançamentos de "1300.00" em "2.7.1" no ano
    E a folha "2.7.2" chamada "Despesa Diversa" sem marcação
    E lançamentos de "8700.00" em "2.7.2" no ano
    Quando consulto as metas fiscais do ano
    Então a meta "Aplicação em Saúde" está fora do piso
    Quando o piso da categoria "SAUDE" passa a "12"
    E consulto as metas fiscais do ano
    Então a meta "Aplicação em Saúde" está dentro do piso

  Cenário: Cada meta usa o denominador da sua própria categoria
    # PESSOAL mede sobre a RCL; SAUDE e EDUCACAO sobre a despesa total. Sem
    # base de cálculo na categoria, isso viraria um `if` pela sigla.
    Dado a folha "2.7.1" chamada "Folha de Pagamento" marcada como "PESSOAL"
    E lançamentos de "5000.00" em "2.7.1" no ano
    E receita realizada de "20000.00" no ano
    Quando consulto as metas fiscais do ano
    Então a meta "Despesa com Pessoal" tem percentual "25.0"
    E a meta "Despesa com Pessoal" mede sobre "RCL"
    E a meta "Aplicação em Saúde" mede sobre "Despesa total"

  # ------------------------------------------------------------------ R19

  Cenário: Dívida consolidada não é exibida
    Quando consulto as metas fiscais do ano
    Então não existe meta de dívida consolidada

  Cenário: Meta de superávit vem do valor informado
    Dado a meta de superávit primário do ano informada como "1500.00"
    E receita realizada de "20000.00" no ano
    Quando consulto as metas fiscais do ano
    Então a meta "Superávit Primário" compara com "1500.00"
