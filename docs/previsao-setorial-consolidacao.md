# Previsão setorial e cenário consolidado

## Contexto e problema

Hoje um cenário do simulador é **monolítico**: uma configuração por perna
(`flc_cenario_config`, unicidade por cenário + perna `'C'`/`'D'`), um modelo por
perna, e a execução projeta a árvore de qualificadores inteira.

Em órgãos públicos de médio e grande porte, porém, a previsão é **federada**:
cada setor/unidade responde pela previsão do seu recorte da árvore. Exemplos
típicos:

- **Receita**: o setor responsável por IPVA envia a previsão de IPVA; o de
  ITCMD envia a dele; transferências constitucionais vêm de outra equipe.
- **Despesa**: dívida pública, precatórios, folha de pessoal — cada um com
  dono diferente.

Alguém (a equipe de programação financeira) precisa **juntar todas essas
previsões** num cenário único que alimente o DFC projetado e os relatórios.

O modelo atual não comporta isso: ou uma pessoa opera tudo num cenário só
(e recalcula a perna dos outros a cada execução), ou cada setor cria um
cenário isolado sem nenhum mecanismo de consolidação.

## Solução em duas partes

- **Parte A — Composição de cenários**: cada setor tem seu próprio cenário,
  restrito ao seu recorte de qualificadores, e publica versões normalmente.
  Um novo tipo de cenário, **CONSOLIDADO**, não roda modelo nenhum — ele
  **compõe** versões publicadas dos cenários setoriais.
- **Parte C — Importação setorial** (canal de entrada opcional): setores que
  enviam planilha em vez de operar o simulador alimentam o próprio cenário
  setorial via importação (upload → preview → confirmar), que grava os valores
  como ajustes MANUAL. A consolidação da Parte A segue idêntica.

A Parte A é a espinha dorsal; a C é um canal de entrada que se pendura nela.

---

## Parte A — Composição de cenários

### A.1 Cadastro de setor (`flc_setor_previsao`)

Tabela de domínio cadastrável, no padrão do projeto:

| Coluna | Tipo | Observação |
| --- | --- | --- |
| `seq_setor_previsao` | PK | |
| `nom_setor` | `String(100)` | Ex.: "Setor IPVA", "Dívida Pública" |
| `sgl_setor` | `String(20)` | Sigla curta, única entre ativos |
| `dsc_setor` | `String(255)` | Opcional |
| `ind_status` | `CHAR(1)` | Soft delete `'A'`/`'I'` |
| Auditoria | | `dat_inclusao`, `cod_pessoa_inclusao`, `dat_alteracao`, `cod_pessoa_alteracao` |

### A.2 Responsabilidade do setor na árvore — marcação com herança

O setor é dono de um **recorte da árvore de qualificadores**. A marcação vai
**no qualificador, com herança pela hierarquia** — exatamente o padrão já
estabelecido por `categoria_fiscal_service.categoria_resolvida`:

- Marca-se o **bloco** (ex.: o nó "IPVA" inteiro) e as folhas herdam.
- Marcação própria **vence** a herdada do pai ("mais próximo vence") — permite
  exceções pontuais dentro de um bloco.
- Marcar **não exige folha** (mesma exceção deliberada da categoria fiscal:
  marcar o bloco é o propósito).
- A responsabilidade resolvida **não é persistida**: é função da marcação +
  posição na árvore (o reapontamento de pai a muda para a subárvore inteira).
  A resolução memoiza o caminho inteiro por chamada, como a categoria fiscal.

Por que não marcar folha a folha: esquecer uma folha entre quarenta deixa uma
rubrica **sem dono em silêncio** — o mesmo defeito que a marcação de categoria
fiscal veio corrigir. Herança com visibilidade na tela (própria × herdada) é a
forma de o usuário auditar a atribuição.

Implementação: coluna `seq_setor_previsao` (FK nullable) em
`flc_qualificador` + serviço `setor_previsao_service.setor_resolvido(qualificador)`
como **origem única** da resposta "de quem é este qualificador?" (mesmo
estatuto de `is_folha()`, `valor_com_sinal`, `periodo_resolver`).

### A.3 Cenário setorial

`flc_simulador_cenario` ganha `seq_setor_previsao` (FK **nullable**):

- Cenário **sem setor** continua sendo o cenário global de hoje — nada quebra,
  nenhuma migração de dados é necessária.
- Cenário **com setor** é um cenário setorial: ajustes, projeções e modelos só
  podem endereçar qualificadores cujo setor resolvido seja o do cenário
  (validação em `_criar_ajustes` e na execução; violação =
  `RegraNegocioError` com mensagem pt-BR, nunca 500).
- O setor publica versões normalmente (`flc_projecao_versao` /
  `flc_projecao_valor`) — todo o mecanismo de versionamento, snapshot e
  publicação existente é reusado sem alteração.

### A.4 Cenário consolidado

Novo campo em `flc_simulador_cenario`: `cod_tipo_cenario` —
`'P'` próprio (default, comportamento atual) / `'K'` consolidado.

O cenário consolidado **não tem configs nem modelos**: sua "execução" é a
mescla de versões publicadas de cenários-fonte.

**Tabela de composição** (`flc_cenario_composicao`):

| Coluna | Tipo | Observação |
| --- | --- | --- |
| `seq_cenario_composicao` | PK | |
| `seq_simulador_cenario` | FK | O cenário consolidado |
| `seq_projecao_versao` | FK | A versão publicada **pinada** da fonte |
| `dat_inclusao` + auditoria | | |

⚠️ **A composição pina a VERSÃO, não o cenário.** Referenciar "a última
publicada" faria o consolidado mudar de conteúdo retroativamente quando um
setor publica de novo. Pinando `seq_projecao_versao`, o consolidado de julho
continua dizendo o que dizia mesmo que o setor de IPVA publique nova versão em
agosto. "Atualizar consolidação" = trocar o pin e **gerar nova versão do
consolidado** — a anterior permanece como registro histórico (versão publicada
não se reescreve, invariante já vigente no projeto).

**Execução da consolidação** (`consolidacao_service.consolidar(seq_cenario)`):

1. Valida as regras de negócio abaixo (tudo **antes** de gravar qualquer
   linha — falhar no meio deixaria a versão pela metade; mesmo princípio da
   cascata de renomeação de qualificadores).
2. Copia as linhas de `flc_projecao_valor` das versões pinadas para uma nova
   versão (rascunho) do cenário consolidado.
3. Grava um resumo por fonte em `json_inputs` da versão (auditoria: quais
   versões entraram, de quais cenários, publicadas quando e por quem).
4. O usuário revisa e **publica** — e a partir daí tudo a jusante funciona sem
   mudar uma linha: o DFC projetado lê `get_ultima_publicada` do consolidado
   como lê de qualquer cenário.

### A.5 Regras de negócio da mescla (as três obrigatórias)

1. **Conflito — mesmo qualificador em duas fontes = erro.**
   `RegraNegocioError` citando o qualificador e os dois cenários de origem.
   Nunca somar nem "o último vence": previsão dá **um** dono por rubrica;
   somar em silêncio dobraria o valor no caixa (mesma filosofia da
   classificação automática de lançamentos, que rejeita linha casada por 2+
   itens). O normal é o conflito nem nascer, porque a validação de escopo do
   cenário setorial (A.3) já restringe cada fonte ao seu recorte — esta checagem
   é defesa em profundidade contra remarcação da árvore entre a publicação e a
   consolidação.
2. **Cobertura — buraco não é zero.** Qualificador folha com movimento
   histórico que **nenhuma** fonte cobre entra num *relatório de cobertura* da
   consolidação (aviso visível na tela e no resumo da versão), e a
   consolidação só prossegue com confirmação explícita (`confirmado=true`,
   padrão do projeto). "Não recebi previsão" não pode ser indistinguível de
   "previsão zero" — é a mesma lição das metas fiscais: o relatório precisa
   separar *"aplicou pouco"* de *"não achei nada"*.
3. **Homogeneidade — mesmo ano-base e mesma periodicidade.** Na v1, fontes com
   `ano_base` ou `cod_periodicidade` divergentes = erro com mensagem clara.
   Normalizar periodicidades mistas via `mes_do_periodo` é possível no futuro,
   mas é complexidade adiável — e silenciosamente misturar semana com mês
   produziria números errados com cara de certos.

### A.6 Permissões e telas

- Permissões novas no catálogo (`auth/catalogo.py`):
  `FC_CONS_SETOR_PREVISAO` / `FC_MANT_SETOR_PREVISAO` (cadastro de setor) e
  `FC_EXEC_CONSOLIDACAO` (consolidar não é consulta — gera versão).
- O vínculo usuário↔setor pode começar simples: o cenário setorial é editável
  por quem tem a permissão de manutenção de cenário; restringir edição por
  setor do usuário é evolução futura (exigiria vínculo pessoa↔setor).
- Telas: CRUD de setor (padrão das telas de extração — um MANT cobre
  incluir/alterar/inativar); no form do cenário, combo de setor + tipo;
  tela de composição do consolidado (lista de fontes com versão pinada,
  botão "usar última publicada" que **grava o pin explícito**); relatório de
  cobertura na confirmação.
- Na árvore de qualificadores, exibir o setor resolvido **e se é próprio ou
  herdado** — herança sem visibilidade repetiria o defeito que a categoria
  fiscal já corrigiu.

---

## Parte C — Importação de previsão setorial

Para setores que **enviam números** (planilha) em vez de operar o simulador.
Não é um caminho paralelo de dados: a importação alimenta o **cenário setorial**
da Parte A, e a consolidação segue idêntica.

### C.1 Canal

Reusar a infraestrutura de importação com pré-processamento (upload →
preview sem gravar → confirmar, staging com TTL): registrar um **adapter
novo** em `services/preprocessamento_adapters.py`:

- `parse_validar` → lê CSV/XLSX (código do qualificador, ano, período, valor),
  valida contra o recorte do setor do cenário-alvo (qualificador fora do
  escopo = linha de erro no preview), valores em **magnitude positiva**
  (o sinal vem da perna — invariante R6 do simulador), períodos coerentes com
  a periodicidade do cenário (semana 53 só em ano ISO longo etc., via
  `periodo_resolver`).
- `gravar` → delega a `simulador_cenario_service`: upsert dos valores como
  **ajustes MANUAL** (`flc_cenario_ajuste`) na config da perna correspondente
  do cenário setorial. Reimportar substitui os ajustes anteriores da mesma
  chave (config, qualificador, ano, período) — a unicidade já existente
  garante isso por construção.

### C.2 Template e rastro

- Endpoint de template XLSX gerado em código (padrão `/saldos/template-xlsx`),
  já com a lista de qualificadores do recorte do setor pré-preenchida — o
  setor recebe o arquivo com as rubricas dele e só preenche valores.
- Cada importação confirmada fica rastreável: quem enviou, quando, quantas
  linhas (o preview/confirmação já registra; o snapshot da versão publicada
  congela o resultado).
- Depois de importar, o fluxo é o normal: executar o cenário setorial
  (modelo MANUAL lê os ajustes), revisar, **publicar** — e a versão publicada
  entra na composição do consolidado.

### C.3 Fora de escopo (deliberado)

- Recebimento automático por API/agendador (extração F3.x com destino
  "previsão"): possível depois, sobre o mesmo cenário setorial; começar pelo
  upload manual cobre o fluxo real com fração do custo.
- Workflow de aprovação (setor envia → gestor aprova): a publicação da versão
  já é o ato de aprovação na v1.

---

## Fluxo completo (visão de quem opera)

1. Administrador cadastra os setores e marca os blocos da árvore (herança).
2. Cada setor tem seu cenário setorial; trabalha nele com qualquer modelo do
   catálogo **ou** importa a planilha (Parte C); ao fechar, **publica** uma
   versão.
3. A equipe de programação financeira abre o cenário consolidado, pina as
   versões publicadas de cada setor, roda a consolidação, revisa o relatório
   de cobertura, e publica.
4. O DFC projetado (e qualquer relatório que leia versão publicada) passa a
   enxergar o consolidado — sem nenhuma mudança nos relatórios.

## Ordem de entrega sugerida

| Fase | Entrega | Depende de |
| --- | --- | --- |
| 1 | `flc_setor_previsao` + marcação com herança + tela de setor | — |
| 2 | Cenário setorial (`seq_setor_previsao` no cenário + validação de escopo) | 1 |
| 3 | Cenário consolidado (`cod_tipo_cenario` + composição + mescla com as 3 regras + tela) | 2 |
| 4 | Importação setorial (adapter + template XLSX) | 2 (independe da 3) |

Cada fase com migração Alembic própria, BDD das regras de negócio (conflito,
cobertura, homogeneidade, escopo) e atualização do teste de completude de
permissões.

## Decisões registradas (e os porquês)

- **Compor cenários, não multiplicar configs**: relaxar a unicidade de
  `flc_cenario_config` para (cenário, perna, setor) desfaria a simplificação
  do despacho único por perna, misturaria o trabalho de setores no mesmo
  registro e não daria independência de publicação — um setor não conseguiria
  publicar sem arrastar os demais.
- **Pinar versão, não cenário**: reprodutibilidade do consolidado; versão
  publicada é registro histórico.
- **Conflito é erro, não soma nem precedência**: uma rubrica, um dono.
- **Buraco de cobertura é aviso com confirmação, não zero silencioso.**
- **Homogeneidade de ano/periodicidade na v1**: misturar granularidades sem
  normalização explícita produziria números errados silenciosamente.
- **Importação alimenta o cenário setorial** (ajustes MANUAL), não uma tabela
  paralela de previsão: um só caminho de dados até a versão publicada.
