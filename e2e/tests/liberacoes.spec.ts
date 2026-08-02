import { expect, test } from '@playwright/test';
import { STORAGE_STATE_ADMIN, STORAGE_STATE_CONSULTA } from '../consts';

test.describe('liberações do desembolso (admin)', () => {
  test.use({ storageState: STORAGE_STATE_ADMIN });

  test('cria rascunho pelo modal, confirma e o pendente reage', async ({ page }) => {
    // semana isolada (ilha 2038-08) para os totais não colidirem com outros specs
    await page.goto('/liberacoes?ref=2038-08-04');
    await expect(page.getByTestId('kpi-pendente')).toBeVisible();

    await page.getByTestId('nova-liberacao').click();
    await expect(page.locator('#liberacao-modal')).toBeVisible();
    await page.getByTestId('liberacao-data').fill('2038-08-04');
    await page.getByTestId('liberacao-valor').fill('1234.56');
    await page.getByTestId('liberacao-orgao').selectOption({ index: 0 });
    await page.getByTestId('liberacao-qualificador').selectOption({ index: 0 });
    // fonte obrigatória e SEM default
    const fonte = page.getByTestId('liberacao-fonte');
    await expect(fonte).toHaveValue('');
    const valorFonte = await fonte.locator('option:nth-child(2)').getAttribute('value');
    await fonte.selectOption(valorFonte!);
    await page.getByTestId('liberacao-salvar').click();

    // nasce rascunho na visão da semana
    await expect(page).toHaveURL(/\/liberacoes/);
    const badgeRascunho = page.locator('[data-testid^="badge-rascunho-"]').first();
    await expect(badgeRascunho).toBeVisible();
    const seq = (await badgeRascunho.getAttribute('data-testid'))!.replace('badge-rascunho-', '');

    // confirma — evento + badge muda
    await page.getByTestId(`confirmar-${seq}`).click();
    await expect(page.getByTestId(`badge-confirmada-${seq}`)).toBeVisible();
    await expect(page.getByTestId('total-semana')).toContainText('1');
  });

  test('apropria um pagamento numa liberação e estorna', async ({ page }) => {
    // 1. liberação confirmada (semana isolada 2038-09-28)
    await page.goto('/liberacoes?ref=2038-09-30');
    await page.getByTestId('nova-liberacao').click();
    await page.getByTestId('liberacao-data').fill('2038-09-30');
    await page.getByTestId('liberacao-valor').fill('1000.00');
    await page.getByTestId('liberacao-orgao').selectOption('70001');
    await page.getByTestId('liberacao-qualificador').selectOption({ label: '2.8.9 · Custeio E2E Liberável' });
    const fonteLib = page.getByTestId('liberacao-fonte');
    const valorFonte = await fonteLib.locator('option:nth-child(2)').getAttribute('value');
    await fonteLib.selectOption(valorFonte!);
    await page.getByTestId('liberacao-salvar').click();
    const badge = page.locator('[data-testid^="badge-rascunho-"]').first();
    const seqLib = (await badge.getAttribute('data-testid'))!.replace('badge-rascunho-', '');
    await page.getByTestId(`confirmar-${seqLib}`).click();
    await expect(page.getByTestId(`badge-confirmada-${seqLib}`)).toBeVisible();

    // 2. pagamento do mesmo órgão/qualificador
    await page.goto('/pagamentos');
    await page.locator('input[name="dat_pagamento"]').fill('2038-09-30');
    await page.locator('select[name="cod_orgao"]').selectOption('70001');
    await page.getByTestId('pagamento-qualificador').selectOption({ label: '2.8.9 - Custeio E2E Liberável' });
    await page.locator('input[name="val_pagamento"]').fill('300.00');
    await page.locator('form[action*="pagamentos/add"] button[type="submit"]').click();

    // 3. vincular → apropriar 300 na candidata
    const semAprop = page.locator('[data-testid^="badge-sem-apropriacao-"]').first();
    await expect(semAprop).toBeVisible();
    const seqPag = (await semAprop.getAttribute('data-testid'))!.replace('badge-sem-apropriacao-', '');
    await page.getByTestId(`vincular-${seqPag}`).click();
    await page.getByTestId(`valor-${seqLib}`).fill('300.00');
    await page.getByTestId('apropriar-salvar').click();
    await expect(page.getByTestId('total-apropriado')).toContainText('300.00');

    // 4. estorno devolve
    const estornar = page.locator('[data-testid^="estornar-"]').first();
    await estornar.click();
    await expect(page.getByTestId('total-apropriado')).toContainText('0.00');
  });

  test('cadastra um órgão pela tela', async ({ page }) => {
    await page.goto('/orgaos');
    await page.getByTestId('novo-orgao').click();
    await page.getByTestId('orgao-cod').fill('123456');
    await page.getByTestId('orgao-nom').fill('Secretaria E2E de Teste');
    await page.getByTestId('orgao-salvar').click();
    await expect(page.getByText('Secretaria E2E de Teste')).toBeVisible();
  });
});

test.describe('simulação de disponibilidade (admin)', () => {
  test.use({ storageState: STORAGE_STATE_ADMIN });

  test('executa a simulação e vê veredicto, curva e não classificado', async ({ page }) => {
    await page.goto('/simulacao-desembolso');
    await page.getByTestId('sim-cenario').selectOption({ label: 'Cenário E2E DFC' });
    await page.locator('input[name="ano"]').fill('2034');
    await page.locator('input[name="mes"]').fill('1');
    await page.getByTestId('sim-executar').click();

    // veredicto presente (qualquer estado) + curva + não classificado visível
    await expect(page.locator('[data-testid^="veredicto-"]')).toBeVisible();
    await expect(page.getByTestId('saldo-mes-1')).toBeVisible();
    // a receita do cenário E2E não tem repartição → aparece como não classificada
    await expect(page.getByTestId('nao-classificado')).not.toContainText('0,00');
  });
});

test.describe('conferência e transferências (admin)', () => {
  test.use({ storageState: STORAGE_STATE_ADMIN });

  test('conferência exibe as três visões com saldos rotulados', async ({ page }) => {
    await page.goto('/conferencia');
    await expect(page.getByTestId('visao-controle')).toBeVisible();
    await expect(page.getByTestId('visao-financeira')).toBeVisible();
    await expect(page.getByTestId('visao-conciliacao')).toBeVisible();
    await expect(page.getByText('saldo de CONTROLE — não é caixa')).toBeVisible();
    await expect(page.getByText('saldo BANCÁRIO', { exact: true })).toBeVisible();
  });

  test('registra uma transferência interna pela tela', async ({ page }) => {
    await page.goto('/transferencias');
    await page.getByTestId('transf-data').fill('2041-03-10');
    await page.getByTestId('transf-origem').selectOption({ index: 0 });
    await page.getByTestId('transf-destino').selectOption({ index: 1 });
    await page.getByTestId('transf-valor').fill('1234.56');
    await page.getByTestId('transf-salvar').click();
    await expect(page.locator('[data-testid^="transferencia-"]').first()).toBeVisible();
  });
});

test.describe('programação de desembolso (admin)', () => {
  test.use({ storageState: STORAGE_STATE_ADMIN });

  test('registra uma cota do decreto e a visão anual reage', async ({ page }) => {
    await page.goto('/desembolso/programacao?ano=2046');
    await page.getByTestId('cota-mes').fill('3');
    await page.getByTestId('cota-orgao').selectOption('70001');
    await page.getByTestId('cota-valor').fill('1234.56');
    await page.getByTestId('cota-ato').fill('Decreto fictício 001/2046');
    await page.getByTestId('cota-salvar').click();
    await expect(page.getByTestId('prog-70001-cota')).toContainText('1,234.56');
  });
});

// Ilha 2060 — painel analítico do desembolso (F7.6)
test.describe('painel analítico do desembolso (admin)', () => {
  test.use({ storageState: STORAGE_STATE_ADMIN });

  test('card no hub e os três blocos visíveis', async ({ page }) => {
    await page.goto('/relatorios');
    await page.getByTestId('card-rel-analitico-desembolso').click();
    await page.goto('/relatorios/analitico-desembolso?ano=2060');
    await expect(page.getByTestId('analitico-por-orgao')).toBeVisible();
    await expect(page.getByTestId('analitico-composicao')).toBeVisible();
    await expect(page.getByTestId('analitico-evolucao')).toBeVisible();
  });
});

test.describe('liberações (CONSULTA)', () => {
  test.use({ storageState: STORAGE_STATE_CONSULTA });

  test('vê a visão semanal sem ações de manutenção', async ({ page }) => {
    await page.goto('/liberacoes');
    await expect(page.getByTestId('kpi-pendente')).toBeVisible();
    await expect(page.getByTestId('kpi-previsto')).toBeVisible();  // previsto da LOA (F7.3a)
    await expect(page.getByTestId('kpi-devido')).toBeVisible();    // liquidado não pago (F8.4)
    await expect(page.getByTestId('nova-liberacao')).toHaveCount(0);
  });
});
