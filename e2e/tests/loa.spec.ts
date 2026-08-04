import { expect, test } from '@playwright/test';
import { STORAGE_STATE_ADMIN } from '../consts';

// Unicidade da LOA (cadastros-nucleo R24, change loa-unicidade-e-servico-proprio).
// Ilha E2E 2066; valores fictícios. O duplo submit do mesmo formulário deve
// ATUALIZAR o registro, nunca duplicá-lo — duplicata dobraria teto do
// autorizado, metas fiscais e previsto do desembolso.

test.describe('LOA — unicidade por (ano, qualificador)', () => {
  test.use({ storageState: STORAGE_STATE_ADMIN });

  test('submeter duas vezes a mesma chave mantém um único registro', async ({ page }) => {
    await page.goto('/loa');
    await page.getByTestId('loa-ano').fill('2066');
    await page.getByTestId('loa-qualificador').selectOption({ index: 1 });
    await page.getByTestId('loa-valor').fill('1234,56');
    await page.getByTestId('loa-form').getByRole('button', { name: 'Salvar' }).click();
    await expect(page).toHaveURL(/\/loa\?ano=2066/);

    // segunda gravação da MESMA chave, com valor novo
    await page.getByTestId('loa-ano').fill('2066');
    await page.getByTestId('loa-qualificador').selectOption({ index: 1 });
    await page.getByTestId('loa-valor').fill('7890,12');
    await page.getByTestId('loa-form').getByRole('button', { name: 'Salvar' }).click();
    await expect(page).toHaveURL(/\/loa\?ano=2066/);

    // um único registro do ano-ilha, com o valor ATUALIZADO
    const linhas = page.getByTestId('loa-linha').filter({ hasText: '2066' });
    await expect(linhas).toHaveCount(1);
    await expect(linhas.first()).toContainText('7.890,12');
  });
});
