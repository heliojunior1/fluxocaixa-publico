# Previsão por qualificador — método por rubrica, cópia de cenário e propostas setoriais

> Documento de regras (concepção). Complementa e, no ponto A.4, **substitui**
> `docs/previsao-setorial-consolidacao.md`: a consolidação deixa de ser um tipo
> de cenário à parte e passa a ser um **método** atribuído a um nó da árvore.
> Protótipo navegável: `docs/prototipos/previsao-por-qualificador.html`.
>
> **Implementado** (change `previsao-por-qualificador`, migração `0039`) — as
> seis fases da seção 8. Código: `services/metodo_qualificador_service.py`
> (marcação, resolução, motor, cobertura, recomendações),
> `services/setor_previsao_service.py` (setores, recorte, propostas),
> `web/previsao_qualificador.py` + `templates/simulador_metodos.html`,
> `setores_previsao.html`, `propostas_setoriais.html`. BDD:
> `src/tests/features/previsao/metodo_por_qualificador.feature`.

## 1. Contexto — o que limita a projeção hoje

| # | Situação atual | Onde | Efeito |
|---|---|---|---|
| P1 | Um modelo por **perna** (receita/despesa). `flc_cenario_config` é único por (cenário, perna) | `simulador_cenario_service._projetar_perna` | Não dá para ter ICMS por SARIMA, IPVA por fórmula e taxas por valor fixo no mesmo cenário |
| P2 | Modelos de série (HW, ARIMA, SARIMA, XGBoost, LightGBM, média histórica, LOA) projetam o **agregado** dos qualificadores escolhidos, sem `seq_qualificador` | idem; `detalhada = None` | A projeção não chega às rubricas (ver seção 6 — relatórios zerados ou fora do veredicto) |
| P3 | Folha sem método **some em silêncio** (FORMULA ignora folha sem fórmula; MANUAL só projeta o que tem ajuste) | `formula_engine.projetar_cenario_formula`, `_executar_cenario_manual` | "Não projetei" é indistinguível de "projetei zero" |
| P4 | Fórmula é **global por qualificador** (`flc_rubrica_formula.seq_qualificador` único); só os valores de parâmetro são por cenário | `models/formula.py` | Mudar a fórmula num cenário muda todos os cenários |
| P5 | Método da base (média simples/ponderada, anos, pesos) é **um só por cenário**; o `cod_metodo_base` da fórmula existe mas é ignorado | `projetar_cenario_formula` | Rubricas com comportamentos diferentes forçadas à mesma base |
| P6 | Não existe **cópia de cenário** | `web/simulador_cenarios.py` | Testar uma variante exige recriar o cenário do zero |
| P7 | Recomendação do backtest é gravada mas **nada a consome** | `backtest_service.salvar_recomendacoes` | O melhor modelo por rubrica não chega ao cenário |
| P8 | Relatórios leem a projeção por **caminhos diferentes** (publicada × ao vivo × ajustes do snapshot) | seção 6 | O mesmo cenário mostra números diferentes em relatórios diferentes |

## 2. Princípios

1. **Um cenário pode projetar TODOS os qualificadores sozinho.** O modo setorial é
   uma forma a mais de alimentar o cenário — nunca obrigatório. Quem quiser opera
   tudo num cenário só, misturando métodos por rubrica.
2. **Cada folha termina com exatamente um método resolvido** — nem zero (lacuna
   silenciosa) nem dois (dupla contagem).
3. **Herança pela árvore, mais próximo vence** — o mesmo padrão de
   `categoria_fiscal_service.categoria_resolvida`. Marca-se o bloco; exceções
   ficam nas folhas.
4. **A saída é sempre por folha.** Todo método entrega linhas
   (folha, perna, ano, período). Os relatórios não precisam saber qual método
   gerou o número.
5. **Cenários são independentes.** Editar um cenário (inclusive uma cópia) nunca
   altera outro. Versão publicada é registro histórico e nunca se reescreve.
6. **Compatibilidade**: cenário sem nenhuma marcação se comporta como hoje — a
   configuração da perna vira o "método padrão" da raiz.

## 3. Conceitos

| Termo | Definição |
|---|---|
| **Cenário** | `flc_simulador_cenario` — ano-base, periodicidade, nº de períodos |
| **Método padrão da perna** | A config atual (`flc_cenario_config`). Vale para toda folha da perna que não herde outra marcação |
| **Marcação de método** | Registro (cenário, qualificador, método, configuração). Pode ficar em **qualquer nó** — bloco ou folha |
| **Método resolvido** | O método efetivo de uma folha: marcação própria → do ancestral mais próximo → padrão da perna. **Derivado, nunca persistido** |
| **Nó de cálculo** | O nó onde a marcação está. Métodos de série treinam nele e distribuem às folhas |
| **Cobertura** | Conferência de que toda folha relevante recebeu projeção |
| **Proposta setorial** | Versão publicada de um cenário setorial, oferecida para compor outro cenário |

## 4. Regras de negócio

### A. Método por qualificador

**RN01 — Método padrão.** Todo cenário mantém um método padrão por perna (a
config atual). Pode ser "Sem padrão": então toda folha precisa de marcação
explícita ou vira lacuna (RN12).

**RN02 — Marcação em qualquer nó.** A marcação pode ficar em nó com filhos (é o
propósito: marcar o bloco). Não exige folha — mesma exceção deliberada da
categoria fiscal.

**RN03 — Resolução.** `marcacao_resolvida(folha, marcacoes)` é a **origem única** da
resposta "qual método projeta esta folha?" (mesmo estatuto de `is_folha()`,
`valor_com_sinal`, `periodo_resolver`). Sobe pela cadeia de pais com conjunto de
visitados (guarda de ciclo). A tela mostra o método **e se é próprio ou herdado**.

**RN04 — Catálogo de métodos.**

| Método | Perna | Grão de cálculo | Configuração |
|---|---|---|---|
| `VALOR_FIXO` | C e D | folha ou bloco | Valor **anual** (distribuído pelo perfil sazonal) ou **12 valores mensais** |
| `PERCENTUAL` | C e D | folha ou bloco | % sobre o realizado do ano anterior **ou** da média de N anos |
| `FORMULA` | C e D | folha | Expressão (biblioteca ou própria do cenário — RN18) + base (método, anos, pesos) |
| `MODELO` | C (econométricos); C e D (média histórica e crescimento) | nó marcado | Tipo (HW, ARIMA, SARIMA, XGBoost, LightGBM, média histórica, crescimento), janela de treino |
| `LOA` | D | folha ou bloco | Ano da LOA; perfil do realizado para distribuir |
| `PROPOSTA_SETORIAL` | C e D | bloco | Versão publicada fixada (RN24–RN29) |
| `SEM_PROJECAO` | C e D | folha ou bloco | Motivo obrigatório. Zero **declarado** — não é lacuna |

Método incompatível com a perna é `RegraNegocioError` (recupera a garantia do
`CATALOGO_MODELOS` de hoje).

**RN05 — Métodos de série treinam no nó marcado e distribuem.** Um `MODELO`
marcado no bloco "Transferências" treina a série do bloco (soma das folhas
descendentes, costurada por raiz via `seqs_da_rubrica`) e o total projetado de
cada período é **distribuído às folhas pela participação histórica** (padrão:
último ano fechado; configurável: média de N anos). Folha sem histórico recebe
participação zero e aparece no relatório de cobertura como "sem participação".
Opção por marcação: *treinar em cada folha* (um modelo por folha, mínimo de 12
pontos; abaixo disso a folha cai para a sugestão de prever no pai — F10.5).

**RN06 — Subárvore com marcação própria sai do nó de cálculo.** Se o bloco
"Receita tributária" está em SARIMA e a folha "IPVA" tem `PROPOSTA_SETORIAL`, a
série de treino do bloco **exclui** IPVA e a distribuição também. Sem isso IPVA
seria projetado duas vezes.

**RN07 — Valor fixo.** Anual: distribuído pelo perfil sazonal do realizado
(fallback 1/12, como no DFC anual). Mensal: em quinzenal/semanal o valor do mês
é rateado pela quota de períodos do mês (mesmo mecanismo do R15 de hoje).
Valor sempre em **magnitude positiva** — o sinal vem da perna (R6).

**RN08 — Fórmula sem parâmetro nunca é silenciosa.** No padrão FORMULA da
perna, parâmetro faltante levanta `RegraNegocioError` citando a variável (regra
vigente). Numa MARCAÇÃO, a folha vira lacuna com a nota da variável faltante —
as demais rubricas seguem projetadas, e a lacuna aparece na cobertura e exige
confirmação para publicar.

**RN09 — Exercício.** Marcações usam o plano do exercício resolvido para o
ano-base (`resolver_exercicio_do_plano`). *Evolução (não implementada):*
reaplicar as marcações por raiz (`cod_rubrica_raiz`) ao abrir novo exercício.

**RN10 — Recomendação do backtest.** A tela oferece "Aplicar recomendações":
pré-preenche marcações `MODELO` nas folhas/blocos com o modelo de menor erro.
É **sugestão** — gravar é decisão humana (padrão da repartição por fonte).

### B. Cobertura

**RN11 — Relatório de cobertura a cada execução.** Lista, por perna:
folhas com método resolvido, folhas **sem projeção** que tiveram movimento nos
últimos N anos (lacunas), folhas `SEM_PROJECAO` (declaradas) e folhas sem
participação histórica em nó de cálculo.

**RN12 — Lacuna não é zero.** Publicar versão com lacuna exige
`confirmado=true`; as lacunas ficam gravadas no `json_resumo` da versão. Os
relatórios que exibem projeção mostram o aviso "N rubricas sem projeção".

**RN13 — Soma de controle.** Para cada nó de cálculo, a soma distribuída às
folhas é igual ao total projetado no nó (diferença de arredondamento vai à
folha de maior participação).

### C. Contrato com os relatórios

**RN14 — Saída única por folha.** Toda execução produz linhas
`(seq_qualificador folha, cod_tipo, ano, num_periodo, val_projetado, cod_metodo, seq_qualificador_calculo)`.
**Não existe mais linha com `seq_qualificador` nulo.** `cod_metodo` e o nó de
cálculo vão para `flc_projecao_valor` (auditoria: "de onde veio este número?").

**RN15 — Uma porta de leitura.** Todo relatório lê a projeção por
`resolver_projecao` (última versão **publicada** → execução ao vivo com aviso).
Nenhum relatório chama `executar_simulacao` direto nem lê ajustes do snapshot.

**RN16 — Origem visível.** Todo relatório com projeção exibe cenário, versão
(ou "ao vivo — não publicada") e o aviso de lacunas (RN12).

**RN17 — Sem regressão.** Cenário sem marcação produz os **mesmos números** por
folha que hoje para MANUAL/FORMULA/CRESCIMENTO. Para modelos agregados, o
**total** é o mesmo e passa a ser distribuído (antes caía na linha "não
distribuída"). A rede de caracterização (golden) prova isso.

### D. Cópia de cenário

**RN18 — Fórmula própria do cenário.** O cenário usa a fórmula da biblioteca
(`flc_rubrica_formula`) **por referência**. Editar a fórmula **dentro do
cenário** cria uma fórmula própria do cenário e nunca altera a biblioteca.
Alterar a biblioteca exibe os cenários afetados (os que a usam por referência)
antes de gravar. Versões publicadas nunca mudam.

**RN19 — Duplicar cenário.** Cópia profunda numa transação única:
cabeçalho, método padrão das pernas, marcações, ajustes, valores de parâmetro,
fórmulas próprias, parâmetros econômicos. **Não copia versões** (a cópia nasce
sem histórico). Registra `seq_cenario_origem` e o autor. Nome obrigatório e
diferente dos cenários ativos. Permissão `FC_INS_PREVISAO`.

**RN20 — Opção "congelar fórmulas".** Ao duplicar, o usuário pode transformar
todas as fórmulas por referência em fórmulas próprias da cópia — blindagem total
contra mudança futura da biblioteca.

**RN21 — Independência.** Após a cópia, nada mutável é compartilhado: editar
original ou cópia nunca afeta o outro. Compartilhados apenas: a árvore de
qualificadores, o realizado, a biblioteca de fórmulas (por referência, RN18) e a
**definição** dos parâmetros globais (os valores são por cenário).

**RN22 — Comparar.** Qualquer par de cenários (ou versões) pode ser comparado
por folha, bloco e período — especialmente origem × cópia.

### E. Propostas setoriais (opcional)

**RN23 — Setor é opcional.** Cenário **sem setor** pode marcar qualquer nó e
projetar a árvore inteira. Setor existe para quando a instituição quer
distribuir o trabalho.

**RN24 — Recorte do setor.** `flc_setor_previsao` + marcação do setor na árvore
com herança (padrão da categoria fiscal). Cenário setorial só marca/ajusta nós
do seu recorte (fora = `RegraNegocioError`).

**RN25 — Entrada da proposta.** O setor projeta no seu cenário com qualquer
método **ou importa planilha** (upload → preview → confirmar; planilha-modelo
CSV `codigo;descricao;mes;valor` com as folhas do recorte), que grava
`VALOR_FIXO` mensal PRÓPRIO em cada folha. Linha de bloco, de fora do recorte,
mês repetido ou valor negativo é erro no preview; mês ausente vale zero (aviso).
A importação serve a qualquer cenário, setorial ou não.

**RN26 — Situação da proposta.** Rascunho → **Enviada** (versão publicada) →
**Aceita** / **Devolvida** (motivo obrigatório). Devolvida volta a rascunho no
cenário setorial; o histórico fica.

**RN27 — Uso no cenário consumidor.** Qualquer cenário (inclusive o que projeta
todo o resto sozinho) marca um nó com `PROPOSTA_SETORIAL` **fixando a versão**
(`seq_projecao_versao`). Nova versão do setor **não** altera o consumidor até a
troca explícita do pin — a tela avisa "há versão mais nova".

**RN28 — Conflito.** A mesma folha não pode vir de duas propostas (erro citando
folha e cenários). Linhas da proposta **fora** da subárvore marcada são
ignoradas e listadas como aviso.

**RN29 — Homogeneidade.** Proposta com ano-base ou periodicidade diferente do
consumidor é recusada na v1 (normalização é evolução).

### F. Permissões e auditoria

| Permissão | Uso |
|---|---|
| `FC_CONS/INS/ALT/DEL_PREVISAO` | Vigentes — cenário, marcações, fórmula própria, importação (ALT), duplicar (INS) |
| `FC_MANT_SETOR_PREVISAO` | Cadastro de setores e recorte na árvore |
| `FC_AVALIAR_PROPOSTA` | Aceitar/devolver proposta |

Enviar a proposta é **publicar** a versão do cenário setorial (`FC_ALT_PREVISAO`,
como qualquer publicação) — não ganhou permissão própria. Devolver exige motivo
e é **recusado enquanto algum cenário fixa a versão** (o consumidor perderia os
números em silêncio; troque a versão fixada antes).

Toda marcação registra autor e data de inclusão/alteração; a versão publicada
congela as marcações no `json_inputs`.

## 5. Modelo de dados (proposta)

| Objeto | Mudança |
|---|---|
| `flc_cenario_metodo` (nova) | `seq_cenario_metodo`, `seq_simulador_cenario`, `seq_qualificador`, `cod_tipo_lancamento`, `cod_metodo`, `json_configuracao`, `ind_treinar_por_folha`, auditoria. Único (cenário, qualificador) entre ativos |
| `flc_cenario_formula` (nova) | Fórmula própria do cenário: (cenário, qualificador, expressão, método da base, config da base) |
| `flc_cenario_config` | Mantida — passa a ser o **método padrão da perna**; `cod_tipo_modelo` aceita `SEM_PADRAO` |
| `flc_cenario_ajuste` | Mantida — valores do `VALOR_FIXO` mensal e do MANUAL legado |
| `flc_simulador_cenario` | + `seq_cenario_origem` (FK nullable), + `seq_setor_previsao` (FK nullable) |
| `flc_projecao_valor` | + `cod_metodo`, + `seq_qualificador_calculo`; `seq_qualificador` passa a ser sempre preenchido em versão nova |
| `flc_projecao_versao` | + `cod_situacao_proposta` (R/E/A/D), + `dsc_motivo_devolucao` |
| `flc_setor_previsao` (nova) | Domínio cadastrável (nome, sigla, status, auditoria) |
| `flc_qualificador` | + `seq_setor_previsao` (FK nullable — marcação própria; resolvido por herança) |

Cada fase com migração Alembic própria (anti-deriva).

## 6. Relatórios que usam a projeção

| Relatório | Como lê hoje | Problema hoje | Depois |
|---|---|---|---|
| **DFC projetado** | `resolver_projecao` (publicada → ao vivo) | Modelo agregado cai na linha sintética "não distribuída" | Distribuído nas folhas; drill-down mostra o método |
| **Simulação de disponibilidade (desembolso)** | `resolver_projecao` | Receita agregada (`seq` nulo) vai ao grupo **N** → fica **fora do veredicto prudente** | Por folha → repartida por fonte (F9.3) e entra no veredicto |
| **Previsão de receita** | `executar_simulacao` ao vivo, usa `projecao_receita_detalhada` | Modelo econométrico tem `detalhada = None` → **previsão zero** | `resolver_projecao`; sempre por folha |
| **Controle de despesa** | `executar_simulacao` ao vivo, `projecao_despesa_detalhada` | Idem — MEDIA_HISTORICA/LOA zeram a previsão | `resolver_projecao` |
| **Resumo do fluxo** | `executar_simulacao` ao vivo, agregado | Ignora versão publicada — número muda sem publicar | `resolver_projecao` |
| **Previsão × realizado** | Ajustes do snapshot inicial/final | Só enxerga MANUAL | Lê `flc_projecao_valor` das versões |
| **Comparativo de versões** | `flc_projecao_valor` | — | Ganha comparação entre cenários (RN22) |

## 7. Telas (ver protótipo)

0. **Formulário do cenário (criar/editar)** — escolha "Um método para cada
   perna" (como antes) ou **"Escolher o método por qualificador"**: a árvore
   aparece no próprio formulário, com o método e o parâmetro de cada linha e a
   herança exibida ao vivo; ao salvar, cenário e marcações gravam numa
   transação única (marcação inválida desfaz tudo, citando a rubrica). Métodos
   que o formulário não expressa (valores mês a mês, proposta setorial, treino
   por folha) aparecem como "manter" e são ajustados na tela de métodos.
1. **Cenários** — lista com origem (cópia de…), setor, última versão; ação **Duplicar**.
2. **Métodos por qualificador** — árvore com método resolvido por nó (próprio ×
   herdado), painel de edição do nó, cobertura ao vivo.
3. **Cobertura** — lacunas, declaradas, sem participação; publicar com confirmação.
4. **Propostas setoriais** — situação por setor, versão fixada, "há versão mais nova".
5. **Resultado e relatórios** — projeção por folha com método e o impacto nos relatórios.

## 8. Ordem de entrega

| Fase | Entrega | Depende |
|---|---|---|
| 1 | Porta única de leitura (RN15/RN16) + saída sempre por folha para os modelos agregados (RN05/RN14) | — |
| 2 | Duplicar cenário + fórmula própria do cenário (RN18–RN21) | — |
| 3 | Marcação de método com herança + cobertura (RN01–RN13) | 1 |
| 4 | Aplicar recomendação do backtest (RN10) | 3 |
| 5 | Setor, cenário setorial e importação (RN23–RN26) | 3 |
| 6 | Método `PROPOSTA_SETORIAL` com pin, conflito e homogeneidade (RN27–RN29) | 5 |

A fase 1 vem primeiro porque corrige relatórios que hoje mostram zero ou deixam
receita fora do veredicto — e tudo que vem depois escreve na mesma saída.

## 9. Decisões e porquês

- **Marcação por nó com herança, não uma config por folha**: marcar folha a
  folha troca erro automático por erro manual (esquecer uma folha entre
  quarenta). Mesma lição da categoria fiscal.
- **Consolidação como método, não como tipo de cenário** (revisa o A.4 do doc
  setorial): permite o cenário **misto** — IPVA da proposta do setor, ICMS por
  SARIMA, taxas por valor fixo — com um mecanismo só.
- **Distribuir, não deixar agregado**: sem qualificador a receita não reparte
  por fonte e cai no grupo N; o agregado é o motivo de três relatórios errados.
- **Fórmula por referência + própria do cenário**, não cópia sempre: preserva a
  biblioteca como padrão e dá independência quando o usuário pede.
- **Lacuna exige confirmação, não bloqueio**: há casos legítimos (rubrica
  extinta); o que não pode é ser silencioso.

## 10. Notas da implementação

- **Compatibilidade**: cenário sem marcação não passa pelo motor novo —
  `executar_simulacao` segue idêntico, com duas correções que valem para todos:
  (1) os modelos AGREGADOS da configuração da perna (Holt-Winters, ARIMA,
  SARIMA, XGBoost, LightGBM, média histórica, crescimento) passam a sair
  distribuídos pelos qualificadores do modelo (`distribuir_projecao_agregada`),
  preservando o total por período; (2) o LOA legado passa a ser datado pelo
  ano-base (usava `date.today()` e a golden quebrava a cada mês). A golden de
  previsão foi regenerada só por esses dois motivos (docstring de
  `src/tests/caracterizacao_previsao.py`). LOA e regressão legados, sem
  qualificador na configuração, seguem agregados — use o método LOA por
  qualificador.
- **Série de um qualificador**: a configuração com `seq_qualificadores` de UM
  elemento treinava sobre série vazia (o código só lia `seq_qualificador`);
  corrigido.
- **Cobertura calculada a pedido** na tela (`?cobertura=1`): exige executar o
  cenário, e abrir a página não treina modelos (R14). Na publicação ela é
  sempre calculada e gravada no `json_resumo` (`lacunas`,
  `rubricas_sem_projecao`).
- **Folha relevante para lacuna** = folha ativa do plano do exercício do
  cenário com realizado nos três anos anteriores ao ano-base (ou com método
  declarado). Folha sem histórico e sem método não é lacuna.
- **Modelos na marcação** usam o catálogo de pernas do simulador
  (econométricos só em receita; crescimento nas duas), com uma exceção
  deliberada: **média histórica vale nas duas pernas** na marcação. O backtest
  a avalia e a recomenda para receita (no seed, ganhou em 3 de 4 rubricas), e
  com a restrição "só despesa" a melhor recomendação sumia em silêncio de
  "Aplicar recomendações". A restrição segue valendo para a configuração da
  perna (spec R2). Treinam 12 meses e a série é emitida na periodicidade do cenário
  (quinzenal/semanal rateiam o mês).
