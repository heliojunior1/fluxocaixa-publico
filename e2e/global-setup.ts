import { chromium, FullConfig } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import {
  ADMIN_SENHA_E2E,
  ADMIN_SENHA_INICIAL,
  ADMIN_USUARIO,
  CONSULTA_SENHA,
  CONSULTA_USUARIO,
  EXTRACAO_SENHA,
  EXTRACAO_USUARIO,
  STORAGE_STATE_ADMIN,
  STORAGE_STATE_CONSULTA,
  STORAGE_STATE_EXTRACAO,
} from './consts';

/**
 * Faz o primeiro login do admin (senha inicial → troca obrigatória) e salva o
 * storageState autenticado reutilizado pelos testes.
 */
export default async function globalSetup(config: FullConfig) {
  const baseURL = config.projects[0].use.baseURL as string;
  const storagePath = path.resolve(__dirname, STORAGE_STATE_ADMIN);
  fs.mkdirSync(path.dirname(storagePath), { recursive: true });

  const browser = await chromium.launch();
  const page = await browser.newPage({ baseURL });

  await page.goto('/login');
  await page.getByTestId('login-usuario').fill(ADMIN_USUARIO);
  await page.getByTestId('login-senha').fill(ADMIN_SENHA_INICIAL);
  await page.getByTestId('login-submit').click();

  // Primeiro acesso: troca de senha obrigatória
  await page.waitForURL('**/trocar-senha');
  await page.getByTestId('troca-senha-atual').fill(ADMIN_SENHA_INICIAL);
  await page.getByTestId('troca-nova-senha').fill(ADMIN_SENHA_E2E);
  await page.getByTestId('troca-confirmacao').fill(ADMIN_SENHA_E2E);
  await page.getByTestId('troca-submit').click();
  await page.waitForURL((url) => !url.pathname.includes('trocar-senha'));

  await page.context().storageState({ path: storagePath });

  // Segundo estado: usuário de perfil CONSULTA (testes de visibilidade)
  const contextoConsulta = await browser.newContext({ baseURL });
  const paginaConsulta = await contextoConsulta.newPage();
  await paginaConsulta.goto('/login');
  await paginaConsulta.getByTestId('login-usuario').fill(CONSULTA_USUARIO);
  await paginaConsulta.getByTestId('login-senha').fill(CONSULTA_SENHA);
  await paginaConsulta.getByTestId('login-submit').click();
  await paginaConsulta.waitForURL((url) => !url.pathname.includes('login'));
  await contextoConsulta.storageState({
    path: path.resolve(__dirname, STORAGE_STATE_CONSULTA),
  });
  await contextoConsulta.close();

  // Terceiro estado: usuário de perfil EXTRACAO (telas de extração)
  const contextoExtracao = await browser.newContext({ baseURL });
  const paginaExtracao = await contextoExtracao.newPage();
  await paginaExtracao.goto('/login');
  await paginaExtracao.getByTestId('login-usuario').fill(EXTRACAO_USUARIO);
  await paginaExtracao.getByTestId('login-senha').fill(EXTRACAO_SENHA);
  await paginaExtracao.getByTestId('login-submit').click();
  await paginaExtracao.waitForURL((url) => !url.pathname.includes('login'));
  await contextoExtracao.storageState({
    path: path.resolve(__dirname, STORAGE_STATE_EXTRACAO),
  });
  await contextoExtracao.close();

  await browser.close();
}
