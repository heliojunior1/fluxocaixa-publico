import { expect, test } from '@playwright/test';
import { STORAGE_STATE_ADMIN } from '../consts';

test.use({ storageState: STORAGE_STATE_ADMIN });

test('lançamento com valor zero mostra mensagem de validação na tela', async ({ page }) => {
  await page.goto('/saldos');
  await page.getByTestId('novo-lancamento').click();

  const modal = page.locator('#manual-entry-modal');
  await expect(modal).toBeVisible();
  await modal.locator('[name="dat_lancamento"]').fill('2026-07-10');
  await modal.locator('[name="seq_qualificador"]').selectOption({ index: 1 });
  await modal.locator('[name="val_lancamento"]').fill('0');
  await modal.locator('form#manual-entry-form button[type="submit"]').click();

  await expect(page.getByTestId('flash-erro')).toContainText(
    'O valor do lançamento deve ser positivo'
  );
});

test('excluir qualificador com lançamentos pede confirmação em duas etapas', async ({ page }) => {
  // Rubrica 9.9.9 (com lançamento) criada pelo seed_usuarios_e2e.py
  page.on('dialog', (dialog) => dialog.accept());

  await page.goto('/qualificadores');
  await page.getByTestId('excluir-qualificador-9.9.9').click();

  // 1ª etapa: flash + banner de confirmação
  await expect(page.getByTestId('flash-erro')).toContainText('confirme a exclusão');
  await expect(page.getByTestId('banner-confirmar-exclusao')).toBeVisible();

  // 2ª etapa: confirmar de fato
  await page.getByTestId('confirmar-exclusao').click();
  await expect(page.getByTestId('banner-confirmar-exclusao')).toHaveCount(0);
  await expect(page.getByTestId('excluir-qualificador-9.9.9')).toHaveCount(0);
});
