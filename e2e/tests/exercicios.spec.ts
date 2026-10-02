import { expect, test } from '@playwright/test';
import { STORAGE_STATE_ADMIN } from '../consts';

// Massa do seed_usuarios_e2e.py (change exercicio-aberto-fechado,
// cadastros-nucleo R31): plano-ilha 2131. O bloqueio de escrita do exercício
// fechado (lançamento, plano, mapeamento) é coberto pelo BDD; aqui, o fluxo da
// tela: fechar exige confirmação, fecha com motivo, reabre e o histórico
// registra os dois gestos. Idempotente: em nova tentativa, reabre antes.

test.describe('Exercícios — fechar e reabrir', () => {
  test.use({ storageState: STORAGE_STATE_ADMIN });

  test('fechar exige confirmação; fechar e reabrir ficam no histórico', async ({ page }) => {
    await page.goto('/exercicios');
    const cartao = page.getByTestId('exercicio-2131');
    await expect(cartao).toBeVisible();

    if ((await page.getByTestId('situacao-2131').textContent())?.includes('Fechado')) {
      await page.getByTestId('form-reabrir-2131').locator('input[name="motivo"]').fill('Retentativa E2E');
      await page.getByTestId('btn-reabrir-2131').click();
      await page.waitForLoadState('networkidle');
    }
    await expect(page.getByTestId('situacao-2131')).toHaveText('Aberto');

    // sem confirmar: recusa com mensagem de negócio
    const fechar = page.getByTestId('form-fechar-2131');
    await fechar.locator('input[name="motivo"]').fill('Encerramento E2E');
    await page.getByTestId('btn-fechar-2131').click();
    await page.waitForLoadState('networkidle');
    await expect(page.getByTestId('flash-erro')).toContainText('confirme');
    await expect(page.getByTestId('situacao-2131')).toHaveText('Aberto');

    // com confirmação: fecha
    await page.getByTestId('form-fechar-2131').locator('input[name="motivo"]').fill('Encerramento E2E');
    await page.getByTestId('confirmar-fechar-2131').check();
    await page.getByTestId('btn-fechar-2131').click();
    await page.waitForLoadState('networkidle');
    await expect(page.getByTestId('situacao-2131')).toHaveText('Fechado');
    await expect(page.getByTestId('historico-2131')).toContainText('FECHAMENTO');

    // reabre com motivo
    await page.getByTestId('form-reabrir-2131').locator('input[name="motivo"]').fill('Ajuste tardio E2E');
    await page.getByTestId('btn-reabrir-2131').click();
    await page.waitForLoadState('networkidle');
    await expect(page.getByTestId('situacao-2131')).toHaveText('Aberto');
    await expect(page.getByTestId('historico-2131')).toContainText('REABERTURA');
  });

  test('menu de Cadastros leva à tela', async ({ page }) => {
    await page.goto('/');
    await page.getByTestId('menu-exercicios').click();
    await expect(page.getByTestId('tela-exercicios')).toBeVisible();
  });
});
