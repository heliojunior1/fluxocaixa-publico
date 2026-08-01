# language: pt
Funcionalidade: Tela de mapeamentos com builder, validação e preview
  Spec automacao-lancamentos R10/R11 (change tela-mapeamentos-builder)

  O texto é a verdade: o builder só gera `txt_regra`. Na edição, regra plana volta ao
  builder; regra com `não`/parênteses abre no modo avançado.

  Contexto:
    Dado que estou autenticado como administrador
    E um sistema de origem "SIS_X" cadastrado
    E os termos de regra padrão cadastrados
    E um qualificador folha "1.1.1"

  Cenário: Criar mapeamento com item pela tela
    Quando crio pela tela o mapeamento 2026 tipo "1" origem "SIS_X" com um item no qualificador "1.1.1" e regra "Unidade Gestora = '999001'"
    Então a lista de mapeamentos mostra o mapeamento 2026 tipo "1" origem "SIS_X"
    E o item salvo tem a regra "Unidade Gestora = '999001'"

  Cenário: Regra inválida impede salvar
    Quando crio pela tela o mapeamento 2026 tipo "1" origem "SIS_X" com um item no qualificador "1.1.1" e regra "Coisa Inexistente = '1'"
    Então a tela de mapeamentos mostra erro contendo "Coisa Inexistente"
    E o mapeamento 2026 tipo "1" origem "SIS_X" não existe

  # --- validar e prever, sem gravar (R10) ---

  Cenário: Validar regra sem salvar
    Quando peço pela tela a validação da regra "Coisa Inexistente = '1'"
    Então a validação responde inválida com mensagem contendo "Coisa Inexistente"
    E nenhum mapeamento existe

  Cenário: Validar regra boa responde válida
    Quando peço pela tela a validação da regra "Unidade Gestora = '999001'"
    Então a validação responde válida

  Cenário: Preview a partir da tela não grava
    Dado linhas na staging do sistema de origem "SIS_X"
    Quando peço pela tela o preview da regra "Natureza começa com '1112'" para "SIS_X"
    Então o preview da tela retorna 2 linhas
    E nenhuma linha da staging teve o status alterado

  # --- ida e volta builder × modo avançado (R10) ---

  Cenário: Regra plana abre no builder
    Dado um mapeamento salvo com a regra "Natureza começa com '1112' e Unidade Gestora = '999001'"
    Quando abro o mapeamento para edição
    Então a regra é apresentada no builder com 2 linhas

  Cenário: Regra com não e parênteses abre no modo avançado
    Dado um mapeamento salvo com a regra "não (Unidade Gestora = '999001')"
    Quando abro o mapeamento para edição
    Então a regra é apresentada no modo avançado
    E a regra apresentada é "não (Unidade Gestora = '999001')"

  Cenário: Regra com conectivos misturados abre no modo avançado
    Dado um mapeamento salvo com a regra "Natureza = '1112' e Unidade Gestora = '999001' ou Valor > 100"
    Quando abro o mapeamento para edição
    Então a regra é apresentada no modo avançado

  Cenário: Valor com apóstrofo é recusado no builder
    Quando peço pela tela a validação da regra montada com o valor "O'Brien"
    Então a validação responde inválida com mensagem contendo "apóstrofo"

  # --- controle de acesso (R11) ---

  Cenário: Sem permissão de manutenção não vejo as ações
    Dado que estou autenticado como usuário só de consulta
    Quando abro a lista de mapeamentos
    Então não vejo as ações de manutenção de mapeamento

  Cenário: Consulta pode prever a regra
    Dado que estou autenticado como usuário só de consulta
    E linhas na staging do sistema de origem "SIS_X"
    Quando peço pela tela o preview da regra "Natureza começa com '1112'" para "SIS_X"
    Então o preview da tela retorna 2 linhas
