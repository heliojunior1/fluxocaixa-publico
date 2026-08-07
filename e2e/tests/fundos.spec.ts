import { expect, test } from '@playwright/test';
import { STORAGE_STATE_ADMIN, STORAGE_STATE_CONSULTA } from '../consts';

test.describe('gestão de fundos (admin)', () => {
  test.use({ storageState: STORAGE_STATE_ADMIN });

  test('cadastra um fundo pelo modal', async ({ page }) => {
    await page.goto('/fundos');
    await page.getByTestId('novo-fundo').click();
    await expect(page.locator('#fundo-modal')).toBeVisible();
    await page.getByTestId('fundo-cod').fill('8001');
    await page.getByTestId('fundo-dsc').fill('FUNDO E2E CADASTRADO');
    await page.getByTestId('fundo-salvar').click();

    await expect(page).toHaveURL(/\/fundos/);
    await expect(page.getByText('FUNDO E2E CADASTRADO')).toBeVisible();
  });

  test('cadastra um CDB com carência e vencimento pelo modal', async ({ page }) => {
    await page.goto('/fundos');
    await page.getByTestId('novo-fundo').click();
    await expect(page.locator('#fundo-modal')).toBeVisible();
    await page.getByTestId('fundo-cod').fill('8002');
    await page.getByTestId('fundo-dsc').fill('CDB E2E COM CARENCIA');
    await page.getByTestId('fundo-tipo').selectOption({ label: 'CDB — Certificado de Depósito Bancário' });
    await page.getByTestId('fundo-liquidez').selectOption('N');
    await page.getByTestId('fundo-venc').fill('2048-12-31');
    await page.getByTestId('fundo-salvar').click();

    await expect(page).toHaveURL(/\/fundos/);
    await expect(page.getByTestId('tipo-instrumento-8002')).toContainText('CDB');
    await expect(page.getByTestId('badge-carencia-8002')).toBeVisible();
  });

  test('filtra a lista pelo tipo de instrumento', async ({ page }) => {
    await page.goto('/fundos');
    // Seed: CDBE2E (CDB) e FIE2E (FUNDO) coexistem sem filtro
    await expect(page.getByTestId('tipo-instrumento-CDBE2E')).toBeVisible();
    await expect(page.getByTestId('tipo-instrumento-FIE2E')).toBeVisible();

    await page.getByTestId('filtro-tipo-instrumento').selectOption({ label: 'CDB' });
    await page.getByRole('button', { name: 'Filtrar' }).click();

    await expect(page.getByTestId('tipo-instrumento-CDBE2E')).toBeVisible();
    await expect(page.getByTestId('tipo-instrumento-FIE2E')).toHaveCount(0);
  });

  test('aprova o fundo pendente e a badge some', async ({ page }) => {
    await page.goto('/fundos');
    // Badge no menu visível (há pelo menos o fundo 9911 pendente do seed)
    await expect(page.getByTestId('badge-fundos-pendentes')).toBeVisible();
    await expect(page.getByTestId('badge-pendente-9911')).toBeVisible();

    await page.getByTestId('aprovar-fundo-9911').click();
    await expect(page.locator('#aprovar-modal')).toBeVisible();
    await page.getByTestId('aprovar-confirmar').click();

    await expect(page).toHaveURL(/\/fundos/);
    await expect(page.getByTestId('badge-pendente-9911')).toHaveCount(0);
  });
});

test.describe('gestão de fundos (CONSULTA)', () => {
  test.use({ storageState: STORAGE_STATE_CONSULTA });

  test('vê a lista sem ações e sem contador no menu', async ({ page }) => {
    await page.goto('/fundos');
    await expect(page.getByRole('heading', { name: 'Aplicações/Fundos' })).toBeVisible();
    await expect(page.getByTestId('novo-fundo')).toHaveCount(0);
    await expect(page.getByTestId('badge-fundos-pendentes')).toHaveCount(0);
  });
});
