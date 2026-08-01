import { expect, Page, test } from '@playwright/test';
import { STORAGE_STATE_ADMIN, STORAGE_STATE_CONSULTA } from '../consts';

// Semeado por seed_usuarios_e2e.py: sistema SIS_E2E, 3 linhas de staging
// (2 com natureza 1112xxxx, 1 com 2222xxxx — tudo fictício) e o mapeamento
// "Mapeamento E2E Receita" com a regra "Natureza começa com '1112'".
const MAPEAMENTO_E2E = 'Mapeamento E2E Receita';

async function processarAgora(page: Page) {
  await page.goto('/mapeamentos/execucoes');
  await page.getByTestId('mapeamento-alvo').selectOption({ label: MAPEAMENTO_E2E });
  await page.getByTestId('processar-mapeamento').click();
}

test.describe('processamento de mapeamentos (admin)', () => {
  test.use({ storageState: STORAGE_STATE_ADMIN });

  test('processa a staging e registra a execução com os contadores', async ({ page }) => {
    await processarAgora(page);

    const tabela = page.getByTestId('tabela-execucoes-mapeamento');
    await expect(tabela).toContainText(MAPEAMENTO_E2E);
    await expect(tabela).toContainText('MANUAL');
    // 2 das 3 linhas casam com "Natureza começa com '1112'"
    await expect(tabela.locator('tr').nth(1)).toContainText('2');
  });

  test('reprocessar não duplica: a segunda execução não gera nada', async ({ page }) => {
    await processarAgora(page);   // 1ª: gera
    await processarAgora(page);   // 2ª: as linhas já não estão pendentes

    // a execução mais recente (1ª linha da tabela) fica sem dados a processar
    const primeira = page.getByTestId('tabela-execucoes-mapeamento').locator('tr').nth(1);
    await expect(primeira).toContainText('SEM_DADOS');
  });
});

test.describe('processamento de mapeamentos (consulta)', () => {
  test.use({ storageState: STORAGE_STATE_CONSULTA });

  test('não vê a ação de processar', async ({ page }) => {
    await page.goto('/mapeamentos/execucoes');
    await expect(page.getByTestId('tabela-execucoes-mapeamento')).toBeVisible();
    await expect(page.getByTestId('processar-mapeamento')).toHaveCount(0);
  });
});
