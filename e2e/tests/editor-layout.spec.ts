import { expect, Page, test } from '@playwright/test';
import { STORAGE_STATE_ADMIN } from '../consts';

function nomeUnico(prefixo: string): string {
  return `${prefixo} ${Date.now()}`;
}

// Layout de extrato bancário de referência (índice → campo destino + transformação).
const COLUNAS: Array<[string, string, string]> = [
  ['0', 'cod_banco', ''],
  ['1', 'num_agencia', ''],
  ['2', 'num_conta', 'somente_digitos'],
  ['3', 'dat_saldo', 'data'],
  ['4', 'cod_fundo+dsc_fundo', 'codigo_antes_hifen'],
  ['5', 'val_saldo', 'decimal'],
];

// CSV de amostra (BOM), com as mesmas contas seedadas (123456 / 987654).
const AMOSTRA =
  '﻿Banco;Agência;Conta;Data;Descrição;Saldo\n' +
  '104;0001;12345-6;10/07/2026;9999-FUNDO ALFA E2E;1.234,56\n' +
  '104;0001;98765-4;10/07/2026;8888-FUNDO BETA E2E;7.890,12\n';

async function montarLayout(page: Page) {
  // A tabela começa com 1 linha; adiciona até termos 6.
  for (let i = 1; i < COLUNAS.length; i++) {
    await page.getByTestId('lay-add-coluna').click();
  }
  const linhas = page.getByTestId('lay-coluna');
  for (let i = 0; i < COLUNAS.length; i++) {
    const [origem, destino, transf] = COLUNAS[i];
    const linha = linhas.nth(i);
    await linha.getByTestId('lay-col-origem').fill(origem);
    await linha.getByTestId('lay-col-destino').selectOption(destino);
    await linha.getByTestId('lay-col-transf').selectOption(transf);
  }
  await page.getByTestId('lay-header-esperado').fill('Banco;Agência;Conta;Data;Descrição;Saldo');
}

test.describe('editor de layout (admin)', () => {
  test.use({ storageState: STORAGE_STATE_ADMIN });

  test('monta layout, prevê parsing, salva e executa', async ({ page }) => {
    const nome = nomeUnico('Caixa Layout');

    await page.goto('/extracao/fontes');
    await page.getByTestId('tipo-nova').selectOption('FTP_ARQUIVO');
    await page.getByTestId('nova-fonte').click();
    await expect(page).toHaveURL(/\/extracao\/fontes\/nova/);

    // A seção de layout só aparece para conector com schema_layout
    await expect(page.getByTestId('secao-layout')).toBeVisible();

    await page.getByTestId('fonte-nome').fill(nome);
    await page.getByTestId('fonte-sistema').selectOption('SIS_E2E');
    await page.getByTestId('config-protocolo').fill('PASTA_LOCAL');
    await page.getByTestId('config-diretorio').fill('e2e/.data/fixtures');
    await page.getByTestId('config-padrao_nome').fill('AMOSTRA_EXTRATO.csv');

    await montarLayout(page);

    // Preview: upload da amostra → 2 linhas, 0 erros
    await page.getByTestId('lay-preview-arquivo').setInputFiles({
      name: 'AMOSTRA_EXTRATO.csv',
      mimeType: 'text/csv',
      buffer: Buffer.from(AMOSTRA, 'utf-8'),
    });
    await page.getByTestId('lay-preview-btn').click();
    await expect(page.getByTestId('lay-preview-resultado')).toContainText('2 linha(s) · 0 erro(s)');

    // Salvar → volta à lista
    await page.getByTestId('fonte-salvar').click();
    await expect(page).toHaveURL(/\/extracao\/fontes$/);
    const linha = page.locator('tr', { hasText: nome });
    await expect(linha).toBeVisible();
    const seq = (await linha.getAttribute('data-testid'))!.replace('fonte-linha-', '');

    // Executar agora → SUCESSO (arquivo de nome fixo encontrado no dia corrente)
    await page.getByTestId(`executar-${seq}`).click();
    await expect(page.getByTestId('extracao-toast')).toContainText('SUCESSO');

    // Histórico
    await page.goto(`/extracao/execucoes?fonte=${seq}`);
    await expect(page.locator('tbody tr', { hasText: nome }).first()).toContainText('SUCESSO');
  });

  test('layout inválido é rejeitado ao salvar', async ({ page }) => {
    await page.goto('/extracao/fontes/nova?tipo=FTP_ARQUIVO');
    await page.getByTestId('fonte-nome').fill(nomeUnico('Layout Ruim'));
    await page.getByTestId('fonte-sistema').selectOption('SIS_E2E');
    await page.getByTestId('config-protocolo').fill('PASTA_LOCAL');
    await page.getByTestId('config-diretorio').fill('e2e/.data/fixtures');
    await page.getByTestId('config-padrao_nome').fill('AMOSTRA_EXTRATO.csv');

    // Uma coluna com destino válido mas... força transformação inexistente via JS
    // (o <select> só tem as válidas; injetamos uma opção inválida para o servidor validar)
    const linha = page.getByTestId('lay-coluna').first();
    await linha.getByTestId('lay-col-origem').fill('0');
    await linha.getByTestId('lay-col-destino').selectOption('cod_banco');
    await linha.getByTestId('lay-col-transf').evaluate((sel: HTMLSelectElement) => {
      const opt = document.createElement('option');
      opt.value = 'inexistente';
      sel.appendChild(opt);
      sel.value = 'inexistente';
    });

    await page.getByTestId('fonte-salvar').click();
    await expect(page.getByTestId('flash-erro')).toBeVisible();
  });
});
