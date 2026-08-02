import { expect, test } from '@playwright/test';
import { STORAGE_STATE_ADMIN } from '../consts';

// Ilha 2049 — dotações do funil orçamentário (F8.1)
test.describe('dotações e créditos (admin)', () => {
  test.use({ storageState: STORAGE_STATE_ADMIN });

  test('cria dotação, registra crédito e a atualizada deriva', async ({ page }) => {
    await page.goto('/orcamento/dotacoes?ano=2049');
    await page.getByTestId('dotacao-qualificador').selectOption({ index: 0 });
    await page.getByTestId('dotacao-valor').fill('1234.56');
    await page.getByTestId('dotacao-salvar').click();
    await expect(page.locator('[data-testid^="atualizada-"]').first()).toContainText('1,234.56');

    await page.getByTestId('credito-dotacao').selectOption({ index: 0 });
    await page.getByTestId('credito-tipo').selectOption('S');
    await page.getByTestId('credito-valor').fill('100.00');
    await page.getByTestId('credito-data').fill('2049-02-01');
    await page.getByTestId('credito-ato').fill('Lei fictícia 123/2049');
    await page.getByTestId('credito-salvar').click();
    await expect(page.locator('[data-testid^="atualizada-"]').first()).toContainText('1,334.56');
  });
});

// Ilha 2051 — funil E/L/P (F8.2)
test.describe('execução orçamentária (admin)', () => {
  test.use({ storageState: STORAGE_STATE_ADMIN });

  test('exibe o funil do ano com os quatro números', async ({ page }) => {
    await page.goto('/orcamento/execucao?ano=2051');
    await expect(page.getByTestId('funil-empenhado')).toBeVisible();
    await expect(page.getByTestId('funil-liquidado')).toBeVisible();
    await expect(page.getByTestId('funil-pago')).toBeVisible();
    await expect(page.getByTestId('funil-liquidado-nao-pago')).toBeVisible();
  });
});

// Ilha 2055 — relatório do funil + conciliação (F8.3)
test.describe('funil LOA→caixa (admin)', () => {
  test.use({ storageState: STORAGE_STATE_ADMIN });

  test('exibe o relatório do funil e a conciliação', async ({ page }) => {
    await page.goto('/orcamento/funil?ano=2055');
    await expect(page.getByTestId('funil-relatorio')).toBeVisible();
    await expect(page.getByTestId('funil-conciliacao')).toBeVisible();
  });
});
