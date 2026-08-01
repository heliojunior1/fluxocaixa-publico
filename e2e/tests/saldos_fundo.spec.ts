import { expect, test } from '@playwright/test';
import { STORAGE_STATE_ADMIN } from '../consts';

test.use({ storageState: STORAGE_STATE_ADMIN });

test('toggle alterna entre visão agregada e por fundo', async ({ page }) => {
  await page.goto('/saldos-bancarios');
  // default: agregado — coluna Origem visível, sem botão "Novo Saldo"
  await expect(page.getByTestId('visao-agregado')).toBeVisible();
  await expect(page.getByTestId('novo-saldo')).toHaveCount(0);

  await page.getByTestId('visao-fundo').click();
  await expect(page).toHaveURL(/visao=fundo/);
  await expect(page.getByTestId('novo-saldo')).toBeVisible();
});

test('cria um saldo pelo modal na visão por fundo', async ({ page }) => {
  await page.goto('/saldos-bancarios?visao=fundo');
  await page.getByTestId('novo-saldo').click();
  await expect(page.locator('#saldo-modal')).toBeVisible();

  await page.getByTestId('saldo-conta').selectOption({ index: 0 });
  await page.getByTestId('saldo-fundo').selectOption({ index: 0 });
  await page.getByTestId('saldo-data').fill('2025-05-15');
  await page.getByTestId('saldo-valor').fill('4242.42');
  await page.getByTestId('saldo-salvar').click();

  await expect(page).toHaveURL(/visao=fundo/);
  await expect(page.getByText('4,242.42')).toBeVisible();
});

test('edição mantém as chaves somente leitura', async ({ page }) => {
  await page.goto('/saldos-bancarios?visao=fundo');
  const editar = page.getByTestId(/^editar-saldo-/).first();
  await editar.click();
  await expect(page.locator('#saldo-modal')).toBeVisible();
  // conta/fundo/data desabilitados (chaves imutáveis)
  await expect(page.getByTestId('saldo-conta')).toBeDisabled();
  await expect(page.getByTestId('saldo-data')).toBeDisabled();
  await expect(page.getByTestId('saldo-valor')).toBeEnabled();
});
