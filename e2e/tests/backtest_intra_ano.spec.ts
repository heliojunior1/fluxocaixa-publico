import { expect, test } from '@playwright/test';
import { STORAGE_STATE_ADMIN } from '../consts';

// Massa do seed_usuarios_e2e.py (change corrigir-motores-de-previsao, R16):
//   "Folha backtest E2E" (1.989.1) com 100,00/mês em 2082 e 150,00/mês em 2083.
// O crescimento é reprojeção intra-ano: aparece no bloco próprio e nunca como
// "Melhor". MEDIA_HISTORICA e CRESCIMENTO_ANO não dependem de libs de ML.

test.describe('Backtest — reprojeção intra-ano fora do ranking', () => {
  test.use({ storageState: STORAGE_STATE_ADMIN });

  test('crescimento aparece no bloco intra-ano e não é o melhor modelo', async ({ page }) => {
    await page.goto('/relatorios/backtest');

    for (const cb of await page.locator('.ano-treino-cb').all()) await cb.uncheck();
    for (const cb of await page.locator('.ano-teste-cb').all()) await cb.uncheck();
    await page.locator('.ano-treino-cb[value="2082"]').check();
    await page.locator('.ano-teste-cb[value="2083"]').check();

    for (const cb of await page.locator('.modelo-cb').all()) await cb.uncheck();
    await page.locator('.modelo-cb[value="MEDIA_HISTORICA"]').check();
    await page.locator('.modelo-cb[value="CRESCIMENTO_ANO"]').check();
    await page.getByTestId('backtest-mes-referencia').fill('6');

    await page.getByRole('button', { name: 'Desmarcar Todos' }).click();
    await page.locator('label', { hasText: 'Folha backtest E2E' }).locator('.qual-cb').check();

    await page.locator('#btn-executar').click();

    const intra = page.getByTestId('backtest-intra-ano');
    await expect(intra).toBeVisible();
    await expect(intra.getByTestId('intra-ano-linha')).toHaveCount(1);
    await expect(intra).toContainText('Folha backtest E2E');
    await expect(intra).toContainText('7–12');

    const ranking = page.locator('#ranking-tabela');
    await expect(ranking).toContainText('Média Histórica');
    await expect(ranking).not.toContainText('Crescimento');
  });
});
