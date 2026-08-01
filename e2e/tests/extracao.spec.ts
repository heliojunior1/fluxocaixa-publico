import { expect, test } from '@playwright/test';
import {
  STORAGE_STATE_ADMIN,
  STORAGE_STATE_CONSULTA,
  STORAGE_STATE_EXTRACAO,
} from '../consts';

// Nome único por execução para não colidir entre re-runs no mesmo banco.
function nomeUnico(prefixo: string): string {
  return `${prefixo} ${Date.now()}`;
}

test.describe('telas de extração (admin — cadastro e execução)', () => {
  test.use({ storageState: STORAGE_STATE_ADMIN });

  test('cadastra fonte demo, testa conexão, executa e vê no histórico', async ({ page }) => {
    const nome = nomeUnico('Fonte E2E');

    // Cadastro: escolhe o conector DEMO_MANUAL e abre o formulário dinâmico
    await page.goto('/extracao/fontes');
    await page.getByTestId('tipo-nova').selectOption('DEMO_MANUAL');
    await page.getByTestId('nova-fonte').click();

    await expect(page).toHaveURL(/\/extracao\/fontes\/nova/);
    await page.getByTestId('fonte-nome').fill(nome);
    await page.getByTestId('fonte-sistema').selectOption('SIS_E2E');
    // Campos vindos do schema do conector demo. A conta precisa existir (o
    // seed E2E cria 104/0001/E2E-1); o fundo 9999 é auto-cadastrado pendente.
    await page.getByTestId('config-cod_banco').fill('104');
    await page.getByTestId('config-num_agencia').fill('0001');
    await page.getByTestId('config-num_conta').fill('E2E-1');
    await page.getByTestId('config-cod_fundo').fill('9999');
    await page.getByTestId('config-val_saldo').fill('1234.56');
    // Campo secreto renderizado como password
    await expect(page.getByTestId('config-token')).toHaveAttribute('type', 'password');
    await page.getByTestId('fonte-salvar').click();

    await expect(page).toHaveURL(/\/extracao\/fontes$/);
    const linha = page.locator('tr', { hasText: nome });
    await expect(linha).toBeVisible();
    const seq = (await linha.getAttribute('data-testid'))!.replace('fonte-linha-', '');

    // Testa conexão → toast de sucesso
    await page.getByTestId(`testar-${seq}`).click();
    await expect(page.getByTestId('extracao-toast')).toContainText(/pronto|OK|sucesso/i);

    // Executa agora → toast com status e recarrega
    await page.getByTestId(`executar-${seq}`).click();
    await expect(page.getByTestId('extracao-toast')).toContainText('SUCESSO');

    // Histórico mostra a execução da fonte com status SUCESSO
    await page.goto(`/extracao/execucoes?fonte=${seq}`);
    const linhaExec = page.locator('tbody tr', { hasText: nome });
    await expect(linhaExec.first()).toContainText('SUCESSO');
  });

  test('config inválido é rejeitado com mensagem visível', async ({ page }) => {
    await page.goto('/extracao/fontes/nova?tipo=DEMO_MANUAL');
    await page.getByTestId('fonte-nome').fill(nomeUnico('Fonte Invalida'));
    await page.getByTestId('fonte-sistema').selectOption('SIS_E2E');
    // Preenche os demais obrigatórios e deixa cod_banco vazio — removendo só o
    // required dele, a validação recai no servidor (schema do conector).
    await page.getByTestId('config-cod_banco').evaluate((el) => el.removeAttribute('required'));
    await page.getByTestId('config-num_agencia').fill('0001');
    await page.getByTestId('config-num_conta').fill('E2E-1');
    await page.getByTestId('config-cod_fundo').fill('9999');
    await page.getByTestId('config-val_saldo').fill('10.00');
    await page.getByTestId('fonte-salvar').click();
    await expect(page.getByTestId('flash-erro')).toBeVisible();
  });
});

test.describe('telas de extração (perfil EXTRACAO — consulta e execução)', () => {
  test.use({ storageState: STORAGE_STATE_EXTRACAO });

  test('vê o módulo, mas não a ação de cadastrar fonte', async ({ page }) => {
    await page.goto('/extracao/fontes');
    await expect(page.getByRole('heading', { name: 'Fontes de Extração' })).toBeVisible();
    // EXTRACAO consulta/executa, mas não tem FC_MANT_FONTE_EXTRACAO
    await expect(page.getByTestId('nova-fonte')).toHaveCount(0);
  });
});

test.describe('telas de extração (perfil CONSULTA)', () => {
  test.use({ storageState: STORAGE_STATE_CONSULTA });

  test('CONSULTA não vê o módulo de extração no menu', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByTestId('menu-extracao-fontes')).toHaveCount(0);
    await expect(page.getByTestId('menu-extracao-execucoes')).toHaveCount(0);
  });
});
