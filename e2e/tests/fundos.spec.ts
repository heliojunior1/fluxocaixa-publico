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
    await expect(page.getByRole('heading', { name: 'Fundos de Investimento' })).toBeVisible();
    await expect(page.getByTestId('novo-fundo')).toHaveCount(0);
    await expect(page.getByTestId('badge-fundos-pendentes')).toHaveCount(0);
  });
});
