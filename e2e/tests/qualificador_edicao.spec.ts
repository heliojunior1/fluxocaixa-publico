import { expect, test } from '@playwright/test';
import { STORAGE_STATE_ADMIN } from '../consts';

test.use({ storageState: STORAGE_STATE_ADMIN });

// ⚠️ Este teste existe porque a edição de qualificador respondeu 500 por um
// commit inteiro sem que 566 pytest e 48 Playwright percebessem: o único teste
// que tocava `update_qualificador` esperava um erro levantado ANTES da linha
// quebrada. É o caminho de SUCESSO que faltava.
//
// Edita o BLOCO 1.6 (raiz, visível sem expandir) mantendo o código — mudar o
// código dispararia a cascata do R17, que é outro cenário.
test('editar um qualificador pela tela grava a alteração', async ({ page }) => {
  await page.goto('/qualificadores');

  const no = page
    .getByText('1.6', { exact: true })
    .locator('xpath=ancestor::div[contains(@class,"qualificador-node")][1]');
  await expect(no).toBeVisible();
  const seq = await no.getAttribute('data-id');
  expect(seq).toBeTruthy();

  const novaDescricao = `Rubrica Profunda N1 editada ${Date.now()}`;
  await page.evaluate(
    ([id, desc]) => {
      const form = document.createElement('form');
      form.method = 'POST';
      form.action = `/qualificadores/edit/${id}`;
      const campos: Record<string, string> = {
        num_qualificador: '1.6',
        dsc_qualificador: desc as string,
        cod_qualificador_pai: '',
        confirmado: 'true',
      };
      for (const [nome, valor] of Object.entries(campos)) {
        const input = document.createElement('input');
        input.name = nome;
        input.value = valor;
        form.appendChild(input);
      }
      document.body.appendChild(form);
      form.submit();
    },
    [seq, novaDescricao]
  );

  await page.waitForURL('**/qualificadores');
  // um 500 apareceria como página de erro; a descrição nova prova que gravou
  await expect(page.getByText(novaDescricao, { exact: true })).toBeVisible();
});
