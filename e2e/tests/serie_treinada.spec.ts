import { expect, test } from '@playwright/test';
import { STORAGE_STATE_ADMIN } from '../consts';

// Massa do seed_usuarios_e2e.py (F10.2 — previsao R17):
//   "Cenário E2E Série": despesa MEDIA_HISTORICA sobre 2.8.1, SEM versão
//   publicada — abrir a página executa ao vivo e o resultado declara o treino
//   (1 mês, ano 2031 — o lançamento "Saída 500,00" do seed dos KPIs).
// MEDIA_HISTORICA é puro (sem libs de ML) — roda em qualquer host do E2E.

test.describe('Simulador — série treinada declarada', () => {
  test.use({ storageState: STORAGE_STATE_ADMIN });

  test('execução ao vivo exibe o bloco com pontos e anos da série', async ({ page }) => {
    await page.goto('/simulador');
    await page
      .locator('tr', { hasText: 'Cenário E2E Série' })
      .getByRole('link')
      .first()
      .click();
    await page.waitForLoadState('networkidle');

    const bloco = page.getByTestId('info-serie-treinada');
    await expect(bloco).toBeVisible();
    await expect(bloco).toContainText('Despesa');
    await expect(bloco).toContainText('1 mês(es)');
    await expect(bloco).toContainText('2031');
    // F10.5 (R30): série curta (< 12 meses) sugere prever no nível do pai
    await expect(page.getByTestId('sugestao-prever-no-pai')).toBeVisible();
  });

  test('versão publicada não declara treino (bloco ausente)', async ({ page }) => {
    // "Cenário E2E DFC" tem versão publicada — a página serve a versão e não
    // reexecuta modelos, logo não há série treinada a declarar.
    await page.goto('/simulador');
    await page
      .locator('tr', { hasText: 'Cenário E2E DFC' })
      .getByRole('link')
      .first()
      .click();
    await page.waitForLoadState('networkidle');

    await expect(page.getByTestId('origem-versao')).toBeVisible();
    await expect(page.getByTestId('info-serie-treinada')).toHaveCount(0);
  });
});
