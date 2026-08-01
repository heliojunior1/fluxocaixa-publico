# language: pt
Funcionalidade: Agendamento embutido das fontes de extração
  Spec extracao-configuravel R5 (change infra-extracao-agendador)

  Contexto:
    Dado que estou autenticado como administrador
    E um sistema de origem "SIS_X" cadastrado
    E o conector de teste "FAKE" registrado

  Cenário: Fonte ativa com cron gera job agendado
    Dado uma fonte "Agendada A" do tipo "FAKE" com cron "0 6 * * *"
    Quando o agendador inicia
    Então existe job agendado para a fonte "Agendada A"

  Cenário: Flag desabilitada não agenda nada
    Dado a flag do agendador desabilitada
    E uma fonte "Agendada B" do tipo "FAKE" com cron "0 6 * * *"
    Quando o agendador inicia
    Então não existe job agendado para a fonte "Agendada B"

  Cenário: Fonte sem cron não agenda job
    Dado uma fonte "Sem Cron" do tipo "FAKE"
    Quando o agendador inicia
    Então não existe job agendado para a fonte "Sem Cron"

  Cenário: Inativar fonte remove o job
    Dado uma fonte "Agendada C" do tipo "FAKE" com cron "0 6 * * *"
    E o agendador iniciado
    Quando inativo a fonte "Agendada C"
    Então não existe job agendado para a fonte "Agendada C"

  Cenário: Criar fonte com o agendador ativo agenda o job imediatamente
    Dado o agendador iniciado
    Quando crio a fonte "Agendada D" do tipo "FAKE" com cron "0 6 * * *"
    Então existe job agendado para a fonte "Agendada D"
