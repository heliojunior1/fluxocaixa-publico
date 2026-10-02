# Exercício, identidade da rubrica e De/Para

Como o sistema trata a passagem de um ano para o outro: o plano de
qualificadores por exercício, abrir e fechar exercício, a continuidade da
série histórica pela identidade da rubrica (raiz), o De/Para para fusões e
desdobramentos, e a automação de lançamentos com dois exercícios abertos.

> **Situação (02/10/2026):** tudo o que este documento descreve está
> implementado — plano por exercício, identidade estável (raiz), abertura por
> cópia (agora com os mapeamentos), herança de raiz, De/Para
> (`correspondencia-rubricas-entre-exercicios`) e exercício aberto/fechado com
> a automação por exercício (`exercicio-aberto-fechado`).

---

## 1. Visão geral

São quatro peças, cada uma com um papel:

| Peça | Responde a | Onde fica |
|---|---|---|
| **Exercício** | "Qual plano vale para este ano? O ano ainda aceita escrita?" | Plano de qualificadores por ano + situação aberto/fechado |
| **Identidade da rubrica (raiz)** | "Esta rubrica de 2027 é a mesma de 2026?" | `cod_rubrica_raiz` em cada qualificador |
| **De/Para** | "Esta rubrica de 2027 veio da fusão ou do desdobramento de quais de 2026?" | Tela *Previsão → De/Para de rubricas* |
| **Automação por exercício** | "Esta linha extraída pertence a qual ano, e em que dia ela entra no caixa?" | Extração → staging → mapeamento do exercício |

A regra que amarra tudo: **o realizado nunca é reescrito**. Lançamentos de
2026 continuam no plano de 2026 com a classificação de 2026. A raiz e o De/Para
só servem para **ler** o passado na estrutura do ano atual quando a previsão
precisa de série histórica.

---

## 2. Exercício e plano de qualificadores

- Cada exercício tem o **seu** plano: as linhas de qualificador de 2027 são
  diferentes das de 2026, mesmo quando código e descrição são iguais.
- O código é único **dentro do ano**: "1.1.1" pode existir em 2026 e em 2027.
- Pai e filho são sempre do mesmo exercício.
- Lançamento, importação e ajuste apontam para o qualificador **do ano do
  registro**: um lançamento de março/2027 usa a rubrica do plano de 2027.
- **Ano sem plano próprio** usa o plano mais recente anterior. É o
  comportamento de uma instalação que nunca abriu exercício: tudo continua
  funcionando como antes.
- Telas e relatórios mostram um exercício por vez. A tela de qualificadores tem
  o combo de exercício.

---

## 3. Abrir exercício

Na tela de qualificadores, botão **Abrir exercício**: escolhe o ano de origem
(ex.: 2026) e o novo (ex.: 2027). A abertura é uma **cópia única**: abrir um ano
que já tem plano é recusado, porque abertura não é sincronização.

### O que a abertura copia

| Item | Como vai | Por quê |
|---|---|---|
| Qualificadores **ativos** | Cópia com a hierarquia remapeada | O plano novo nasce igual ao anterior |
| Identidade (raiz) | A cópia leva a **mesma raiz** | A série histórica continua sem nenhum passo manual |
| Categoria fiscal e setor de previsão | A marcação **própria** de cada nó | A herança pela árvore continua valendo |
| Fórmulas da biblioteca | Cópia por valor | Editar a fórmula de 2027 não altera o que 2026 projeta |
| Cenários de previsão do ano novo | Marcações, fórmulas, ajustes e configuração re-apontados pela raiz | A previsão de 2027 não "perde" o método |
| **Mapeamentos** | Um por sistema de origem, com os itens re-apontados para os qualificadores copiados, mesma regra, sem marcador de execução | O mapeamento de 2027 nasce pronto; a equipe só ajusta o que mudou |

### O que a abertura **não** copia

- **LOA, dotação e programação de desembolso:** são peças orçamentárias do ano,
  não estrutura.
- **Lançamentos:** o realizado fica no ano dele.
- **Qualificadores inativos.** Item de mapeamento que apontava para rubrica
  não copiada também não é copiado e aparece no relatório da abertura.

### Depois de abrir: ajustar o plano novo

| O que aconteceu com a rubrica | O que fazer | A identidade (raiz) |
|---|---|---|
| Continua igual | Nada | Já veio na cópia |
| Mudou de código ou nome | **Editar** a rubrica no plano novo | Preservada: renomear ou renumerar não mexe nela |
| Mudou de lugar na árvore | Reapontar o pai | Preservada |
| É realmente nova | Criar | Nasce própria, sem histórico (correto) |
| Volta de rubrica extinta | Criar usando **"herdar raiz"** | Escolhida manualmente |
| Fusão ou desdobramento | Cadastrar no **De/Para** | Ver seção 6 |

> ⚠️ Para mudar o código de uma rubrica, **edite** a que veio na cópia. Excluir
> e criar de novo faz a nova nascer com raiz própria, e a série histórica se
> perde, a não ser que alguém use "herdar raiz".

---

## 4. Fechar e reabrir exercício

Tela **Cadastros → Exercícios**: lista os anos com a situação (aberto ou
fechado), as pendências da automação e o histórico.

- **Abrir 2027 não fecha 2026.** Na virada os dois ficam abertos ao mesmo tempo.
- **Ano sem registro de situação é aberto.** Nada muda para quem não usa o
  fechamento.

### Fechar

- **Exige motivo e confirmação.**
- Antes de confirmar, o sistema mostra o que está **pendente** naquele ano: linhas
  da staging que não viraram lançamento e linhas em erro.
- Efeitos com o exercício fechado:

| O que | Situação |
|---|---|
| Plano de qualificadores do ano | Somente leitura (criar, editar, inativar e herdar raiz são recusados) |
| Mapeamentos do ano | Somente leitura |
| Lançamento com data no ano | Criar, alterar, inativar e importar são recusados |
| Extração automática | Não roda para o ano; linhas daquele ano são descartadas com aviso |
| Processamento (mapeamento → lançamento) | Não roda para o ano |
| Previsão, cenários, versões, De/Para | **Não** são travados |
| Relatórios | Continuam lendo normalmente |

### Reabrir

- Exige **permissão própria** e **motivo**.
- Volta a aceitar escrita e automação.

Todo gesto (abrir, fechar, reabrir) vira um **evento** com autor, data e
motivo, e nada é apagado.

| Permissão | Para quê |
|---|---|
| `FC_ABRIR_EXERCICIO` | Abrir |
| `FC_FECHAR_EXERCICIO` | Fechar |
| `FC_REABRIR_EXERCICIO` | Reabrir |
| `FC_CONS_EXERCICIO` | Consultar |

---

## 5. Identidade da rubrica (raiz) e a série histórica

Cada qualificador tem `cod_rubrica_raiz`, o "CPF" da rubrica:

- **Nasce sozinha:** ao criar, a raiz é o próprio identificador da linha.
- **Vai junto na abertura:** a cópia de 2027 tem a raiz da original de 2026.
- **Nunca muda** com renome, renumeração ou mudança de pai.
- **Herdar raiz:** ao criar uma rubrica, dá para declarar que ela continua outra,
  por exemplo ao reativar uma rubrica extinta. A herança é recusada se:
  - outra rubrica ativa do mesmo ano já usa aquela raiz (a série seria somada em
    dobro);
  - a natureza é diferente (receita × despesa).

### Quem usa a raiz

- **Série histórica da previsão:** soma os lançamentos de todas as linhas com a
  mesma raiz. A rubrica de 2027 enxerga 2024, 2025 e 2026.
- **Versão de previsão publicada antes da abertura:** é traduzida pela raiz na
  leitura do DFC e dos relatórios, sem reescrever a versão.
- **Previsão × Realizado:** soma o realizado pela raiz.
- **Abertura:** re-aponta os cenários de previsão pela raiz.

A raiz cobre a **continuidade simples (1:1)**. Ela não representa "duas
rubricas viraram uma" nem "uma virou duas". Isso é papel do De/Para.

---

## 6. De/Para de rubricas (fusão e desdobramento)

Tela **Previsão → De/Para de rubricas**. O sistema não detecta sozinho que uma
rubrica foi fundida ou desdobrada: alguém registra, com o ato que fundamenta.

### Antes de cadastrar

- **Origens** existem no plano anterior à vigência.
- **Destinos** existem no plano do ano da vigência como rubricas **novas**, sem
  herdar a raiz de uma origem. Se herdarem, o cadastro recusa, porque a origem
  seria contada duas vezes (pela raiz e pelo De/Para).
- A origem não pode continuar ativa no ano da vigência.
- Origens e destinos têm a mesma natureza.

### Os cinco casos

| Situação | Série de previsão do destino antes da vigência |
|---|---|
| Continuidade simples | Pela raiz (não usa o De/Para) |
| **Fusão** (A + B → C) | Soma integral de A e B |
| **Desdobramento com detalhe na origem** | Reconstruída: a regra de cada destino é aplicada aos atributos dos lançamentos automáticos da origem. **Só vale se reconciliar** mês a mês com o total da origem |
| **Desdobramento com rateio** | Origem × percentual de cada destino; esses meses ficam **marcados como estimados** |
| **Desdobramento sem fundamento** | **Distribuição pendente**: ninguém inventa a divisão |

### Desdobramento, passo a passo

1. **Cadastrar a estrutura:** tipo *Desdobramento*, vigência, origem, destinos,
   ato e fundamento. Opcionalmente, uma regra de reconstrução por destino no
   formato `código | regra`, na mesma linguagem do mapeamento, por exemplo
   `1.2.3 | Natureza começa com '1121'`.
2. **Reconstrução:** se houver regras, o sistema confere se a soma das partes
   bate com o total da origem em todos os meses. Lançamento manual ou importado
   não tem atributos de origem, e a reconciliação daquele mês falha. Quando não
   reconcilia, vale o passo 3 ou o 4.
3. **Rateio:** no cartão da correspondência há um percentual por destino e um
   campo de fundamento.
   - A tela sugere percentuais pelo realizado dos destinos desde a vigência.
   - A sugestão só vale depois de conferida e registrada.
   - É uma permissão separada (`FC_DEFINIR_RATEIO_CORRESPONDENCIA`): a estrutura
     é classificação oficial, o rateio é estimativa da tesouraria.
4. **Pendente:** sem reconstrução nem rateio, a previsão é feita no **total do
   grupo** de destinos:
   - o valor aparece uma vez, sem rubrica, na linha "Projeção do cenário (não
     detalhada)" do DFC;
   - na simulação de disponibilidade, vai para o grupo "não classificado", fora
     do modo prudente;
   - os destinos aparecem como **"Distribuição pendente"** na cobertura;
   - publicar a versão exige confirmação.

### Versão do De/Para

- Nada é editado no lugar. Para corrigir uma correspondência, inative e cadastre
  outra; para trocar o rateio, registre um novo.
- Cada gesto é um evento, e o número do último evento é a **versão do De/Para**.
- A simulação usa uma versão fixa, e a versão salva da previsão a grava no
  resumo. Mudar o De/Para amanhã não muda a explicação de um número publicado
  hoje.

### O que o De/Para **não** faz

- Não altera lançamentos, nem relatórios de realizado, nem fonte de recursos.
- Não cobre N:M num único ato: representa-se como dois atos encadeados. Fusões e
  desdobramentos em anos seguidos se compõem: os percentuais multiplicam pelo
  caminho.

---

## 7. Lançamentos automáticos com dois exercícios abertos

### Três informações por linha extraída

| Campo (destino no layout da fonte) | O que é | Para que serve |
|---|---|---|
| `num_ano_exercicio` | Exercício do documento na origem | Escolhe o **mapeamento e as rubricas** daquele ano |
| `dat_saldo` (data do movimento) | Data de emissão / data contábil | Vira a **data do lançamento**, o dia que impacta o caixa |
| `dat_registro` | Quando o documento foi registrado na origem | **Janela** da extração |

Se a origem não informa o exercício, vale o ano da data do movimento. Antes,
todas as linhas recebiam o ano do fim da janela.

### Extração

- **Por exercício aberto:** consulta de banco que usa `:ano` roda **uma vez para
  cada exercício aberto** entre o ano anterior ao início da janela e o ano do
  fim dela. Em janeiro de 2027, com 2026 e 2027 abertos, roda para os dois.
- **Exercício fechado:** linhas daquele ano são descartadas, e a execução
  registra um aviso.
- **Dias retroativos:** a carga agendada cobre os últimos N dias, configurável
  por fonte. Um documento registrado hoje com emissão em dezembro entra na
  carga de hoje e cai no dia de dezembro.
- **Reextração substitui:** rodar de novo a mesma fonte, exercício e janela
  **troca** as linhas da staging daquela janela, e os lançamentos gerados por
  elas são refeitos. Nunca acumula.

### Processamento

- Cada linha vai para o **mapeamento do seu exercício**. Mapeamento de
  exercício fechado não processa.
- O item do mapeamento só pode apontar rubrica do **mesmo exercício** do
  mapeamento. Ao cadastrar, isso é recusado; no processamento, item fora da
  regra vira erro explícito, nunca lançamento.
- Linha que não casa com nenhuma regra há mais de 7 dias aparece num **aviso**
  na tela de execuções de mapeamento, por exercício e sistema de origem.

---

## 8. A virada na prática (exemplo)

| Quando | O que acontece / o que fazer |
|---|---|
| Out–dez/2026 | Classificação de 2027 publicada. **Abrir 2027** a partir de 2026 (plano, fórmulas e mapeamentos copiados). Ajustar o plano de 2027: editar códigos que mudaram, criar rubricas novas, cadastrar fusões e desdobramentos no De/Para |
| Dez/2026 | Ajustar o **mapeamento de 2027** para as naturezas novas. Montar a previsão de 2027: a série vem pela raiz e pelo De/Para |
| Jan/2027 | 2026 e 2027 **abertos**. A carga diária roda para os dois: ajustes de 2026 registrados em janeiro vão para o mapeamento de 2026; movimentos de 2027, para o de 2027 |
| Fev/2027 (após o encerramento na origem) | Conferir as pendências de 2026 na tela de exercícios. **Fechar 2026** com motivo. A partir daí, 2026 é registro: só leitura |
| Se precisar corrigir 2026 depois | **Reabrir 2026** com motivo e corrigir. Fechar de novo |

---

## 9. Perguntas frequentes

**Preciso mexer na raiz toda vez que abro um ano?**
Não. A abertura copia a raiz. O manual fica só para reativação ("herdar raiz")
e para fusão ou desdobramento (De/Para).

**Por que não usar só o De/Para, com uma linha 1:1 para cada rubrica?**
Seriam centenas de linhas óbvias por ano, e esquecer uma corta a série em
silêncio. A raiz faz da continuidade o padrão, e o De/Para fica só para a
exceção. É o padrão de "chave durável + tabela de correspondência" das
classificações oficiais versionadas.

**Fechar um exercício apaga alguma coisa?**
Não. Fechar só trava a escrita e a automação daquele ano. Reabrir devolve tudo.

**O que acontece com a previsão quando fecho o ano?**
Nada. Cenários, versões e De/Para não são travados.

**Lancei um ajuste de 2026 em janeiro de 2027. Ele entra?**
Entra, enquanto 2026 estiver aberto: pela data de registro na janela da carga
diária, com o exercício 2026 e a data do movimento de 2026.

---

## 10. Referências no código

| Assunto | Onde |
|---|---|
| Plano por exercício, abertura, herança | `services/qualificador_service.py` (`abrir_exercicio`, `resolver_exercicio_do_plano`, `create_qualificador`) |
| Série de previsão (raiz + De/Para) | `services/serie_historica.py` (`serie_mensal`) |
| De/Para | `services/correspondencia_rubrica_service.py`, tela `/previsao/correspondencias` |
| Grupo pendente na projeção | `services/metodo_qualificador_service.py` (`_unidades`, `emitir_grupo`) |
| Exercício aberto/fechado | `services/exercicio_service.py`, tela `/exercicios` |
| Extração e processamento por exercício | `services/extracao_service.py`, `services/staging_service.py`, `services/processamento_service.py` |
