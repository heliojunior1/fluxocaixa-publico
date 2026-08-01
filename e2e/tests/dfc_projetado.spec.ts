import { expect, test } from '@playwright/test';
import { STORAGE_STATE_ADMIN } from '../consts';

// Massa do seed_usuarios_e2e.py:
//   qualificador 1.8.3 com lançamento em 2034 (ano no dropdown)
//   cenário "Cenário E2E DFC" com versão publicada "v1 E2E DFC":
//     200,00/mês (R) para 1.8.3 em 2034 — ano futuro, todas as colunas abertas
//   lançamentos realizados de 2031 (seed dos KPIs) para o drill-down realizado
//
// O caminho de fallback "cálculo ao vivo" não é coberto aqui: depende de libs
// de ML opcionais no host (XGBoost/libomp). O BDD cobre o fallback com stub.

async function filtrarAnual(page, ano: string, opts: { cenario?: string } = {}) {
  await page.goto('/relatorios/dfc');
  await page.locator('#dfc-periodo-filter').selectOption('ano');
  await page.locator('select[name="mes_ano"]').selectOption(ano);
  if (opts.cenario) {
    await page.locator('#estrategia').selectOption('projetado');
    await page.locator('#cenario_id').selectOption({ label: opts.cenario });
  }
  await page.getByRole('button', { name: 'Filtrar' }).click();
  await page.waitForLoadState('networkidle');
}

test.describe('DFC — estratégia Projetado', () => {
  test.use({ storageState: STORAGE_STATE_ADMIN });

  test('projetado com versão publicada: destaque, TOTAIS e origem', async ({ page }) => {
    await filtrarAnual(page, '2034', { cenario: 'Cenário E2E DFC' });

    // Origem da versão publicada visível; sem aviso de cálculo ao vivo
    await expect(page.getByTestId('origem-projecao')).toBeVisible();
    await expect(page.getByTestId('origem-projecao')).toContainText('v1 E2E DFC');
    await expect(page.getByTestId('aviso-projecao-ao-vivo')).toHaveCount(0);

    // Layout projetado ganha a coluna TOTAIS
    await expect(page.locator('#dfc-table-head')).toContainText('TOTAIS');

    // Raiz Receita: colunas abertas substituídas pela projeção (200,00/mês)
    const linhaReceita = page
      .locator('#dfc-table-body tr')
      .filter({ has: page.locator('span.number-badge', { hasText: /^1$/ }) })
      .first();
    const celulaJaneiro = linhaReceita.locator('td[data-col="1"]');
    await expect(celulaJaneiro).toContainText('200,00');
    await expect(celulaJaneiro).toHaveAttribute('data-proj', '1');
    // TOTAIS da raiz = 12 × 200,00
    await expect(linhaReceita.locator('td').last()).toContainText('2.400,00');
  });

  test('drill-down de célula realizada continua funcionando', async ({ page }) => {
    await filtrarAnual(page, '2031');

    const linhaReceita = page
      .locator('#dfc-table-body tr')
      .filter({ has: page.locator('span.number-badge', { hasText: /^1$/ }) })
      .first();
    await linhaReceita.locator('td[data-col="7"]').click();

    const modal = page.locator('#modal-eventos');
    await expect(modal).toBeVisible();
    await expect(modal).toContainText('2.000,00'); // lançamento do seed dos KPIs
  });

  test('drill-down de célula projetada informa a origem', async ({ page }) => {
    await filtrarAnual(page, '2034', { cenario: 'Cenário E2E DFC' });

    const linhaReceita = page
      .locator('#dfc-table-body tr')
      .filter({ has: page.locator('span.number-badge', { hasText: /^1$/ }) })
      .first();
    await linhaReceita.locator('td[data-col="1"]').click();

    const modal = page.locator('#modal-eventos');
    await expect(modal).toBeVisible();
    await expect(modal).toContainText('Projeção do cenário');
    await expect(modal).toContainText('v1 E2E DFC');
  });
});
