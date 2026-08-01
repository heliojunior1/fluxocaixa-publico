import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  globalSetup: './global-setup',
  timeout: 30_000,
  use: {
    baseURL: 'http://localhost:8433',
    // Local: navegador visível para acompanhar a execução; CI: headless
    headless: !!process.env.CI,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  webServer: {
    command: 'sh start-server.sh',
    url: 'http://localhost:8433/login',
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
  projects: [{ name: 'chromium', use: { browserName: 'chromium' } }],
});
