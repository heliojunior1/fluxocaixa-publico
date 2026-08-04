import { expect, test } from '@playwright/test';
import { STORAGE_STATE_ADMIN } from '../consts';

// F10.3 (cadastros-nucleo R29): fluxo completo da abertura de exercício pela
// tela. Massa do seed: plano-ilha 2078 ("Receita Ilha 2078" + "Rubrica Ilha
// 2078") — a abertura copia 2078 → 2087 (ilha exclusiva deste spec; o teste
// é idempotente porque a segunda abertura seria recusada, então o assert
// final aceita o plano já existente de uma rodada anterior).

test.describe('Qualificadores — abertura de exercício', () => {
  test.use({ storageState: STORAGE_STATE_ADMIN });

  test('abrir exercício copia o plano e navega para o novo', async ({ page }) => {
    await page.goto('/qualificadores?exercicio=2078');

    await page.getByTestId('abrir-exercicio').click();
    const form = page.getByTestId('abrir-exercicio-form');
    await expect(form).toBeVisible();

    await form.locator('#exercicio_novo').fill('2087');
    await page.getByTestId('confirmar-abertura').click();
    await page.waitForLoadState('networkidle');

    if (page.url().includes('exercicio=2087')) {
      // primeira rodada: abertura feita, tela já está no exercício novo
      await expect(page.getByTestId('filtro-exercicio')).toHaveValue('2087');
      await expect(page.locator('body')).toContainText('Rubrica Ilha 2078');
    } else {
      // rodada repetida: a segunda abertura é recusada (A.5) com flash de
      // negócio — e o plano de 2087 continua acessível pelo combo
      await expect(page.getByTestId('flash-erro')).toContainText('já possui');
      await page.goto('/qualificadores?exercicio=2087');
      await expect(page.locator('body')).toContainText('Rubrica Ilha 2078');
    }
  });
});
