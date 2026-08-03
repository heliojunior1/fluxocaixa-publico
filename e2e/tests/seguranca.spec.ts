import { expect, test } from '@playwright/test';
import { ADMIN_SENHA_E2E, ADMIN_USUARIO, STORAGE_STATE_ADMIN } from '../consts';

// Cobertura E2E dos changes de segurança que só o navegador real prova:
//  - blindar-rotas-administrativas-banco (C1/M8)
//  - corrigir-open-redirect-destino (M4)
//
// O open redirect em particular DEPENDE da normalização do navegador: o teste
// unitário prova que a guarda recusa a string, mas só o browser demonstra que
// `/\host` viraria navegação externa se ela não recusasse.

test.describe('rotas destrutivas de banco', () => {
  test.use({ storageState: STORAGE_STATE_ADMIN });

  test('init-db não responde a GET, mesmo para administrador', async ({ request }) => {
    const resp = await request.get('/init-db', { maxRedirects: 0 });
    expect(resp.status()).toBe(405);
  });

  test('recreate-db não responde a GET, mesmo para administrador', async ({ request }) => {
    const resp = await request.get('/recreate-db', { maxRedirects: 0 });
    expect(resp.status()).toBe(405);
  });

  test('navegar para init-db não destrói os dados', async ({ page }) => {
    // Antes: a rota era GET e o cookie de sessão viaja em navegação top-level
    // (SameSite=lax) — seguir um link de terceiro zerava lançamentos,
    // qualificadores, pagamentos e órgãos do admin logado.
    await page.goto('/qualificadores');
    const antes = await page.getByTestId('excluir-qualificador-9.9.9').count();
    expect(antes).toBeGreaterThan(0);

    const resp = await page.goto('/init-db');
    expect(resp?.status()).toBe(405);

    await page.goto('/qualificadores');
    await expect(page.getByTestId('excluir-qualificador-9.9.9')).toHaveCount(antes);
  });

  test('POST sem confirmação é recusado e preserva os dados', async ({ page, request }) => {
    const resp = await request.post('/init-db', { form: {}, maxRedirects: 0 });
    expect(resp.status()).not.toBe(200);

    await page.goto('/qualificadores');
    await expect(page.getByTestId('excluir-qualificador-9.9.9')).toHaveCount(1);
  });
});

test.describe('confinamento de conectores', () => {
  test.use({ storageState: STORAGE_STATE_ADMIN });

  // O vetor é explorado PELA TELA por quem tem FC_MANT_FONTE_EXTRACAO:
  // diretorio=/etc + padrao_nome=passwd lia arquivo do servidor e devolvia o
  // conteúdo no detalhe da execução.
  test('cadastrar fonte com diretório fora da raiz mostra o erro na tela', async ({ page }) => {
    await page.goto('/extracao/fontes');
    await page.getByTestId('tipo-nova').selectOption('FTP_ARQUIVO');
    await page.getByTestId('nova-fonte').click();

    await page.getByTestId('fonte-nome').fill('Fonte E2E Fora da Raiz');
    await page.getByTestId('fonte-sistema').selectOption('SIS_E2E');
    await page.getByTestId('config-protocolo').fill('PASTA_LOCAL');
    await page.getByTestId('config-diretorio').fill('/etc');
    await page.getByTestId('config-padrao_nome').fill('passwd');

    await page.getByTestId('fonte-salvar').click();

    await expect(page.getByTestId('flash-erro')).toContainText('raiz de extração');
    await page.goto('/extracao/fontes');
    await expect(page.getByText('Fonte E2E Fora da Raiz')).toHaveCount(0);
  });
});

test.describe('XSS armazenado em texto de cadastro', () => {
  test.use({ storageState: STORAGE_STATE_ADMIN });

  // Cadeia real: OPERADOR cria rubrica cuja descrição é o payload; qualquer
  // usuário que abrir o relatório — inclusive ADMINISTRADOR — o executaria na
  // própria sessão. Só o browser prova isto: o teste de servidor vê a string,
  // não o DOM resultante.
  test('descrição com marcação HTML não executa nem cria elemento', async ({ page }) => {
    await page.goto('/relatorios/dfc');
    await page.waitForLoadState('networkidle');

    // 1. O payload não executou.
    const executou = await page.evaluate(() => (window as any).__xss_e2e === 1);
    expect(executou).toBe(false);

    // 2. Nenhum elemento foi criado a partir da descrição.
    expect(await page.locator('img[src="x"]').count()).toBe(0);

    // 3. E o texto continua visível para o usuário, literal.
    await expect(page.getByText('Rubrica', { exact: false }).first()).toBeVisible();
  });
});

test.describe('cabeçalhos de segurança e CSP', () => {
  test.use({ storageState: STORAGE_STATE_ADMIN });

  // Telas representativas: dashboard, um relatório com gráfico (Chart.js +
  // adapter de datas) e uma tela com ícones e JS pesado.
  const TELAS = ['/', '/relatorios/dfc', '/saldos'];

  for (const tela of TELAS) {
    test(`CSP não bloqueia recurso em ${tela}`, async ({ page }) => {
      // Recurso bloqueado por CSP NÃO gera erro visível: a página renderiza
      // sem o gráfico, sem o ícone, ou quase certa — e nenhum assert
      // tradicional percebe. Escutar o console é o que transforma "parece que
      // está tudo bem" em verificação.
      const violacoes: string[] = [];
      page.on('console', (msg) => {
        const texto = msg.text();
        if (/Content Security Policy|Refused to (load|execute|apply)/i.test(texto)) {
          violacoes.push(texto);
        }
      });
      page.on('pageerror', (err) => violacoes.push(`pageerror: ${err.message}`));

      const resp = await page.goto(tela);
      await page.waitForLoadState('networkidle');

      expect(resp?.headers()['content-security-policy']).toBeTruthy();
      expect(resp?.headers()['x-content-type-options']).toBe('nosniff');
      expect(violacoes, `violações de CSP em ${tela}`).toEqual([]);
    });
  }

  test('assets de terceiros são servidos pela própria aplicação', async ({ page }) => {
    // Coleta tudo e só depois compara: o host da aplicação só é conhecido
    // após a navegação (antes dela `page.url()` é about:blank).
    const requisitados: string[] = [];
    page.on('request', (req) => {
      if (req.url().startsWith('http')) requisitados.push(req.url());
    });

    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const hostApp = new URL(page.url()).host;
    const externos = requisitados.filter((u) => new URL(u).host !== hostApp);

    expect(externos, 'a aplicação deve funcionar em rede fechada').toEqual([]);
  });
});

test.describe('proteção CSRF', () => {
  test.use({ storageState: STORAGE_STATE_ADMIN });

  test('formulário real da aplicação carrega e envia o token', async ({ page }) => {
    await page.goto('/qualificadores');
    // A injeção é feita pelo seguranca.js — só o navegador prova que ela
    // acontece de fato em formulário renderizado pelo servidor.
    const temCampo = await page.evaluate(() => {
      const forms = Array.from(document.querySelectorAll('form'));
      const mutantes = forms.filter(
        (f) => (f.getAttribute('method') || 'GET').toUpperCase() !== 'GET'
      );
      return (
        mutantes.length > 0 &&
        mutantes.every((f) => !!f.querySelector('input[name="csrf_token"]'))
      );
    });
    expect(temCampo).toBe(true);
  });

  test('POST forjado sem token é recusado', async ({ request }) => {
    // `request` não passa pelo seguranca.js — é o atacante que monta a
    // requisição fora da página.
    const resp = await request.post('/qualificadores/edit/1', {
      form: { num_qualificador: '1.6', dsc_qualificador: 'forjado' },
      maxRedirects: 0,
    });
    expect(resp.status()).toBe(403);
  });

  test('POST com origem externa é recusado mesmo com token', async ({ page, request }) => {
    await page.goto('/qualificadores');
    const token = await page.evaluate(
      () => document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') ?? ''
    );
    expect(token).not.toBe('');

    const resp = await request.post('/qualificadores/edit/1', {
      form: { num_qualificador: '1.6', dsc_qualificador: 'forjado' },
      headers: { 'X-CSRF-Token': token, Origin: 'https://exemplo-externo.test' },
      maxRedirects: 0,
    });
    expect(resp.status()).toBe(403);
  });
});

test.describe('sessão revogável', () => {
  // Sem storageState: o teste precisa de uma sessão própria, que será revogada.
  test.use({ storageState: { cookies: [], origins: [] } });

  test('trocar a senha derruba a outra sessão do mesmo usuário', async ({ browser }) => {
    // Duas sessões independentes do MESMO usuário — é o cenário de resposta a
    // comprometimento: troco a senha aqui, o cookie roubado morre lá.
    const ctxA = await browser.newContext();
    const ctxB = await browser.newContext();
    const senhaInicial = 'E2e-Sessao-123';
    const senhaNova = 'E2e-Sessao-456';
    const login = 'sessao.e2e';

    const entrar = async (ctx: typeof ctxA, senha: string) => {
      const p = await ctx.newPage();
      await p.goto('/login');
      await p.locator('[name="usuario"]').fill(login);
      await p.locator('[name="senha"]').fill(senha);
      await p.locator('button[type="submit"]').click();
      await p.waitForLoadState('domcontentloaded');
      return p;
    };

    const pA = await entrar(ctxA, senhaInicial);
    const pB = await entrar(ctxB, senhaInicial);
    expect(pB.url()).not.toContain('/login');

    // A troca de senha na sessão A incrementa a versão de credencial.
    await pA.goto('/trocar-senha');
    await pA.locator('[name="senha_atual"]').fill(senhaInicial);
    await pA.locator('[name="nova_senha"]').fill(senhaNova);
    await pA.locator('[name="confirmacao"]').fill(senhaNova);
    await pA.locator('button[type="submit"]').click();
    await pA.waitForLoadState('domcontentloaded');

    // A sessão B, que não trocou nada, cai na próxima requisição.
    await pB.goto('/saldos');
    expect(pB.url()).toContain('/login');

    await ctxA.close();
    await ctxB.close();
  });
});

test.describe('bloqueio por tentativas', () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test('cinco erros bloqueiam, e a senha correta também é recusada', async ({ page }) => {
    // O E2E roda SEM modo demo, então o bloqueio está ativo. Usuário dedicado:
    // bloquear um usuário compartilhado derrubaria os outros specs.
    const login = 'bloqueio.e2e';
    const senha = 'E2e-Bloqueio-123';

    const tentar = async (s: string) => {
      await page.goto('/login');
      await page.locator('[name="usuario"]').fill(login);
      await page.locator('[name="senha"]').fill(s);
      await page.locator('button[type="submit"]').click();
      await page.waitForLoadState('domcontentloaded');
    };

    for (let i = 0; i < 5; i++) await tentar('errada-de-proposito');

    // A sexta é com a senha CERTA — é o que prova que o bloqueio serve para
    // algo: se ela passasse, ele só atrasaria o ataque.
    await tentar(senha);
    expect(page.url()).toContain('/login');
    await expect(page.getByText('Usuário ou senha inválidos')).toBeVisible();
  });
});

test.describe('configuração de ambiente', () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test('cookie de sessão é HttpOnly e respeita o ambiente', async ({ page, context }) => {
    await page.goto('/login');
    await page.locator('[name="usuario"]').fill(ADMIN_USUARIO);
    await page.locator('[name="senha"]').fill(ADMIN_SENHA_E2E);
    await page.locator('button[type="submit"]').click();
    await page.waitForLoadState('domcontentloaded');

    const sessao = (await context.cookies()).find((c) => c.name === 'session');
    expect(sessao, 'cookie de sessão não emitido').toBeTruthy();
    expect(sessao!.httpOnly).toBe(true);
    // O servidor E2E roda com APP_ENV=dev, então `Secure` fica desligado — é
    // exatamente o comportamento do default por ambiente: seguro em qualquer
    // outro caso, dispensado só em desenvolvimento (que fala HTTP).
    expect(sessao!.secure).toBe(false);
  });
});

test.describe('limites de upload', () => {
  test.use({ storageState: STORAGE_STATE_ADMIN });

  test('arquivo acima do limite é recusado na tela', async ({ page }) => {
    await page.goto('/saldos-bancarios');

    // 6 MB > teto de 5 MB. Antes, o arquivo inteiro ia para a memória do
    // processo — que com --workers 1 é a aplicação toda.
    const grande = Buffer.alloc(6 * 1024 * 1024, 0x61);
    await page.getByTestId('import-arquivo').setInputFiles({
      name: 'grande.csv',
      mimeType: 'text/csv',
      buffer: grande,
    });
    await page.getByTestId('import-enviar').click();

    await expect(page.getByTestId('flash-erro')).toContainText('limite');
  });

  test('extensão não suportada é recusada na tela', async ({ page }) => {
    await page.goto('/saldos-bancarios');
    await page.getByTestId('import-arquivo').setInputFiles({
      name: 'relatorio.pdf',
      mimeType: 'application/pdf',
      buffer: Buffer.from('%PDF-1.4 conteudo ficticio'),
    });
    await page.getByTestId('import-enviar').click();

    await expect(page.getByTestId('flash-erro')).toContainText('não suportado');
  });
});

test.describe('destino de redirect após login', () => {
  // Sem storageState: o fluxo é justamente autenticar com destino malicioso.
  test.use({ storageState: { cookies: [], origins: [] } });

  const destinosExternos = [
    { rotulo: 'barra dupla', valor: '//exemplo-externo.test' },
    { rotulo: 'barra invertida', valor: '/\\exemplo-externo.test' },
    { rotulo: 'esquema absoluto', valor: 'https://exemplo-externo.test/painel' },
  ];

  for (const destino of destinosExternos) {
    test(`login com destino externo (${destino.rotulo}) permanece na aplicação`, async ({
      page,
    }) => {
      await page.goto(`/login?next=${encodeURIComponent(destino.valor)}`);
      // host da própria aplicação, lido da página de login já carregada
      const hostEsperado = new URL(page.url()).host;

      await page.locator('[name="usuario"]').fill(ADMIN_USUARIO);
      await page.locator('[name="senha"]').fill(ADMIN_SENHA_E2E);
      await page.locator('button[type="submit"]').click();
      await page.waitForLoadState('domcontentloaded');

      // A asserção real: o navegador terminou no host da aplicação, não fora.
      expect(new URL(page.url()).host).toBe(hostEsperado);
      expect(page.url()).not.toContain('exemplo-externo.test');
    });
  }
});
