import { test, expect } from '@playwright/test';
import { STORAGE_STATE_ADMIN } from '../consts';

test.use({ storageState: STORAGE_STATE_ADMIN });

test('fórmulas de receita e despesa mostram vínculos e preservam parâmetros', async ({ page }) => {
  const erros: string[] = [];
  page.on('pageerror', erro => erros.push(erro.message));
  await page.goto('/simulador/novo');
  const csrf = await page.locator('meta[name="csrf-token"]').getAttribute('content');
  const headers = { 'X-CSRF-Token': csrf! };
  for (const [tipo, codigo] of [['receita', '1.987.65'], ['despesa', '2.987.65']]) {
    const qualificador = await page.request.post('/qualificadores/add', {
      headers, maxRedirects: 0,
      form: { num_qualificador: codigo, dsc_qualificador: `Fórmula E2E ${tipo}` },
    });
    expect(qualificador.status()).toBe(303);
    await page.goto('/formulas');
    const seq = await page.locator('#select_qualificador option')
      .filter({ hasText: `Fórmula E2E ${tipo}` }).getAttribute('value');
    const formula = await page.request.post('/formulas/criar', {
      headers, maxRedirects: 0,
      form: {
        seq_qualificador: seq!, nom_formula: `Projeção E2E ${tipo}`,
        dsc_formula_expressao: tipo === 'receita'
          ? 'base * (1 + taxa_formula_e2e)'
          : 'base * (1 + taxa_formula_e2e) + acrescimo_formula_e2e',
      },
    });
    expect(formula.status()).toBe(303);
  }

  await page.goto('/simulador/novo');
  await page.locator('#cod_periodicidade').selectOption('ANUAL');
  await page.locator('#tipo_receita').selectOption('ARIMA');
  await page.locator('#tipo_despesa').selectOption('FORMULA');
  await expect(page.locator('#receita_model_fields')).toBeVisible();
  await expect(page.locator('#formula_despesa')).toBeVisible();
  await expect(page.locator('#formula_despesa')).toContainText('2.987.65');
  await expect(page.locator('#formula_despesa')).toContainText('base * (1 + taxa_formula_e2e) + acrescimo_formula_e2e');
  await expect(page.locator('#formula_receita')).toBeHidden();
  const taxa = page.locator('[name="formula_param_taxa_formula_e2e"]');
  const acrescimo = page.locator('[name="formula_param_acrescimo_formula_e2e"]');
  await taxa.fill('0.05');
  await acrescimo.fill('20');
  await page.locator('#tipo_receita').selectOption('FORMULA');
  await expect(page.locator('#formula_receita')).toContainText('1.987.65');
  await expect(taxa).toHaveCount(1);
  await expect(taxa).toHaveValue('0.05');
  await page.locator('#tipo_despesa').selectOption('MANUAL');
  await expect(acrescimo).toBeDisabled();
  await expect(acrescimo).toBeHidden();
  await page.locator('#tipo_despesa').selectOption('FORMULA');
  await expect(acrescimo).toHaveValue('20');
  await page.locator('[name="nom_cenario"]').fill('Cenário de fórmulas E2E');
  await page.locator('label').filter({
    has: page.locator('[name="cod_metodo_base"][value="VALOR_FIXO"]'),
  }).click();
  await page.locator('[name="valor_fixo_cenario"]').fill('100');
  await page.getByRole('button', { name: 'Salvar Cenário', exact: true }).click();
  await expect(page).toHaveURL(/\/simulador\/\d+$/);
  await page.goto(`${page.url()}/editar`);
  await expect(page.locator('#formula_despesa')).toBeVisible();
  await expect(taxa).toHaveValue('0.050000');
  await expect(acrescimo).toHaveValue('20.000000');
  expect(erros).toEqual([]);
});
