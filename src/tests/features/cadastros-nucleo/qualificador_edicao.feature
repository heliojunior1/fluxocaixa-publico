# language: pt
Funcionalidade: Edição de qualificador
  Spec `cadastros-nucleo` R18: alterar um qualificador grava descrição, pai e
  categoria fiscal conforme informados.

  ⚠️ Esta funcionalidade existe porque a suíte inteira — 566 pytest e 48
  Playwright — passou verde com a edição respondendo 500. O único teste que
  chamava `update_qualificador` esperava um erro de negócio levantado ANTES da
  linha quebrada, então o caminho de SUCESSO nunca era executado. Teste que só
  cobre o caminho de erro de uma função não cobre a função.

  Ramo "7.2" — fora das raízes 1/2, para não entrar nas varreduras de relatório
  de outros testes.

  Cenário: Alteração bem-sucedida grava os três campos
    Dado o qualificador "7.2" chamado "Bloco Origem"
    E o qualificador "7.2.1" chamado "Rubrica Editavel" sob "7.2"
    Quando altero "7.2.1" para descrição "Rubrica Renomeada" com categoria "EDUCACAO"
    Então o qualificador "7.2.1" tem descrição "Rubrica Renomeada"
    E o qualificador "7.2.1" tem categoria própria "EDUCACAO"
    E o qualificador "7.2.1" tem pai "7.2"

  Cenário: Remover a marcação de categoria é possível
    Dado o qualificador "7.2" chamado "Bloco Origem"
    E o qualificador "7.2.1" chamado "Rubrica Marcada" sob "7.2" com categoria "SAUDE"
    Quando altero "7.2.1" para descrição "Rubrica Marcada" sem categoria
    Então o qualificador "7.2.1" não tem categoria própria
