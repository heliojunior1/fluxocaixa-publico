import { expect, test } from '@playwright/test';
import { STORAGE_STATE_ADMIN, STORAGE_STATE_CONSULTA } from '../consts';

test.describe('fontes de recurso (admin)', () => {
  test.use({ storageState: STORAGE_STATE_ADMIN });

  test('exibe a decomposição operacional e o catálogo do seed', async ({ page }) => {
    await page.goto('/fontes-recurso');
    // Rótulo "operacional" com a ressalva do RGF e os quatro números
    await expect(page.getByTestId('disponibilidade-operacional')).toBeVisible();
    await expect(page.getByTestId('grupo-livre')).toBeVisible();
    await expect(page.getByTestId('grupo-vinculado')).toBeVisible();
    await expect(page.getByTestId('grupo-pendente')).toBeVisible();
    // Fonte livre do seed (padrão STN)
    await expect(page.getByTestId('fonte-1.500')).toBeVisible();
  });

  test('cadastra uma fonte vinculada pelo modal', async ({ page }) => {
    await page.goto('/fontes-recurso');
    await page.getByTestId('nova-fonte').click();
    await expect(page.locator('#fonte-modal')).toBeVisible();
    await page.getByTestId('fonte-stn').fill('777');
    await page.getByTestId('fonte-dsc').fill('Fonte E2E Vinculada');
    await page.getByTestId('fonte-vinculada').selectOption('V');
    await page.getByTestId('fonte-salvar').click();

    await expect(page).toHaveURL(/\/fontes-recurso/);
    await expect(page.getByText('Fonte E2E Vinculada')).toBeVisible();
  });

  test('classifica o fundo sem fonte pela tela de fundos', async ({ page }) => {
    await page.goto('/fundos');
    // O fundo do seed nasce sem fonte — destacado como pendente de classificação
    await expect(page.getByTestId('aviso-sem-fonte-9931')).toBeVisible();

    const form = page.getByTestId('classificar-fonte-9931');
    // seleciona a primeira fonte real do combo (a opção 1 é "sem fonte")
    const primeiraFonte = await form.locator('select option:nth-child(2)').getAttribute('value');
    await form.locator('select').selectOption(primeiraFonte!);
    await form.locator('button[type="submit"]').click();

    await expect(page).toHaveURL(/\/fundos/);
    await expect(page.getByTestId('aviso-sem-fonte-9931')).toHaveCount(0);
  });
});

test.describe('conciliação por fonte (admin)', () => {
  test.use({ storageState: STORAGE_STATE_ADMIN });

  test('exibe a tabela de conciliação operacional × contábil', async ({ page }) => {
    await page.goto('/fontes-recurso/conciliacao?data=2058-01-31');
    await expect(page.getByTestId('conciliacao-fonte')).toBeVisible();
  });
});

test.describe('fonte no lançamento manual (admin)', () => {
  test.use({ storageState: STORAGE_STATE_ADMIN });

  test('cria lançamento com fonte e a vê na lista e no filtro', async ({ page }) => {
    await page.goto('/saldos');
    await page.getByTestId('novo-lancamento').click();
    await expect(page.locator('#manual-entry-modal')).toBeVisible();

    await page.locator('#dat_lancamento').fill('2036-02-10');
    await page.locator('#seq_qualificador').selectOption({ index: 1 });
    await page.locator('#val_lancamento').fill('1234.56');
    // fonte OPCIONAL e SEM default — seleção explícita da 1ª fonte real
    const fonte = page.getByTestId('lancamento-fonte');
    await expect(fonte).toHaveValue('');
    const valorFonte = await fonte.locator('option:nth-child(2)').getAttribute('value');
    await fonte.selectOption(valorFonte!);
    await page.locator('#manual-entry-form button[type="submit"]').click();

    await expect(page).toHaveURL(/\/saldos/);
    // filtra pela fonte escolhida e encontra o lançamento (com a fonte na coluna)
    await page.getByTestId('filtro-fonte-recurso').selectOption(valorFonte!);
    await page.locator('form button[type="submit"]', { hasText: 'Consultar' }).click();
    const linha = page.getByRole('row', { name: /10\/02\/2036/ });
    await expect(linha).toBeVisible();
    await expect(linha.getByText('1.500')).toBeVisible();
  });
});

test.describe('repartição por fonte (admin)', () => {
  test.use({ storageState: STORAGE_STATE_ADMIN });

  test('mostra pendência e define uma repartição de 100%', async ({ page }) => {
    await page.goto('/reparticao-fonte');
    // qualificador de receita do seed E2E sem repartição → pendência destacada
    const pendencia = page.locator('[data-testid^="pendencia-"]').first();
    await expect(pendencia).toBeVisible();
    const num = (await pendencia.getAttribute('data-testid'))!.replace('pendencia-', '');

    // define 100% numa fonte — a soma tem de ser exatamente 100
    const form = page.getByTestId(`form-reparticao-${num}`);
    await form.locator('input[name^="pct_"]').first().fill('100');
    await page.getByTestId(`salvar-reparticao-${num}`).click();
    await expect(page.getByTestId(`pendencia-${num}`)).toHaveCount(0);
  });
});

test.describe('fontes de recurso (CONSULTA)', () => {
  test.use({ storageState: STORAGE_STATE_CONSULTA });

  test('vê o catálogo sem ações de manutenção', async ({ page }) => {
    await page.goto('/fontes-recurso');
    await expect(page.getByTestId('disponibilidade-operacional')).toBeVisible();
    await expect(page.getByTestId('nova-fonte')).toHaveCount(0);
    await expect(page.getByTestId('importar-fontes')).toHaveCount(0);
  });
});
