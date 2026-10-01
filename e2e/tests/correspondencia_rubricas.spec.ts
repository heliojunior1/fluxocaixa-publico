import { expect, test } from '@playwright/test';
import { STORAGE_STATE_ADMIN } from '../consts';

// Massa do seed_usuarios_e2e.py (change correspondencia-rubricas-entre-
// exercicios, previsao R30–R32): origem "1.988.1" no plano 2095; destinos
// "1.988.2" (300,00) e "1.988.3" (700,00) no plano 2096. O banco do E2E é
// descartável a cada execução; em nova tentativa (retry) a correspondência
// já existe e o cadastro é pulado.

test.describe('De/Para de rubricas entre exercícios', () => {
  test.use({ storageState: STORAGE_STATE_ADMIN });

  test('desdobramento nasce pendente com sugestão e passa a rateio', async ({ page }) => {
    await page.goto('/previsao/correspondencias');
    await expect(page.getByTestId('tela-correspondencias')).toBeVisible();

    const cartao = page.locator('[data-testid^="correspondencia-"]', {
      hasText: 'Origem De/Para E2E',
    });
    if ((await cartao.count()) === 0) {
      const form = page.getByTestId('form-correspondencia');
      await form.locator('#c-tipo').selectOption('D');
      await form.locator('#c-vigencia').fill('2096');
      await form.locator('#c-origens').fill('1.988.1');
      await form.locator('#c-destinos').fill('1.988.2, 1.988.3');
      await form.locator('#c-ato').fill('Portaria fictícia 1/2096');
      await form.locator('#c-fundamento').fill('Desdobramento da rubrica no exercício');
      await page.getByTestId('btn-criar-correspondencia').click();
      await page.waitForLoadState('networkidle');
    }

    await expect(cartao).toHaveCount(1);
    await expect(cartao.locator('[data-testid^="modo-"]')).toHaveText('Distribuição pendente');
    // sugestão pelo realizado dos destinos desde a vigência — não gravada
    await expect(cartao.getByTestId('pct-1.988.2')).toHaveValue('30.0000');
    await expect(cartao.getByTestId('pct-1.988.3')).toHaveValue('70.0000');

    await cartao.locator('[data-testid^="fundamento-rateio-"]').fill('Proporção observada em 2096');
    await cartao.locator('[data-testid^="btn-rateio-"]').click();
    await page.waitForLoadState('networkidle');

    await expect(cartao.locator('[data-testid^="modo-"]')).toHaveText('Rateio (estimado)');
    await expect(cartao).toContainText('30.0000%');
    await expect(cartao).toContainText('70.0000%');
  });

  test('menu de Previsão leva à tela', async ({ page }) => {
    await page.goto('/');
    await page.getByTestId('menu-correspondencias').click();
    await expect(page.getByTestId('tela-correspondencias')).toBeVisible();
  });
});
