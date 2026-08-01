# language: pt
Funcionalidade: Perfis e permissões por verbo e recurso
  Como tesouraria, quero que cada usuário só faça o que seu perfil permite,
  com auditoria de quem fez o quê.

  Cenário: Matriz de perfis seedada no boot
    Então os perfis "ADMINISTRADOR,GESTOR_FINANCEIRO,OPERADOR,CONSULTA,EXTRACAO" existem
    E o usuário "admin" possui todos os perfis

  Cenário: Perfil CONSULTA não cria lançamento
    Dado um usuário autenticado com o perfil "CONSULTA"
    Quando tenta criar um lançamento válido
    Então recebe status 403
    E nenhum lançamento novo foi criado

  Cenário: Perfil OPERADOR cria lançamento
    Dado um usuário autenticado com o perfil "OPERADOR"
    Quando tenta criar um lançamento válido
    Então o lançamento é criado com sucesso

  Cenário: Auditoria registra o usuário da sessão
    Dado um usuário autenticado com o perfil "OPERADOR"
    Quando tenta criar um lançamento válido
    Então o lançamento criado registra esse usuário como autor

  Cenário: Página 403 amigável no navegador
    Dado um usuário autenticado com o perfil "CONSULTA"
    Quando acessa a tela "/simulador/novo"
    Então recebe a página 403 informando a permissão "FC_INS_PREVISAO"

  Cenário: Botão de novo lançamento oculto sem permissão
    Dado um usuário autenticado com o perfil "CONSULTA"
    Quando acessa a tela "/saldos"
    Então a página não exibe o elemento "novo-lancamento"

  Cenário: Botão de novo lançamento visível com permissão
    Dado um usuário autenticado com o perfil "OPERADOR"
    Quando acessa a tela "/saldos"
    Então a página exibe o elemento "novo-lancamento"

  Cenário: init-db exige FC_ADMIN_BANCO
    Dado um usuário autenticado com o perfil "CONSULTA"
    Quando acessa a tela "/init-db"
    Então recebe status 403

  Cenário: Admin acessa com todos os perfis
    Dado que estou autenticado como admin de testes
    Quando acessa a tela "/saldos"
    Então o recurso é servido com status 200

  Cenário: Customização da matriz é preservada pelo seed
    Dado que a instalação removeu a permissão "FC_DEL_LANCAMENTO" do perfil "OPERADOR"
    Quando o seed de domínio executa novamente
    Então o perfil "OPERADOR" continua sem a permissão "FC_DEL_LANCAMENTO"
