import { expect, test } from '@playwright/test';
import { STORAGE_STATE_ADMIN } from '../consts';

test.use({ storageState: STORAGE_STATE_ADMIN });

test('import de saldos passa por preview e grava só as linhas válidas', async ({ page }) => {
  await page.goto('/saldos-bancarios');

  // CSV de transição: 1 linha ok (conta E2E existente) + 1 erro (conta inexistente)
  const csv = [
    'Data;Conta;Valor',
    '2025-08-01;104/0001/E2E-1;123456.78',
    '2025-08-01;999/9999/NAO-EX;5000',
  ].join('\n');

  await page.locator('[data-testid="importar-saldos"] input[type=file]').setInputFiles({
    name: 'saldos.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from(csv),
  });
  await page.locator('[data-testid="importar-saldos"] button[type=submit]').click();

  // Preview: 1 ok, 1 erro
  await expect(page.getByTestId('preview-total-ok')).toContainText('1');
  await expect(page.getByTestId('preview-total-erro')).toContainText('1');
  await expect(page.getByTestId('preview-linha-2')).toContainText('Erro');

  // Confirmar → grava só a válida e volta à listagem, com flash do resumo
  await page.getByTestId('preview-confirmar').click();
  await expect(page).toHaveURL(/\/saldos-bancarios/);
  await expect(page.getByTestId('flash-erro')).toContainText('1 registro');
});

test('cancelar o preview não grava nada', async ({ page }) => {
  await page.goto('/saldos-bancarios');
  const csv = 'Data;Conta;Valor\n2025-08-02;104/0001/E2E-1;999.99';
  await page.locator('[data-testid="importar-saldos"] input[type=file]').setInputFiles({
    name: 'saldos.csv', mimeType: 'text/csv', buffer: Buffer.from(csv),
  });
  await page.locator('[data-testid="importar-saldos"] button[type=submit]').click();

  await expect(page.getByTestId('preview-confirmar')).toBeVisible();
  await page.getByTestId('preview-cancelar').click();
  await expect(page).toHaveURL(/\/saldos-bancarios/);
});
