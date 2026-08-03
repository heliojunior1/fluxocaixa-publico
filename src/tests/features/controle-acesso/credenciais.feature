# language: pt
Funcionalidade: Endurecimento de credenciais e resistência a força bruta
  Spec controle-acesso R14 + R1/R4/R5 (change endurecer-credenciais-e-antibruteforce)

  Não havia contador de falhas, bloqueio nem atraso: `POST /login` aceitava
  tentativas ilimitadas. Somava-se a senha inicial `admin` e uma política de
  senha de 8 caracteres sem complexidade.

  Cenário: Bloqueio após tentativas consecutivas
    Dado um usuário ativo "eva.brute" com senha "Segredo-Forte-1"
    Quando envio 5 tentativas de login de "eva.brute" com senha incorreta
    E envio uma tentativa de "eva.brute" com a senha CORRETA
    Então o acesso é recusado com a mensagem genérica
    E nenhuma sessão é criada

  Cenário: Login válido zera o contador
    Dado um usuário ativo "fabio.brute" com senha "Segredo-Forte-1"
    Quando envio 2 tentativas de login de "fabio.brute" com senha incorreta
    E envio uma tentativa de "fabio.brute" com a senha CORRETA
    Então o acesso é permitido
    E o contador de falhas de "fabio.brute" está zerado

  Cenário: Bloqueio expira e o usuário legítimo volta
    Dado um usuário ativo "gina.brute" com senha "Segredo-Forte-1"
    Quando envio 5 tentativas de login de "gina.brute" com senha incorreta
    E passa mais tempo que o período de bloqueio
    E envio uma tentativa de "gina.brute" com a senha CORRETA
    Então o acesso é permitido

  Cenário: Login inexistente exercita a verificação de senha
    Quando tento autenticar o login inexistente "nao.existe.brute"
    Então o acesso é recusado com a mensagem genérica
    E a verificação de senha foi exercida

  Cenário: Em modo demo não há bloqueio
    Dado um usuário ativo "helo.brute" com senha "Segredo-Forte-1"
    E que o modo demonstração está ligado
    Quando envio 5 tentativas de login de "helo.brute" com senha incorreta
    E envio uma tentativa de "helo.brute" com a senha CORRETA
    Então o acesso é permitido
