import { expect, test } from '@playwright/test';
import {
  STORAGE_STATE_ADMIN,
  STORAGE_STATE_CONSULTA,
  STORAGE_STATE_EXTRACAO,
} from '../consts';

// Massa criada por seed_usuarios_e2e.py (ilha 2031-07):
//   conta 001/0001/KPI-1: saldo 900.00 em 10/07/2031 e 1000.00 em 15/07/2031
//   conta 104/0001/KPI-2: saldo 500.00 em 15/07/2031
//   lançamentos em 05/07/2031: Entrada 2000.00 (conta 001), Saída 500.00
//   (conta 001, tipo D) e Entrada 100.00 AUTOMÁTICA SEM conta
//   fonte ativa SALDO_FUNDO com execução SUCESSO no start do servidor

async function aplicarFiltros(page, opts: { banco?: string } = {}) {
  await page.getByTestId('filtro-referencia').fill('2031-07-15');
  await page.getByTestId('filtro-inicio').fill('2031-07-01');
  await page.getByTestId('filtro-fim').fill('2031-07-31');
  if (opts.banco) {
    await page.getByTestId('filtro-banco').selectOption(opts.banco);
  }
  await page.getByTestId('btn-aplicar-filtros').click();
}

test.describe('relatório de KPIs (admin)', () => {
  test.use({ storageState: STORAGE_STATE_ADMIN });

  test('painel com seed conhecido: cards, blocos e semáforo', async ({ page }) => {
    await page.goto('/relatorios/kpis');
    await aplicarFiltros(page);

    // Bloco 1 — saldos: consolidado, quebra dinâmica por banco e variação D-1
    await expect(page.getByTestId('kpi-consolidado')).toContainText('1.500,00');
    await expect(page.getByTestId('banco-001')).toContainText('1.000,00');
    await expect(page.getByTestId('banco-104')).toContainText('500,00');
    // D-1 da conta 001 é 10/07 (último dia com saldo): 1500 − 900 = 600
    await expect(page.getByTestId('kpi-variacao')).toContainText('600,00');

    // Bloco 2 — receita × despesa (inclui a entrada automática sem conta)
    await expect(page.getByTestId('kpi-receita')).toContainText('2.100,00');
    await expect(page.getByTestId('kpi-despesa')).toContainText('500,00');
    await expect(page.getByTestId('kpi-resultado')).toContainText('1.600,00');

    // Bloco 4 — linha da conta com Δ vs D-1
    const linhaConta = page.getByTestId('linha-conta-001-KPI-1');
    await expect(linhaConta).toContainText('100,00'); // delta 1000 − 900

    // Bloco 5 — composição com "outras" zeradas (menos de 5 qualificadores)
    await expect(page.getByTestId('kpi-top-receitas')).toContainText('2.000,00');
    await expect(page.getByTestId('kpi-outras-receitas')).toContainText('0,00');

    // Bloco 6 — semáforo: execução SUCESSO recente ⇒ saldo OK
    await expect(page.getByTestId('semaforo-saldo')).toHaveAttribute('data-estado', 'OK');

    // Sem filtro de banco/conta não há aviso de recorte
    await expect(page.getByTestId('aviso-recorte')).toBeHidden();
  });

  test('filtro por banco muda os valores e sinaliza o recorte sem conta', async ({ page }) => {
    await page.goto('/relatorios/kpis');
    await aplicarFiltros(page, { banco: '001' });

    // Só o banco 001: consolidado cai para 1000 e a entrada automática
    // sem conta (100.00) sai da receita
    await expect(page.getByTestId('kpi-consolidado')).toContainText('1.000,00');
    await expect(page.getByTestId('kpi-receita')).toContainText('2.000,00');
    await expect(page.getByTestId('aviso-recorte')).toBeVisible();
  });
});

test.describe('visibilidade por perfil', () => {
  test('CONSULTA vê o card no hub e abre o painel', async ({ browser }) => {
    const context = await browser.newContext({ storageState: STORAGE_STATE_CONSULTA });
    const page = await context.newPage();

    await page.goto('/relatorios');
    await expect(page.getByTestId('card-rel-kpis')).toBeVisible();

    await page.goto('/relatorios/kpis');
    await expect(page.getByTestId('kpi-consolidado')).toBeVisible();
    await context.close();
  });

  test('perfil sem FC_REL_KPIS não acessa o painel', async ({ browser }) => {
    const context = await browser.newContext({ storageState: STORAGE_STATE_EXTRACAO });
    const page = await context.newPage();

    const resposta = await page.goto('/relatorios/kpis');
    expect(resposta!.status()).toBe(403);
    await context.close();
  });
});
