import { expect, test } from '@playwright/test';
import { STORAGE_STATE_ADMIN } from '../consts';

// Massa do seed_usuarios_e2e.py (F10.4 — cadastros-nucleo R28):
//   plano-ilha 2078: raiz "1 — Receita Ilha 2078" + folha "1.1 — Rubrica
//   Ilha 2078". O plano corrente (ano do relógio) tem as rubricas KPI
//   (1.8.x). A tela exibe UM exercício por vez.

test.describe('Qualificadores — tela por exercício', () => {
  test.use({ storageState: STORAGE_STATE_ADMIN });

  test('default é o exercício corrente resolvido, não o plano-ilha', async ({ page }) => {
    await page.goto('/qualificadores');
    const combo = page.getByTestId('filtro-exercicio');
    await expect(combo).toBeVisible();
    const anoCorrente = String(new Date().getFullYear());
    await expect(combo).toHaveValue(anoCorrente);
    await expect(page.locator('body')).not.toContainText('Rubrica Ilha 2078');
  });

  test('trocar o exercício troca o plano exibido', async ({ page }) => {
    await page.goto('/qualificadores');
    await page.getByTestId('filtro-exercicio').selectOption('2078');
    await page.waitForLoadState('networkidle');

    await expect(page.getByTestId('filtro-exercicio')).toHaveValue('2078');
    const arvore = page.locator('.qualificador-tree');
    await expect(arvore).toContainText('Receita Ilha 2078');
    // o plano corrente não vaza para a ÁRVORE do exercício 2078 (o select de
    // herança da F10.5 lista candidatas do plano anterior — fora da árvore)
    await expect(arvore).not.toContainText('Rubrica KPI 1.8.1');
  });
});
