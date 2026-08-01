import { expect, test } from '@playwright/test';
import { STORAGE_STATE_ADMIN } from '../consts';

// Massa do seed_usuarios_e2e.py (mesma dos KPIs, ilha 2031-07, fundo 9902):
//   conta 001/0001/KPI-1: saldo 900.00 em 10/07/2031 e 1000.00 em 15/07/2031
//   conta 104/0001/KPI-2: saldo 500.00 em 15/07/2031

test.describe('relatório de saldos diários — modos agregado e por fundo', () => {
  test.use({ storageState: STORAGE_STATE_ADMIN });

  test('alternar modos mantém os totais coerentes', async ({ page }) => {
    await page.goto('/relatorios/saldos-diarios?visao=agregado&data_ref=2031-07-15');

    // Modo agregado: saldo inicial derivado + registrado do dia
    await expect(page.getByTestId('tabela-agregado')).toBeVisible();
    const linha = page.getByTestId('linha-conta-001-KPI-1');
    await expect(linha).toContainText('900.00'); // inicial derivado de 10/07
    await expect(linha).toContainText('1,000.00'); // saldo registrado do dia
    await expect(page.getByTestId('total-saldo-registrado')).toContainText('1,500.00');

    // Alterna para o modo por fundo: total coincide com o agregado
    await page.getByTestId('visao-fundo').click();
    await expect(page.getByTestId('tabela-fundo')).toBeVisible();
    await expect(page.getByTestId('total-saldo-fundo')).toContainText('1,500.00');
    // Coluna de rendimento presente no modo por fundo
    await expect(page.getByTestId('tabela-fundo')).toContainText('Rendimento');
  });

  test('filtro por conta restringe as linhas e os totais', async ({ page }) => {
    await page.goto('/relatorios/saldos-diarios?visao=agregado&data_ref=2031-07-15');

    await page.getByTestId('filtro-conta').selectOption({ label: '001/0001/KPI-1' });
    await page.getByRole('button', { name: 'Filtrar' }).click();

    await expect(page.getByTestId('linha-conta-001-KPI-1')).toBeVisible();
    await expect(page.getByTestId('linha-conta-104-KPI-2')).toHaveCount(0);
    await expect(page.getByTestId('total-saldo-registrado')).toContainText('1,000.00');
  });
});
