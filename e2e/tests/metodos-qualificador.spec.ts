import { test, expect } from '@playwright/test';
import { STORAGE_STATE_ADMIN } from '../consts';

test.use({ storageState: STORAGE_STATE_ADMIN });

// Previsão por qualificador (docs/previsao-metodo-por-qualificador.md):
// marcar o bloco, a folha herda; cobertura a pedido; duplicar o cenário.
// Massa: seed_usuarios_e2e.py ("Cenário métodos E2E", bloco 1.986.60).
test('métodos por qualificador: marca o bloco, herda na folha, cobre e duplica', async ({ page }) => {
  const erros: string[] = [];
  page.on('pageerror', erro => erros.push(erro.message));

  await page.goto('/simulador');
  const linha = page.locator('tr', { hasText: 'Cenário métodos E2E' });
  await linha.locator('a[title^="Métodos por qualificador"]').click();
  await expect(page.getByTestId('tela-metodos')).toBeVisible();

  await page.getByTestId('no-1.986.60').locator('a').click();
  await expect(page.getByTestId('painel-no')).toBeVisible();
  await page.locator('#f-metodo').selectOption('VALOR_FIXO');
  await expect(page.locator('#f-valor')).toBeVisible();
  await page.locator('#f-valor').fill('1200');
  await page.getByTestId('salvar-metodo').click();

  await expect(page.getByTestId('no-1.986.60')).toHaveAttribute('data-origem', 'PROPRIA');
  await expect(page.getByTestId('no-1.986.60.1')).toHaveAttribute('data-origem', 'HERDADA');
  await expect(page.getByTestId('no-1.986.60.1')).toHaveAttribute('data-metodo', 'VALOR_FIXO');
  await expect(page.getByTestId('no-1.986.60.1')).toContainText('herdado de 1.986.60');

  await page.getByTestId('btn-cobertura').click();
  await expect(page.getByTestId('painel-cobertura')).toBeVisible();

  await page.getByTestId('duplicar').locator('summary').click();
  await page.locator('#dup-nome').fill('Cenário métodos E2E — cópia');
  await page.getByRole('button', { name: 'Criar cópia' }).click();
  await expect(page).toHaveURL(/\/simulador\/\d+\/metodos$/);
  await expect(page.getByTestId('origem-copia')).toContainText('Cenário métodos E2E');
  await expect(page.getByTestId('no-1.986.60.1')).toHaveAttribute('data-metodo', 'VALOR_FIXO');

  expect(erros).toEqual([]);
});

test('novo cenário escolhendo o método por qualificador no próprio formulário', async ({ page }) => {
  const erros: string[] = [];
  page.on('pageerror', erro => erros.push(erro.message));

  await page.goto('/simulador/novo');
  await page.locator('[name="nom_cenario"]').fill('Cenário por qualificador E2E');
  await expect(page.getByTestId('arvore-metodos-form')).toBeHidden();
  await page.getByTestId('modo-qualificador').check();
  await expect(page.getByTestId('arvore-metodos-form')).toBeVisible();
  await expect(page.locator('#bloco_por_perna')).toBeHidden();

  const bloco = page.getByTestId('linha-1.986.60');
  await bloco.locator('select').selectOption('VALOR_FIXO');
  await bloco.locator('input').fill('1200');
  const folha2 = page.getByTestId('linha-1.986.60.2');
  await folha2.locator('select').selectOption('PERCENTUAL');
  await folha2.locator('input').fill('5');
  await expect(page.getByTestId('linha-1.986.60.1').locator('.res-metodo')).toContainText('herda Valor fixo');
  await expect(folha2.locator('.res-metodo')).toContainText('próprio');

  await page.getByRole('button', { name: 'Salvar Cenário', exact: true }).click();
  await expect(page).toHaveURL(/\/simulador\/\d+\/metodos\?cobertura=1$/);
  await expect(page.getByTestId('no-1.986.60')).toHaveAttribute('data-origem', 'PROPRIA');
  await expect(page.getByTestId('no-1.986.60.1')).toHaveAttribute('data-origem', 'HERDADA');
  await expect(page.getByTestId('no-1.986.60.2')).toHaveAttribute('data-metodo', 'PERCENTUAL');
  expect(erros).toEqual([]);
});
