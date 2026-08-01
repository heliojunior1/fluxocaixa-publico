# language: pt
Funcionalidade: Cadastro de fontes de extração e registry de conectores
  Spec extracao-configuravel R1 e R2 (change infra-extracao-agendador)

  Contexto:
    Dado que estou autenticado como administrador
    E um sistema de origem "SIS_X" cadastrado
    E o conector de teste "FAKE" registrado

  Cenário: Criar fonte válida
    Quando crio a fonte "Saldos diários" do tipo "FAKE" com cron "0 6 * * *"
    Então a fonte "Saldos diários" existe ativa com auditoria preenchida

  Cenário: Config inválido para o schema do conector é rejeitado
    Quando crio a fonte "Sem caminho" do tipo "FAKE" sem o campo obrigatório "caminho"
    Então o cadastro é rejeitado com mensagem contendo "caminho"
    E a fonte "Sem caminho" não existe

  Cenário: Tipo de conector não registrado é rejeitado
    Quando crio a fonte "Tipo errado" do tipo "NAO_EXISTE" com cron "0 6 * * *"
    Então o cadastro é rejeitado com mensagem contendo "NAO_EXISTE"
    E a fonte "Tipo errado" não existe

  Cenário: Cron inválido é rejeitado no salvar
    Quando crio a fonte "Cron ruim" do tipo "FAKE" com cron "99 99 * * *"
    Então o cadastro é rejeitado com mensagem contendo "agenda"
    E a fonte "Cron ruim" não existe

  Cenário: Destino LANCAMENTO sem layout de staging é rejeitado
    Quando crio a fonte "Lançamentos SQL" do tipo "FAKE" com destino "LANCAMENTO"
    Então o cadastro é rejeitado com mensagem contendo "LANCAMENTO"
    E a fonte "Lançamentos SQL" não existe

  Cenário: Nome duplicado entre fontes ativas é rejeitado
    Dado uma fonte "Fonte Duplicada" do tipo "FAKE"
    Quando crio a fonte "Fonte Duplicada" do tipo "FAKE" com cron "0 6 * * *"
    Então o cadastro é rejeitado com mensagem contendo "nome"

  Cenário: Conector registrado dinamicamente fica disponível
    Então o tipo "FAKE" está entre os tipos de conector disponíveis

  Cenário: Registrar tipo duplicado é rejeitado
    Quando registro outro conector com o tipo "FAKE"
    Então o registro é recusado por tipo duplicado
