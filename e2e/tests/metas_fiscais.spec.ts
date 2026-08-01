import { expect, test } from '@playwright/test';
import { STORAGE_STATE_ADMIN } from '../consts';

test.use({ storageState: STORAGE_STATE_ADMIN });

// Bloco 2.9 marcado como EDUCACAO, com as folhas 2.9.1/2.9.2 herdando e sem a
// palavra "educação" na descrição — o caso que a heurística antiga zerava.
test.describe('metas fiscais por categoria explícita', () => {
  test('a árvore mostra a categoria e se ela é herdada', async ({ page }) => {
    await page.goto('/qualificadores');

    const bloco = page
      .getByText('2.9', { exact: true })
      .locator('xpath=ancestor::div[contains(@class,"qualificador-node")][1]');
    await expect(bloco).toBeVisible();
    // marcação PRÓPRIA: sem o sufixo "(herdada)"
    await expect(page.getByTestId('categoria-fiscal-2.9')).toHaveText('EDUCACAO');

    await bloco.locator('> .node-content .toggle-btn').click();
    // folha: mesma categoria, mas HERDADA — e é isso que o usuário precisa ver
    await expect(page.getByTestId('categoria-fiscal-2.9.1')).toContainText('herdada');
  });

  test('a meta de educação soma as folhas que herdaram do bloco', async ({ page }) => {
    const resposta = await page.request.get(
      '/relatorios/ldo-orcamento/data?ano=2018'
    );
    expect(resposta.ok()).toBeTruthy();
    const dados = await resposta.json();

    const educacao = dados.metas_fiscais.find(
      (m: { nome: string }) => m.nome === 'Aplicação em Educação'
    );
    expect(educacao).toBeTruthy();
    // 3000 + 2000 das duas folhas herdeiras, sobre a despesa total de 2018
    expect(Number(educacao.percentual)).toBeGreaterThan(0);
  });

  test('a dívida consolidada não é mais exibida', async ({ page }) => {
    const resposta = await page.request.get(
      '/relatorios/ldo-orcamento/data?ano=2018'
    );
    const dados = await resposta.json();
    const nomes = dados.metas_fiscais.map((m: { nome: string }) => m.nome);
    expect(nomes.some((n: string) => n.includes('Dívida'))).toBeFalsy();
  });
});
