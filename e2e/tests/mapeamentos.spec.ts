import { expect, Page, test } from '@playwright/test';
import { STORAGE_STATE_ADMIN, STORAGE_STATE_CONSULTA } from '../consts';

function nomeUnico(prefixo: string): string {
  return `${prefixo} ${Date.now()}`;
}

// Sistema de origem + staging semeados por seed_usuarios_e2e.py (SIS_E2E):
// 2 linhas com natureza começando em 1112, 1 com 2222 — tudo fictício.
const SISTEMA_E2E = 'SIS_E2E';
// rótulo do option: "num — dsc" (ver QUALIF_ROTULO no mapeamento_form.html)
const QUALIF_E2E = '1.9.9 — Receita E2E Mapeável';

// A unicidade do mapeamento é (ano, tipo, sistema de origem): cada teste usa
// o SEU ano, senão o segundo a rodar bate em duplicidade. Só o teste de preview
// precisa de 2026 — é o ano das linhas semeadas na staging.
async function preencherCabecalho(page: Page, descricao: string, ano = '2026') {
  await page.getByTestId('campo-ano').fill(ano);
  await page.getByTestId('campo-tipo').selectOption('1');
  await page.getByTestId('campo-origem').selectOption({ label: SISTEMA_E2E });
  await page.getByTestId('campo-descricao').fill(descricao);
}

test.describe('mapeamentos (admin)', () => {
  test.use({ storageState: STORAGE_STATE_ADMIN });

  test('monta regra no builder, prevê contra a staging e salva', async ({ page }) => {
    const descricao = nomeUnico('Mapeamento E2E');
    await page.goto('/mapeamentos');
    await page.getByTestId('novo-mapeamento').click();

    await preencherCabecalho(page, descricao);
    await page.getByTestId('item-qualificador').first()
      .selectOption({ label: QUALIF_E2E });

    // uma condição no builder: Natureza começa com '1112'
    const linha = page.getByTestId('regra-linha').first();
    await linha.getByTestId('regra-termo').selectOption('Natureza');
    await linha.getByTestId('regra-operador').selectOption('COMECA_COM');
    await linha.getByTestId('regra-valor').fill('1112');

    // preview roda o predicado contra a staging real do sistema de origem
    await page.getByTestId('preview-regra').first().click();
    await expect(page.getByTestId('regra-resultado').first())
      .toContainText('2 linha(s)');

    await page.getByTestId('salvar-mapeamento').click();
    await expect(page.getByTestId('tabela-mapeamentos')).toContainText(descricao);
  });

  test('regra inválida é recusada com mensagem de negócio', async ({ page }) => {
    await page.goto('/mapeamentos/form');
    await preencherCabecalho(page, nomeUnico('Mapeamento Ruim'), '2027');
    await page.getByTestId('item-qualificador').first()
      .selectOption({ label: QUALIF_E2E });

    await page.getByTestId('ir-avancado').first().click();
    await page.getByTestId('item-regra').first().fill("Coisa Inexistente = '1'");

    await page.getByTestId('validar-regra').first().click();
    await expect(page.getByTestId('regra-resultado').first())
      .toContainText('Coisa Inexistente');

    await page.getByTestId('salvar-mapeamento').click();
    await expect(page.getByTestId('flash-erro')).toContainText('Coisa Inexistente');
  });

  test('editar item preserva o mapeamento e reabre a regra no builder', async ({ page }) => {
    const descricao = nomeUnico('Mapeamento Edit');
    await page.goto('/mapeamentos/form');
    await preencherCabecalho(page, descricao, '2028');
    await page.getByTestId('item-qualificador').first()
      .selectOption({ label: QUALIF_E2E });
    const linha = page.getByTestId('regra-linha').first();
    await linha.getByTestId('regra-termo').selectOption('Unidade Gestora');
    await linha.getByTestId('regra-operador').selectOption('IGUAL');
    await linha.getByTestId('regra-valor').fill('999001');
    await page.getByTestId('salvar-mapeamento').click();

    // reabre: a regra é plana, então volta ao builder com a linha preenchida
    await page.getByRole('row', { name: descricao })
      .getByTestId(/^editar-/).click();
    const salva = page.getByTestId('regra-linha').first();
    await expect(salva.getByTestId('regra-termo')).toHaveValue('Unidade Gestora');
    await expect(salva.getByTestId('regra-valor')).toHaveValue('999001');

    await salva.getByTestId('regra-valor').fill('999002');
    await page.getByTestId('salvar-mapeamento').click();
    await expect(page.getByTestId('tabela-mapeamentos')).toContainText(descricao);
  });
});

test.describe('mapeamentos (consulta)', () => {
  test.use({ storageState: STORAGE_STATE_CONSULTA });

  test('não vê as ações de manutenção', async ({ page }) => {
    await page.goto('/mapeamentos');
    await expect(page.getByTestId('tabela-mapeamentos')).toBeVisible();
    await expect(page.getByTestId('novo-mapeamento')).toHaveCount(0);
    await expect(page.getByTestId(/^editar-/)).toHaveCount(0);
    await expect(page.getByTestId(/^inativar-/)).toHaveCount(0);
  });
});
