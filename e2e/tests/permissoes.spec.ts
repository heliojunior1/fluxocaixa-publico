import { expect, test } from '@playwright/test';
import { STORAGE_STATE_ADMIN, STORAGE_STATE_CONSULTA } from '../consts';

test.describe('perfil CONSULTA (somente leitura)', () => {
  test.use({ storageState: STORAGE_STATE_CONSULTA });

  test('não vê o botão de novo lançamento nem a importação', async ({ page }) => {
    await page.goto('/saldos');
    await expect(page.getByTestId('novo-lancamento')).toHaveCount(0);
    await expect(page.getByTestId('importar-lancamentos')).toHaveCount(0);
  });

  test('acesso direto a URL restrita mostra a página 403', async ({ page }) => {
    await page.goto('/simulador/novo');
    await expect(page.getByTestId('pagina-403')).toBeVisible();
    await expect(page.getByTestId('permissao-necessaria')).toHaveText('FC_INS_PREVISAO');
  });
});

test.describe('perfil ADMINISTRADOR (acesso total)', () => {
  test.use({ storageState: STORAGE_STATE_ADMIN });

  test('vê o botão de novo lançamento e a importação', async ({ page }) => {
    await page.goto('/saldos');
    await expect(page.getByTestId('novo-lancamento')).toBeVisible();
    await expect(page.getByTestId('importar-lancamentos')).toBeVisible();
  });
});
