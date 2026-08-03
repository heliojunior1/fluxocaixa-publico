# language: pt
Funcionalidade: Sessão revalidada e revogável
  Spec controle-acesso R13 + R3 (change sessao-revalidada-e-revogavel)

  A sessão nunca revalidava o usuário: `ind_status` era conferido só no login.
  Como NÃO HÁ tela de usuários (gestão via banco, decisão de produto), marcar
  `'I'` É o mecanismo de desligamento — e ele não funcionava justamente para
  quem já estava dentro, que é o caso que importa.

  E trocar a senha, o gesto padrão de resposta a comprometimento, não revogava
  nada: o cookie roubado seguia válido até expirar.

  Cenário: Usuário desativado perde a sessão em curso
    Dado um usuário ativo "ana.sessao" com senha "Segredo-Forte-1"
    E estou autenticado como "ana.sessao"
    Quando o usuário "ana.sessao" é desativado
    E acesso outra tela
    Então o acesso é recusado

  Cenário: Troca de senha invalida a sessão antiga
    Dado um usuário ativo "bruno.sessao" com senha "Segredo-Forte-1"
    E estou autenticado como "bruno.sessao"
    E tenho uma segunda sessão aberta de "bruno.sessao"
    Quando "bruno.sessao" troca a senha para "Outra-Senha-9"
    E a segunda sessão acessa outra tela
    Então o acesso é recusado

  Cenário: Sessão expira por inatividade
    Dado um usuário ativo "caio.sessao" com senha "Segredo-Forte-1"
    E estou autenticado como "caio.sessao"
    Quando passa mais tempo que o limite de inatividade
    E acesso outra tela
    Então o acesso é recusado

  Cenário: Atividade renova o prazo
    Dado um usuário ativo "duda.sessao" com senha "Segredo-Forte-1"
    E estou autenticado como "duda.sessao"
    Quando passa menos tempo que o limite de inatividade
    E acesso outra tela
    Então o acesso é permitido
