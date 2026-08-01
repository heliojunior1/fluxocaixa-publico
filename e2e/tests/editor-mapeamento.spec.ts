import { expect, Page, test } from '@playwright/test';
import { STORAGE_STATE_ADMIN } from '../consts';

function nomeUnico(prefixo: string): string {
  return `${prefixo} ${Date.now()}`;
}

// Mapeamento de referência (estilo API #54 BB).
const CAMPOS: Array<[string, string, string]> = [
  ['codigoFundoInvestimento', 'cod_fundo', ''],
  ['nomeFundoInvestimento', 'dsc_fundo', ''],
  ['valorSaldoBruto', 'val_saldo', ''],
];

const AMOSTRA = JSON.stringify({
  listaFundosInvestimento: [
    { codigoFundoInvestimento: 87, nomeFundoInvestimento: 'ALFA', valorSaldoBruto: 100.0 },
    { codigoFundoInvestimento: 618, nomeFundoInvestimento: 'BETA', valorSaldoBruto: 200.0 },
  ],
});

async function montarMapeamento(page: Page) {
  await page.getByTestId('map-lista-path').fill('listaFundosInvestimento');
  for (let i = 1; i < CAMPOS.length; i++) {
    await page.getByTestId('map-add-campo').click();
  }
  const linhas = page.getByTestId('map-campo');
  for (let i = 0; i < CAMPOS.length; i++) {
    const [caminho, destino, transf] = CAMPOS[i];
    const linha = linhas.nth(i);
    await linha.getByTestId('map-campo-caminho').fill(caminho);
    await linha.getByTestId('map-campo-destino').selectOption(destino);
    await linha.getByTestId('map-campo-transf').selectOption(transf);
  }
}

test.describe('editor de mapeamento (admin)', () => {
  test.use({ storageState: STORAGE_STATE_ADMIN });

  test('API_REST: monta mapeamento, prevê e a fonte mostra a seção de mapeamento', async ({ page }) => {
    await page.goto('/extracao/fontes/nova?tipo=API_REST');
    // Seção certa por layout_kind
    await expect(page.getByTestId('secao-mapeamento')).toBeVisible();
    await expect(page.getByTestId('secao-layout')).toHaveCount(0);

    await montarMapeamento(page);

    // Preview colando uma amostra JSON → 2 linhas, 0 erros
    await page.getByTestId('map-amostra').fill(AMOSTRA);
    await page.getByTestId('map-preview-btn').click();
    await expect(page.getByTestId('map-preview-resultado')).toContainText('2 linha(s) · 0 erro(s)');
  });

  test('BANCO_SQL usa o mesmo editor de mapeamento (não o de arquivo)', async ({ page }) => {
    await page.goto('/extracao/fontes/nova?tipo=BANCO_SQL');
    await expect(page.getByTestId('secao-mapeamento')).toBeVisible();
    await expect(page.getByTestId('secao-layout')).toHaveCount(0);
  });
});
