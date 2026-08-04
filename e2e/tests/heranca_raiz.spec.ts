import { expect, test } from '@playwright/test';
import { STORAGE_STATE_ADMIN } from '../consts';

// F10.5 (cadastros-nucleo R30): herança da identidade estável pela tela.
// Massa do seed: plano-ilha 2078; o exercício anterior resolvido de 2078 é o
// plano corrente (rubricas KPI 1.8.x) — candidatas do select "herdar-raiz".

test.describe('Qualificadores — herdar identidade de rubrica', () => {
  test.use({ storageState: STORAGE_STATE_ADMIN });

  test('criação no exercício 2078 herdando rubrica do plano corrente', async ({ page }) => {
    await page.goto('/qualificadores?exercicio=2078');
    await page.getByTestId('novo-qualificador').click();

    const select = page.getByTestId('herdar-raiz');
    await expect(select).toBeVisible();
    // primeira candidata depois de "Não" — o rótulo carrega o ano corrente,
    // que muda com o relógio; a escolha em si é o que o teste prova
    await select.selectOption({ index: 1 });

    await page.locator('#num_qualificador').fill('1.2');
    await page.locator('#dsc_qualificador').fill('Rubrica Herdada E2E');
    await page.getByRole('button', { name: 'Salvar' }).click();
    await page.waitForLoadState('networkidle');

    // volta para a tela; a rubrica criada aparece no plano de 2078
    await page.goto('/qualificadores?exercicio=2078');
    await expect(page.locator('body')).toContainText('Rubrica Herdada E2E');
  });
});
