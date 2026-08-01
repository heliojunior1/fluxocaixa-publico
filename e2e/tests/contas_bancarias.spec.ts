import { expect, test } from '@playwright/test';
import { STORAGE_STATE_ADMIN, STORAGE_STATE_CONSULTA } from '../consts';

// Dados sempre fictícios (repositório público): banco 001/237, agência 0001,
// contas no padrão 12345-6.

test.describe('gestão de contas bancárias (admin)', () => {
  test.use({ storageState: STORAGE_STATE_ADMIN });

  test('cadastra uma conta pelo modal e a vê na lista', async ({ page }) => {
    await page.goto('/contas-bancarias');
    await page.getByTestId('nova-conta').click();
    await expect(page.locator('#conta-modal')).toBeVisible();
    await page.getByTestId('conta-cod-banco').fill('001');
    await page.getByTestId('conta-num-agencia').fill('0001');
    await page.getByTestId('conta-num-conta').fill('E2E-90');
    await page.getByTestId('conta-dsc').fill('Conta E2E Cadastrada');
    await page.getByTestId('conta-salvar').click();

    await expect(page).toHaveURL(/\/contas-bancarias/);
    await expect(page.getByText('Conta E2E Cadastrada')).toBeVisible();
  });

  test('filtra pelo número da conta', async ({ page }) => {
    await page.goto('/contas-bancarias');
    await page.getByTestId('filtro-conta').fill('E2E-1');
    await page.getByRole('button', { name: 'Filtrar' }).click();

    await expect(page.getByText('Conta E2E', { exact: true })).toBeVisible();
    await expect(page.getByText('Conta E2E Inativa')).toHaveCount(0);
  });

  test('inativa uma conta e ela some da listagem default', async ({ page }) => {
    // Conta própria deste teste, sem vínculos — cadastrada aqui mesmo
    await page.goto('/contas-bancarias');
    await page.getByTestId('nova-conta').click();
    await page.getByTestId('conta-cod-banco').fill('001');
    await page.getByTestId('conta-num-agencia').fill('0001');
    await page.getByTestId('conta-num-conta').fill('E2E-91');
    await page.getByTestId('conta-dsc').fill('Conta E2E Para Inativar');
    await page.getByTestId('conta-salvar').click();
    await expect(page.getByText('Conta E2E Para Inativar')).toBeVisible();

    const linha = page.locator('tr', { hasText: 'Conta E2E Para Inativar' });
    page.once('dialog', (dialog) => dialog.accept());
    await linha.locator('[data-testid^="inativar-conta-"]').click();

    await expect(page).toHaveURL(/\/contas-bancarias/);
    await expect(page.getByText('Conta E2E Para Inativar')).toHaveCount(0);
  });

  test('reativa a conta inativa do seed pelo filtro Todas', async ({ page }) => {
    await page.goto('/contas-bancarias?status=todas');
    const linha = page.locator('tr', { hasText: 'Conta E2E Inativa' });
    await expect(linha).toBeVisible();

    await linha.locator('[data-testid^="reativar-conta-"]').click();

    await expect(page).toHaveURL(/status=todas/);
    const linhaDepois = page.locator('tr', { hasText: 'Conta E2E Inativa' });
    await expect(linhaDepois.getByText('Ativa', { exact: true })).toBeVisible();
  });
});

test.describe('gestão de contas bancárias (CONSULTA)', () => {
  test.use({ storageState: STORAGE_STATE_CONSULTA });

  test('vê a lista sem botões de ação', async ({ page }) => {
    await page.goto('/contas-bancarias');
    await expect(page.getByRole('heading', { name: 'Contas Bancárias' })).toBeVisible();
    await expect(page.getByTestId('nova-conta')).toHaveCount(0);
    await expect(page.locator('[data-testid^="inativar-conta-"]')).toHaveCount(0);
    await expect(page.locator('[data-testid^="editar-conta-"]')).toHaveCount(0);
  });
});
