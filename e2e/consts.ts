// Credenciais do admin nos testes E2E.
// O global-setup troca a senha inicial (admin) por ADMIN_SENHA_E2E e salva o
// storageState autenticado em e2e/.auth/admin.json (fora do controle de versão).
export const ADMIN_USUARIO = 'admin';
export const ADMIN_SENHA_INICIAL = 'admin';
export const ADMIN_SENHA_E2E = 'E2e-Admin-123';
// Relativo ao diretório do playwright.config.ts (e2e/)
export const STORAGE_STATE_ADMIN = '.auth/admin.json';

// Usuário de perfil CONSULTA (criado por seed_usuarios_e2e.py no start do servidor)
export const CONSULTA_USUARIO = 'consulta.e2e';
export const CONSULTA_SENHA = 'E2e-Consulta-123';
export const STORAGE_STATE_CONSULTA = '.auth/consulta.json';

// Usuário de perfil EXTRACAO (executa/consulta fontes — telas de extração)
export const EXTRACAO_USUARIO = 'extracao.e2e';
export const EXTRACAO_SENHA = 'E2e-Extracao-123';
export const STORAGE_STATE_EXTRACAO = '.auth/extracao.json';
