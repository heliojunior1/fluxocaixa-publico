# language: pt
Funcionalidade: Texto de cadastro renderizado sem execução de HTML
  Spec relatorios R21 (change escapar-html-dinamico-relatorios)

  A descrição de qualificador é campo LIVRE — o serviço valida o formato do
  código e a unicidade, não o conteúdo. Um usuário com FC_INS_QUALIFICADOR
  (perfil OPERADOR) cadastra o payload pela porta legítima.

  ⚠️ O escape do RELATÓRIO é do lado do cliente (`escHtml`), então quem o afere
  é o E2E Playwright — teste de servidor veria a string, não o DOM. O que cabe
  aqui é a outra metade, que É do servidor: as telas renderizadas por Jinja
  devem escapar a descrição, e ninguém pode reintroduzir `|safe` sobre ela.

  Contexto:
    Dado que estou autenticado como administrador

  Cenário: Tela server-rendered escapa a descrição
    Dado um qualificador "8.61.1" com descrição "<img src=x onerror=alert(1)>Receita"
    Quando abro a tela de qualificadores
    Então a marcação aparece escapada no HTML
    E a marcação não aparece crua no HTML

  Cenário: Aspas na descrição não escapam do atributo
    Dado um qualificador "8.61.2" com descrição "Rubrica \"citada\" e <b>marcada</b>"
    Quando abro a tela de qualificadores
    Então a marcação não aparece crua no HTML

  Cenário: Dados do relatório trafegam como dado, não como HTML
    Dado um qualificador "8.61.3" com descrição "<b>Bruta</b>"
    E um lançamento fictício de 1234.56 nesse qualificador
    Quando consulto os dados do relatório DFC
    Então a descrição chega íntegra como valor de dado
