import { expect, test } from '@playwright/test';
import { STORAGE_STATE_ADMIN } from '../consts';

test.use({ storageState: STORAGE_STATE_ADMIN });

// Árvore de 6 níveis semeada por seed_usuarios_e2e.py: 1.6 → ... → 1.6.1.1.1.1.1,
// com um lançamento na folha do 6º nível.
const CADEIA = [
  '1.6',
  '1.6.1',
  '1.6.1.1',
  '1.6.1.1.1',
  '1.6.1.1.1.1',
  '1.6.1.1.1.1.1',
];

/**
 * Localiza O NÓ do código, não um ancestral dele.
 *
 * ⚠️ `filter({ hasText })` casa com qualquer nó cuja SUBÁRVORE contenha o
 * texto — então "1.6.1.1.1.1.1" resolvia para a raiz "1.6", que contém o
 * descendente. Ancorar no badge de código (texto exato) e subir UM nível de
 * `.qualificador-node` é o que dá o nó certo.
 */
const no = (page: import('@playwright/test').Page, codigo: string) =>
  page
    .getByText(codigo, { exact: true })
    .locator('xpath=ancestor::div[contains(@class,"qualificador-node")][1]');

test.describe('qualificadores — árvore profunda e folha dinâmica', () => {
  test('a árvore expande os 6 níveis até a folha', async ({ page }) => {
    await page.goto('/qualificadores');

    // Cada nível só aparece depois de expandir o pai — é isso que prova que a
    // recursão do template não para no nível 2.
    for (const codigo of CADEIA) {
      const atual = no(page, codigo);
      await expect(atual).toBeVisible();
      const toggle = atual.locator('> .node-content .toggle-btn');
      if (await toggle.count()) {
        await toggle.click();
      }
    }

    const folha = no(page, '1.6.1.1.1.1.1');
    await expect(folha).toBeVisible();
    // data-nivel confirma a PROFUNDIDADE, não só a presença do texto
    await expect(folha).toHaveAttribute('data-nivel', '5');
  });

  test('folha do 6º nível é oferecida para lançamento', async ({ page }) => {
    await page.goto('/saldos');
    await page.getByTestId('novo-lancamento').click();

    const modal = page.locator('#manual-entry-modal');
    await expect(modal).toBeVisible();
    const opcoes = modal.locator('[name="seq_qualificador"] option');
    await expect(
      opcoes.filter({ hasText: '1.6.1.1.1.1.1' })
    ).toHaveCount(1);
  });

  test('transformar folha com lançamentos em pai pede confirmação', async ({ page }) => {
    await page.goto('/qualificadores');

    // Cadastra um filho sob a folha do 6º nível, que TEM lançamento
    const folha = no(page, '1.6.1.1.1.1.1');
    const seqPai = await folha.getAttribute('data-id');
    expect(seqPai).toBeTruthy();

    await page.evaluate(
      ([seq]) => {
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = '/qualificadores/add';
        const campos: Record<string, string> = {
          num_qualificador: '1.6.1.1.1.1.1.1',
          dsc_qualificador: 'Rubrica Profunda N7',
          cod_qualificador_pai: seq as string,
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
      [seqPai]
    );

    await expect(page.getByTestId('flash-erro')).toContainText('confirme');
    await expect(page.getByTestId('banner-confirmar-pai')).toBeVisible();

    // O "sim" reenvia o mesmo cadastro — sem redigitar
    await page.getByTestId('confirmar-folha-vira-pai').click();
    await expect(no(page, '1.6.1.1.1.1.1.1')).toBeAttached();
  });
});
