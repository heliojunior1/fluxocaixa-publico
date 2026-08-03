/**
 * Utilitários de segurança do lado do cliente (spec relatorios R21).
 *
 * ORIGEM ÚNICA do escape de HTML. Cada template reimplementar o seu produziria
 * variações sutilmente diferentes — foi assim que o mesmo defeito apareceu em
 * sete arquivos.
 *
 * Por que escapar na SAÍDA e não sanitizar na entrada: a mesma descrição de
 * cadastro vai para corpo HTML, valor de atributo, JSON e XLSX, e cada destino
 * escapa diferente. Sanitizar na gravação escolheria um e erraria os outros —
 * além de mutilar descrição legítima como "Contribuições < 1 salário".
 */
(function () {
  'use strict';

  var MAPA = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
    '`': '&#96;',
  };

  /**
   * Escapa texto para interpolação segura em HTML — corpo OU valor de atributo.
   *
   * Aspas simples e duplas entram no mapa porque o projeto interpola em
   * atributo (`data-qualifier-name="${...}"`), onde escapar só `<` e `>`
   * deixaria a injeção por quebra de atributo em pé.
   *
   * `null`/`undefined` viram string vazia: o chamador quase sempre quer isso, e
   * "undefined" aparecendo na tela é defeito visual que passa despercebido.
   */
  window.escHtml = function (valor) {
    if (valor === null || valor === undefined) return '';
    return String(valor).replace(/[&<>"'`]/g, function (c) {
      return MAPA[c];
    });
  };
})();

/**
 * Injeção automática do token CSRF (spec controle-acesso R12).
 *
 * Por que automático e não `{{ csrf_field() }}` em cada formulário: são ~70
 * formulários em 46 templates e 14 chamadas `fetch`. O problema não é o esforço
 * inicial — é o formulário nº 71, que não quebra: fica DESPROTEGIDO em
 * silêncio. Mesmo raciocínio que levou `modo_demo` a virar global Jinja no
 * projeto ("passar pela mão em cada TemplateResponse seria esquecido na
 * primeira rota nova").
 */
(function () {
  'use strict';

  var META = document.querySelector('meta[name="csrf-token"]');
  var TOKEN = META ? META.getAttribute('content') : '';
  var CAMPO = 'csrf_token';
  var CABECALHO = 'X-CSRF-Token';
  var SEGUROS = ['GET', 'HEAD', 'OPTIONS', 'TRACE'];

  if (!TOKEN) return;

  function injetar(form) {
    var metodo = (form.getAttribute('method') || 'GET').toUpperCase();
    if (SEGUROS.indexOf(metodo) !== -1) return;
    if (form.querySelector('input[name="' + CAMPO + '"]')) return;
    var campo = document.createElement('input');
    campo.type = 'hidden';
    campo.name = CAMPO;
    campo.value = TOKEN;
    form.appendChild(campo);
  }

  function injetarTodos() {
    Array.prototype.forEach.call(document.querySelectorAll('form'), injetar);
  }

  document.addEventListener('DOMContentLoaded', injetarTodos);
  // Fase de CAPTURA: pega também o formulário criado por JS depois do load
  // (modais montados dinamicamente), que o varrer-no-load não alcançaria.
  document.addEventListener('submit', function (ev) {
    if (ev.target && ev.target.tagName === 'FORM') injetar(ev.target);
  }, true);

  // `form.submit()` programático NÃO dispara o evento `submit` — o listener
  // acima não o alcança. Sem este patch, todo formulário montado e submetido
  // por código ficaria sem token e tomaria 403 (descoberto pelo E2E, que faz
  // exatamente isso).
  var submitOriginal = HTMLFormElement.prototype.submit;
  HTMLFormElement.prototype.submit = function () {
    injetar(this);
    return submitOriginal.apply(this, arguments);
  };

  // `fetch` de mesma origem e método mutante ganha o cabeçalho — cobre as 14
  // chamadas existentes e as futuras sem tocar em nenhuma delas.
  var fetchOriginal = window.fetch;
  window.fetch = function (entrada, init) {
    init = init || {};
    var metodo = (init.method || (entrada && entrada.method) || 'GET').toUpperCase();
    var alvo = typeof entrada === 'string' ? entrada : (entrada && entrada.url) || '';
    var mesmaOrigem = !/^https?:\/\//i.test(alvo) ||
      alvo.indexOf(window.location.origin) === 0;
    if (SEGUROS.indexOf(metodo) === -1 && mesmaOrigem) {
      var cabecalhos = new Headers(init.headers || (entrada && entrada.headers) || {});
      if (!cabecalhos.has(CABECALHO)) cabecalhos.set(CABECALHO, TOKEN);
      init.headers = cabecalhos;
    }
    return fetchOriginal.call(this, entrada, init);
  };
})();
