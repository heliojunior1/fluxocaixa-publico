import { expect, test } from '@playwright/test';
import { ADMIN_SENHA_E2E, ADMIN_USUARIO, STORAGE_STATE_ADMIN } from '../consts';

// Testes de login partem de contexto anônimo (sem storageState)
test.describe('fluxo de login (anônimo)', () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test('rota protegida redireciona ao login preservando o destino', async ({ page }) => {
    await page.goto('/saldos');
    await expect(page).toHaveURL(/\/login\?next=\/saldos/);
    await expect(page.getByTestId('login-form')).toBeVisible();
  });

  test('senha incorreta exibe mensagem genérica', async ({ page }) => {
    await page.goto('/login');
    await page.getByTestId('login-usuario').fill(ADMIN_USUARIO);
    await page.getByTestId('login-senha').fill('senha-completamente-errada');
    await page.getByTestId('login-submit').click();
    await expect(page.getByTestId('login-erro')).toHaveText('Usuário ou senha inválidos');
  });

  test('login com sucesso leva ao destino original', async ({ page }) => {
    await page.goto('/login?next=/saldos');
    await page.getByTestId('login-usuario').fill(ADMIN_USUARIO);
    await page.getByTestId('login-senha').fill(ADMIN_SENHA_E2E);
    await page.getByTestId('login-submit').click();
    await expect(page).toHaveURL(/\/saldos/);
  });
});

test.describe('sessão autenticada', () => {
  test.use({ storageState: STORAGE_STATE_ADMIN });

  test('usuário logado aparece na sidebar', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByTestId('usuario-logado')).toHaveText(ADMIN_USUARIO);
  });

  test('logout encerra a sessão e volta ao login', async ({ page }) => {
    await page.goto('/');
    await page.getByTestId('botao-logout').click();
    await expect(page).toHaveURL(/\/login/);
    // Sessão encerrada: rota protegida volta a redirecionar
    await page.goto('/saldos');
    await expect(page).toHaveURL(/\/login\?next=\/saldos/);
  });
});
