# Auditoria da previsão — 29/09/2026

Revisão do código local no commit `68df129`. Foram examinados cadastro por exercício, séries históricas, modelos, despacho do simulador, marcações por qualificador, backtest e relatórios. Não houve alteração de código funcional nem acesso à base operacional. Os resultados abaixo combinam leitura do código, testes existentes e sondas com dados sintéticos; não constituem medição da acurácia na base real do órgão.

**Parecer:** a identidade histórica das rubricas está bem encaminhada e vários cuidados estatísticos foram implementados corretamente. Entretanto, existem defeitos reproduzidos que impedem considerar a previsão e a recomendação automática de modelos inteiramente corretas.

## 1. Como qualificadores de anos diferentes são ligados

O sistema separa três coisas:

| Campo | Papel |
|---|---|
| `seq_qualificador` | ID de uma linha do cadastro anual |
| `num_ano_exercicio` | Exercício a que essa linha pertence |
| `cod_rubrica_raiz` | Identidade da mesma rubrica ao longo dos exercícios |

`cod_rubrica_raiz` não é o pai da árvore. Exemplo: ICMS de 2024 pode ter ID 100 e ICMS de 2025, ID 200; ambos mantêm a identidade histórica 100.

- A abertura de exercício copia a identidade e remapeia os pais para os novos IDs: `qualificador_service.py:391–459`.
- Uma criação independente recebe identidade própria; uma continuação pode herdar explicitamente a identidade: `qualificador_service.py:294–365`.
- `serie_historica.py:18–44` expande o ID selecionado para todos os IDs da mesma identidade, deduplicando o conjunto agregado.
- Qualificadores inativos continuam contribuindo com seu passado; o filtro de situação ativa incide sobre os lançamentos.
- A série mensal soma os lançamentos com sinal, completa meses fechados sem movimento e exclui o mês em curso. O horizonte prevê os meses intermediários até o ano-base, evitando deslocar a sazonalidade.

**Verificação com banco isolado:** criei uma rubrica em 2024 e outra, com código diferente, em 2025, compartilhando a identidade. Lancei R$ 100 em cada mês de 2024. Consultando o ID de 2025, o motor recuperou 12 pontos, total R$ 1.200, e projetou R$ 100 para janeiro de 2025.

Isso funciona para continuidade da mesma rubrica, inclusive renumeração. Não resolve automaticamente cisão, fusão ou mudança de significado. Para dividir uma rubrica antiga entre duas novas, seria necessário definir correspondências e pesos, ou prever num agregado comparável. A validação atual proíbe duas rubricas ativas com a mesma identidade no mesmo exercício; simplesmente reutilizar essa identidade em ambas não é uma solução.

Marcações de método e recomendações também não são integralmente transportadas para novos exercícios: a documentação declara a reaplicação de marcações por identidade como evolução ainda não implementada (`previsao-metodo-por-qualificador.md:118`); as recomendações são filtradas por ID e exercício em `metodo_qualificador_service.py:1339–1357`.

## 2. Defeitos reproduzidos

### A1 — Alta: cálculo avulso zera a previsão de despesas

**Local:** `src/fluxocaixa/services/modelos_economicos_service.py:809–814`; chamada real da tela em `templates/simulador_criar.html:1387–1412`.

O histórico vem com despesa negativa. O simulador e as marcações convertem a série para magnitude antes do treinamento; `calcular_projecao` não faz isso. O piso de não negatividade do resultado transforma a previsão negativa em zero.

**Reprodução:** histórico de 36 meses com despesa de R$ 100/mês. `calcular_projecao('MEDIA_HISTORICA', ...)` devolveu 12 zeros. `_projetar_perna('D', ...)`, com a mesma série, devolveu R$ 100 em cada mês. O botão de aplicar média histórica utiliza o primeiro caminho.

**Correção:** unificar o contrato de entrada dos motores, aplicando a mesma normalização de sinal nas três portas e validando o tipo de fluxo dos qualificadores selecionados.

### A2 — Alta: LightGBM fica reduzido à média com a janela padrão

**Local:** `modelos_economicos_service.py:610–618`, janela em `:803`, treino em `feature_engineering.py:80–98`.

A janela tem no máximo 36 meses. As 12 defasagens deixam no máximo 24 exemplos para treinamento. O construtor mantém `min_child_samples=20`, padrão da biblioteca, inviabilizando uma divisão em duas folhas nesse treinamento de regressão com pesos uniformes.

**Reprodução com a biblioteca real:** série de 36 meses `100 + 5*t + 50*sin(2*pi*t/12)`. O treino ficou com 24 linhas e 24 atributos. O modelo gerou uma árvore de uma folha e previu exatamente R$ 217,50 em todos os 12 meses, a média dos alvos de treino. Não aprendeu a tendência nem a sazonalidade presentes na série.

**Correção:** adequar janela e complexidade à amostra efetiva; selecionar parâmetros por validação temporal e detectar modelos sem divisões. Apenas reduzir o mínimo de observações por folha pode introduzir sobreajuste e precisa ser avaliado.

O parâmetro padrão e seu significado estão na [documentação oficial do LightGBM](https://lightgbm.readthedocs.io/en/latest/pythonapi/lightgbm.LGBMRegressor.html).

### A3 — Alta: periodicidade do cenário vira quantidade de meses nos modelos da perna

**Local:** `simulador_cenario_service.py:675–677`, `:730–746`.

No caminho padrão por receita/despesa, `num_periodos` é passado diretamente a motores mensais, mesmo quando a periodicidade é quinzenal, semanal ou anual. O tratamento existente no caminho por marcação não corrige automaticamente esse caminho.

**Reprodução:** cenário quinzenal, 24 períodos, ano-base 2026, histórico constante de R$ 100/mês. Foram produzidas 24 datas mensais, de janeiro/2026 a dezembro/2027, totalizando R$ 2.400. O esperado para 24 quinzenas de um ano seria total R$ 1.200 repartido em quinzenas.

**Correção:** calcular o horizonte mensal correspondente às datas do cenário e converter a saída, preservando os totais; ou impedir explicitamente essas combinações até suportá-las.

### A4 — Alta: backtest trata meses não encerrados como realizado zero

**Local:** `backtest_service.py:57–67`. A rota permite selecionar o ano corrente (`web/relatorios.py:476`, `:529–550`).

A série histórica exclui corretamente o mês em curso e os futuros, mas `_obter_real` volta a preencher todos os 12 meses com zeros.

**Reprodução:** realizado disponível de janeiro a agosto, R$ 100/mês; previsão de R$ 100/mês. A função acrescentou quatro zeros e calculou WMAPE de 50% e viés de 50%, embora a previsão seja exata em todos os meses observados. O MAPE ficou em 0%, agravando a inconsistência entre os indicadores.

**Correção:** avaliar somente meses encerrados e com carga completa, ou restringir o backtest anual a exercícios encerrados. Registrar a data de corte.

### A5 — Alta: recomendação por MAPE pode escolher previsão muito pior para o caixa

**Local:** `backtest_service.py:136–146`, `:352–358`.

Excluir denominadores zero evita uma operação indefinida, mas o sistema usa esse MAPE como critério único para escolher o vencedor. Assim, o erro em meses de realizado zero não influencia a recomendação.

**Reprodução:** realizado `[100, 0]`:

| Modelo | Previsão | MAPE usado na seleção | WMAPE | MAE |
|---|---|---:|---:|---:|
| A | `[100, 1000]` | 0% | 1000% | R$ 500 |
| B | `[110, 0]` | 10% | 10% | R$ 5 |

O critério implementado prefere A, apesar de seu erro monetário cem vezes maior. Além disso, quando todos os reais são zero, o retorno descarta até o MAE, que continuaria definido.

**Correção:** escolher uma métrica compatível com séries intermitentes e com o objetivo financeiro, incluindo todos os meses observados; tratar denominadores nulos explicitamente. Comparar os candidatos sobre o mesmo conjunto de anos e rubricas. As limitações das métricas percentuais são discutidas em [Forecasting: Principles and Practice](https://otexts.com/fpp3/accuracy.html).

### A6 — Alta: média de crescimento não conserva o total anual calculado

**Local:** `src/fluxocaixa/services/formula_engine.py:718–734`.

A função calcula o total pela média de `total_anual/acumulado_parcial`, mas distribui os meses futuros pelo perfil sazonal médio de forma independente. O peso médio dos meses já realizados não é, em geral, o inverso da taxa média. Substituir os meses iniciais pelo realizado rompe a soma anual.

**Reprodução:** dois anos de referência com total R$ 1.200, acumulados até junho de R$ 300 e R$ 900. Acumulado atual de R$ 600. A taxa média é `(4 + 1,3333)/2 = 2,6667`; a fórmula define total R$ 1.600. A função emite seis meses de R$ 100 e seis de R$ 133,33: **R$ 1.399,98**. A diferença de aproximadamente R$ 200 não é explicada por arredondamento.

**Correção:** preservar o realizado e repartir o saldo `total_projetado - realizado_acumulado` entre os meses futuros com pesos renormalizados, incluindo tratamento explícito de saldo negativo e ajuste dos centavos.

### A7 — Média: relatório ainda perde a identidade histórica entre exercícios

**Local:** `src/fluxocaixa/services/previsao_service.py:38–51`, `:109`; `repositories/lancamento_repository.py:428`.

O relatório Previsão × Realizado consulta os IDs selecionados diretamente para vários anos. Não expande os IDs pela identidade histórica nem remapeia os resultados para a rubrica selecionada.

**Reprodução com banco isolado:** no exemplo de continuidade de 2024 para 2025 da seção 1, o motor retornou R$ 100 para janeiro. O relatório, sem cenário publicado e usando a base do ano anterior, retornou previsão inicial e final de R$ 0. O defeito afeta também a leitura histórica por esses IDs; a reprodução não demonstra erro em todas as situações com versões publicadas.

**Correção:** costurar o realizado histórico por identidade e mapear para a rubrica exibida, preservando separadamente os valores e a identidade das versões publicadas.

### A8 — Média: período-base é ignorado na média histórica sazonal

**Local:** `modelos_economicos_service.py:706–715`; controle da tela em `templates/simulador_criar.html:625–626`.

`df_recente` respeita `periodo_meses`, mas a média por mês do ano é calculada sobre `df` completo. A sazonalidade vem habilitada no fluxo da tela.

**Reprodução:** 24 meses de R$ 100 seguidos por 12 meses de R$ 300, configurando período-base de 12 meses. A previsão ficou em R$ 166,67/mês, incorporando os três anos, em vez de R$ 300.

**Correção:** aplicar a janela antes da média sazonal, ou separar explicitamente os parâmetros de janela sazonal e janela de nível. O parâmetro atual não cumpre o significado exibido na tela.

### A9 — Média: herança permite misturar receita e despesa

**Local:** `qualificador_service.py:340–364`.

A validação exige identidade existente e ausência de outro ativo no exercício. Não exige compatibilidade da natureza do fluxo.

**Reprodução pelo serviço de cadastro:** uma nova despesa, código `2.99991`, herdou a identidade de uma receita `1.99991` de outro exercício. A expansão histórica passa a unir as duas naturezas. A conversão posterior para magnitude pode esconder o erro.

**Correção:** validar compatibilidade receita/despesa na herança e nas alterações de hierarquia; explicitar que a continuidade semântica da rubrica depende da decisão de cadastro. Para mudanças de natureza, usar uma identidade nova ou um mecanismo de conversão documentado.

## 3. Avaliação dos modelos e do backtest

| Componente | Avaliação |
|---|---|
| Holt-Winters | Chamada real ao statsmodels; exige dois ciclos antes de usar sazonalidade, reverte o deslocamento aplicado para multiplicativo/Box-Cox e informa fallback. Esses cuidados estão corretos. Faltam diagnósticos de convergência e qualidade do ajuste. |
| ARIMA | Implementação real; busca automática varia p/q mantendo d fixo. Não determina automaticamente d, não demonstra adequação dos resíduos e não verifica convergência antes de aceitar o resultado. |
| SARIMA | Implementação real; remove componente sazonal quando faltam dois ciclos. Dois ciclos não garantem estimação robusta de uma configuração complexa. A janela diverge: quatro anos no cálculo avulso e na marcação, três no padrão da perna. |
| XGBoost | Treino e previsão recursiva compartilham a função de atributos. Não encontrei uso do próprio alvo nos atributos examinados. Contudo, 14 meses permitem somente dois exemplos de treino para 24 atributos; isso é um mínimo operacional, não comprovação de suficiência estatística. |
| LightGBM | Mesmo cuidado com atributos, mas a configuração atual sofre do defeito A2. |
| Média histórica | Referência simples útil, comprometida pelos defeitos A1 e A8 nos caminhos indicados. |
| Regressão múltipla | Calcula `alpha + soma(beta*x)` com coeficientes fornecidos pelo usuário. Não estima coeficientes a partir do histórico; deve ser apresentada como equação parametrizada, sem implicar treinamento automático. |
| Crescimento último ano | É reprojeção intra-ano, usando o realizado acumulado do próprio ano. Acertadamente fica separado dos modelos anuais no backtest; depende de um corte de dados válido. |
| Média de crescimento | Tem o defeito aritmético A6 e não participa do catálogo de métodos intra-ano avaliados pelo backtest. |
| LOA | É distribuição de orçamento informado, sem aprendizado estatístico. Não demonstra, por si, o calendário efetivo de pagamentos. |

Outros limites observados na leitura:

- **Convergência:** `_sem_avisos_de_convergencia` suprime avisos e os motores não inspecionam `mle_retvals`. A ausência de exceção não garante ajuste convergente. Três sondas reais de SARIMA, com 24/36/48 pontos, convergiram; portanto, não afirmo que os dados do usuário tenham apresentado não convergência.
- **Fallback no ranking:** `_executar_modelo` descarta `attrs['degradacao']`. Uma previsão produzida pelo ARIMA de fallback pode concorrer rotulada SARIMA.
- **Treino diferente da aplicação:** o backtest usa janela expansiva desde o primeiro ano selecionado e parâmetros padrão; a previsão usa janelas fixas e aceita parâmetros específicos. Uma recomendação é do experimento executado, não uma validação automática de todas essas outras configurações.
- **Coberturas diferentes:** candidatos que falham ou não têm histórico suficiente são omitidos em determinados anos/rubricas. A média de seus erros pode compará-los em conjuntos diferentes.
- **Métricas dos pais:** `_agregar_pais` faz média das métricas das folhas. Isso não mede o erro da série financeira agregada do pai; seria necessário somar previsto e realizado por mês e recalcular. A média de WMAPEs do ranking global também dá o mesmo peso às rubricas, independentemente de seu volume.
- **Incerteza:** os resultados examinados são previsões pontuais. Não há intervalos preditivos nem avaliação de cobertura desses intervalos.
- **Disponibilidade dos dados:** mês fechado sem lançamento vira zero. Esse tratamento só representa a realidade quando a carga está completa; o motor não distingue ausência econômica de falha de ingestão.

A origem móvel do backtest é uma escolha válida, e o código evita usar anos posteriores ao ano-alvo no treino. Para avaliar o uso real, também é preciso reproduzir janela, parâmetros, data de corte e horizonte efetivamente utilizados. Referência: [validação temporal com origem móvel](https://otexts.com/fpp3/tscv.html).

## 4. Evidências e limites da execução

Ambiente local: Python 3.10.20, statsmodels 0.14.6, XGBoost 3.2.0 e LightGBM 4.7.0.

- 39 testes passaram no recorte unitário: modelos econométricos, atributos, série regular, identidade histórica, série histórica e cadastro por exercício.
- 57 testes passaram na execução final do recorte BDD/integração: séries, backtest, despacho, modelos, métodos por qualificador, cadastro por exercício, caracterização da previsão e telas.
- Uma primeira execução combinada apresentou 3 falhas e 15 erros, incluindo erros de banco/fixture em cascata. O módulo de métodos passou isoladamente (13 testes) e a repetição da seleção completa passou (57 testes). A causa da intermitência não foi estabelecida nesta revisão.
- Foram executadas sondas adicionais para os nove defeitos acima. Sinal, periodicidade, média sazonal e métricas usaram dados de entrada controlados; LightGBM foi treinado de fato. A continuidade anual, o relatório e a herança cruzada foram verificados numa cópia descartável da base de testes.
- Os testes existentes não cobrem todos os contraexemplos reproduzidos. Passarem não elimina os achados.
- Não foram executados E2E em navegador nem uma avaliação estatística sobre dados reais. Não foi feita certificação de acurácia futura.

## 5. Ordem sugerida para correção

1. Unificar entrada e saída dos modelos: sinal, janela, periodicidade, metadados de degradação e identificação das rubricas.
2. Corrigir A1, A3 e A6, que alteram diretamente os valores projetados.
3. Corrigir corte temporal e critério de seleção do backtest (A4/A5), usando a mesma política de treino da aplicação.
4. Adequar LightGBM e os mínimos de ML à amostra efetiva; comparar com referências simples em validação temporal.
5. Completar a costura histórica nos relatórios e as validações de herança (A7/A9); corrigir a janela da média (A8).
6. Acrescentar testes dos contraexemplos, diagnósticos de ajuste e rastreabilidade da execução. Depois, medir acurácia por rubrica e por horizonte em uma base real com carga conferida.

## 6. Conferência e destino dos achados

Cada achado foi conferido de novo (leitura do código e sonda descartável) antes de ser corrigido. Change `corrigir-achados-auditoria-previsao`; o A1 já estava corrigido pela change `corrigir-previsao-despesa-e-abertura-exercicio`, que também transporta marcações, fórmulas e setor na abertura de exercício (seção 1).

| Achado | Conferência | Destino |
|---|---|---|
| A1 | Confirmado | Corrigido antes (série de treino em magnitude na origem única) |
| A2 | Confirmado: 217,50 constante, árvore de uma folha | Corrigido: mínimo por folha proporcional à amostra; modelo sem divisão declara a degradação |
| A3 | Confirmado e mais amplo: ANUAL projetava um mês (R$ 100 em vez de R$ 1.200); SEMANAL gerava 52 meses | Corrigido: motores recebem meses, saída convertida para a periodicidade com total preservado |
| A4 | Confirmado | Corrigido: só meses encerrados, data de corte no resultado e na tela |
| A5 | Confirmado | Corrigido: seleção por WMAPE sobre todos os meses (MAE quando o realizado é todo zero) |
| A6 | Confirmado (R$ 1.399,98 × R$ 1.600,00); o crescimento do último ano conservava o total | Corrigido nos dois métodos: saldo repartido pelo perfil renormalizado |
| A7 | Confirmado | Corrigido: realizado e versão publicada costurados pela identidade |
| A8 | Confirmado | Corrigido: período-base informado recorta nível e sazonalidade; sem período-base, janela inteira (chamadores sem configuração) |
| A9 | Confirmado | Corrigido na herança e na troca de pai |
| Fallback no ranking | Procede | Corrigido: degradação registrada e modelo degradado fora da recomendação |
| Coberturas diferentes | Procede | Corrigido: só concorrem candidatos com a mesma cobertura de anos |
| Métricas dos pais / peso no ranking | Procede | Corrigido: pai pela série somada; ranking pelo WMAPE agregado por volume |
| Janela do SARIMA | Procede | Corrigido: tabela única de janelas nas três portas |
| Recomendações por exercício | Procede | Corrigido: tradução pela identidade para o plano do cenário, ordem por WMAPE |
| Convergência, intervalos, carga incompleta, suficiência do XGBoost com 14 meses, rótulo da regressão, média de crescimento no backtest, política de janela do backtest | Procedem | Fora do escopo desta correção (registrados como non-goals da change) |
