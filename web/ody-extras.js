/* Odysseus KIT: extras para o Odysseus (ferramentas nas Tools, tradutor, Finanças, Gym, etc.).
 * Configuracao opcional em window.KIT_CONFIG (ficheiro kit-config.js gerado pelo assistente):
 *   { owner:'...', member:'...', tester:'...', features:{ news:true, glucose:false, ... } }
 * Carregado como script classico antes dos modulos ES (ver docs/INSTALL.md).
 */
const KIT = Object.assign({ owner: 'owner', member: 'member', tester: 'kit-test', features: {} }, window.KIT_CONFIG || {});
(function () {
  'use strict';

  // ---------- 1) helpers ----------
  const _origFetch = window.fetch.bind(window);
  let _userP = null;
  function whoami() {
    if (!_userP) {
      _userP = _origFetch('/api/auth/status', { credentials: 'same-origin' })
        .then(r => r.ok ? r.json() : {})
        .then(j => String(j.username || '').toLowerCase())
        .catch(() => '');
    }
    return _userP;
  }

  // ---------- 2) tools ----------
  const LANGS = [
    ['auto', 'Detetar idioma'], ['pt', 'Português (Portugal)'], ['en', 'Inglês'], ['es', 'Espanhol'],
    ['fr', 'Francês'], ['de', 'Alemão'], ['it', 'Italiano'], ['nl', 'Neerlandês'], ['ro', 'Romeno'],
    ['uk', 'Ucraniano'], ['ru', 'Russo'], ['pl', 'Polaco'], ['zh', 'Chinês'], ['ja', 'Japonês'],
    ['ko', 'Coreano'], ['ar', 'Árabe'], ['hi', 'Hindi'], ['tr', 'Turco'], ['el', 'Grego'],
    ['sv', 'Sueco'], ['da', 'Dinamarquês'], ['no', 'Norueguês'], ['fi', 'Finlandês'], ['cs', 'Checo'],
    ['hu', 'Húngaro'], ['bg', 'Búlgaro'], ['hr', 'Croata'], ['ca', 'Catalão'], ['gl', 'Galego'],
    ['eu', 'Basco'], ['he', 'Hebraico'], ['fa', 'Persa'], ['id', 'Indonésio'], ['vi', 'Vietnamita'],
    ['th', 'Tailandês'], ['tl', 'Filipino'], ['sw', 'Suaíli'], ['bn', 'Bengali'], ['ur', 'Urdu']
  ];
  const SPEECH = { pt: 'pt-PT', en: 'en-GB', es: 'es-ES', fr: 'fr-FR', de: 'de-DE', it: 'it-IT', zh: 'zh-CN', ja: 'ja-JP' };
  const ICON = {
    spark: '<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"/><path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z"/>',
    fin: '<circle cx="12" cy="12" r="9"/><path d="M14.5 9.5c-.5-1-1.5-1.5-2.5-1.5-1.4 0-2.5.8-2.5 2s1.1 1.7 2.5 2 2.5.8 2.5 2-1.1 2-2.5 2c-1 0-2-.5-2.5-1.5M12 6v2m0 8v2"/>',
    news: '<path d="M4 5h13a2 2 0 0 1 2 2v12H6a2 2 0 0 1-2-2z"/><path d="M19 9h1a1 1 0 0 1 1 1v8a1 1 0 0 1-1 1h-1M7 9h8M7 13h8M7 16h5"/>',
    compose: '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>',
    plane: '<path d="M17.8 19.2 16 11l3.5-3.5C21 6 21.5 4 21 3c-1-.5-3 0-4.5 1.5L13 8 4.8 6.2c-.5-.1-.9.1-1.1.5l-.3.5c-.2.5-.1 1 .3 1.3L9 12l-2 3H4l-1 1 3 2 2 3 1-1v-3l3-2 3.5 5.3c.3.4.8.5 1.3.3l.5-.2c.4-.3.6-.7.5-1.2z"/>',
    canva: '<path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z"/><path d="M12 8v8M8.5 10v4M15.5 10v4"/>',
    inbox: '<path d="M4 13l2-7h12l2 7v5H4z"/><path d="M4 13h5l1 2h4l1-2h5"/>',
    glu: '<path d="M12 3s6 6.5 6 11a6 6 0 0 1-12 0c0-4.5 6-11 6-11z"/>',
    gym: '<path d="M6 7v10M18 7v10M3 9v6M21 9v6M6 12h12"/>',
    tr: '<path d="m5 8 6 6"/><path d="m4 14 6-6 2-3"/><path d="M2 5h12"/><path d="M7 2h1"/><path d="m22 22-5-10-5 10"/><path d="M14 18h6"/>',
    mail: '<rect x="2" y="4" width="20" height="16" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>',
    img: '<path d="M12 3l1.9 5.6L19.5 10l-5.6 1.9L12 17.5l-1.9-5.6L4.5 10l5.6-1.4z"/><path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z"/>'
  };

  function toolItem(id, label, icon) {
    const d = document.createElement('div');
    d.className = 'list-item'; d.id = id;
    d.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
      'stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;opacity:0.5;">' + icon + '</svg>' +
      '<span class="grow"></span>';
    d.querySelector('.grow').textContent = label;
    return d;
  }

  function addTools() {
    const sec = document.getElementById('tools-section');
    if (!sec || (document.getElementById('tool-translate-btn') && document.getElementById('tool-finance-btn') && document.getElementById('tool-email-btn') && document.getElementById('tool-glucose-btn'))) { if (sec) orderTools(sec); return !!sec; }
    const mail = toolItem('tool-email-btn', 'Email', ICON.mail);
    mail.addEventListener('click', () => {
      const t = document.getElementById('email-section-title');
      if (t) t.click(); else document.getElementById('email-section')?.scrollIntoView({ behavior: 'smooth' });
    });
    if (!document.getElementById('tool-email-btn')) sec.insertBefore(mail, sec.firstElementChild ? sec.firstElementChild.nextSibling : null);
    const tr = toolItem('tool-translate-btn', 'Tradução', ICON.tr);
    const fin = toolItem('tool-finance-btn', 'Finanças', ICON.fin);
    const gym = toolItem('tool-gym-btn', 'Gym', ICON.gym);
    // /finance/logout limpa a sessão e mostra o pedido de palavra-passe: pede sempre que se entra.
    fin.addEventListener('click', () => openFrame('Finanças', '/finance/logout'));
    gym.addEventListener('click', () => openFrame('Gym', '/finance/gym'));
    const glu = toolItem('tool-glucose-btn', 'Glicose', ICON.glu);
    glu.addEventListener('click', () => openFrame('Glicose', '/finance/glucose'));
    const cv = toolItem('tool-canva-btn', 'Canva', ICON.canva || ICON.img);
    cv.addEventListener('click', () => openFrame('Canva', '/canva/'));
    const ib = toolItem('tool-inbox-btn', 'Caixa de ideias', ICON.inbox || ICON.img);
    ib.addEventListener('click', () => openFrame('Caixa de ideias', '/finance/inbox'));
    const nw = toolItem('tool-news-btn', 'Notícias', ICON.news); nw.addEventListener('click', () => openFrame('Notícias', '/finance/news'));
    const cp = toolItem('tool-compose-btn', 'Compor', ICON.compose); cp.addEventListener('click', () => openFrame('Compor', '/finance/compose'));
    const em2 = toolItem('tool-emails-btn', 'Emails', ICON.mail); em2.addEventListener('click', () => openFrame('Emails', '/finance/emails'));
    const fl = toolItem('tool-flight-btn', 'Voos', ICON.plane); fl.addEventListener('click', () => openFrame('Voos', '/finance/flight'));
    const pg = toolItem('tool-prompt-btn', 'Prompts', ICON.spark); pg.addEventListener('click', () => openFrame('Prompts', '/finance/prompt'));
    const im = toolItem('tool-gemini-images-btn', 'Imagens (Gemini)', ICON.img);
    tr.addEventListener('click', openTranslator);
    im.addEventListener('click', openGeminiImages);
    const gallery = document.getElementById('tool-gallery-btn');
    if (gallery && gallery.parentNode === sec) gallery.after(im); else sec.appendChild(im);
    const items = Array.from(sec.querySelectorAll(':scope > .list-item'));
    const after = items.filter(x => (x.textContent || '').trim().localeCompare('Tradução', 'pt') < 0).pop();
    if (after) after.after(tr); else sec.appendChild(tr);
    if (!document.getElementById('tool-finance-btn')) sec.appendChild(fin);
    sec.appendChild(gym);
    sec.appendChild(glu);
    sec.appendChild(cv);
    sec.appendChild(ib);
    sec.appendChild(nw); sec.appendChild(cp); sec.appendChild(pg); sec.appendChild(fl); sec.appendChild(em2);
    orderTools(sec);
    return true;
  }

  // Ordem da barra Tools: primeiro as usadas no dia a dia, depois o resto.
  const TOOL_ORDER = ['tool-email-btn', 'tool-calendar-btn', 'tool-tasks-btn', 'tool-notes-btn',
    'tool-finance-btn', 'tool-translate-btn', 'tool-gym-btn', 'tool-routine-btn', 'tool-glucose-btn', 'tool-canva-btn', 'tool-news-btn', 'tool-compose-btn', 'tool-prompt-btn', 'tool-flight-btn', 'tool-emails-btn', 'tool-inbox-btn'];

  // ---- Idioma (i18n) ----
  // Dicionario PT -> EN servido pelo hub (/finance/i18n.json). O idioma escolhido fica em localStorage + cookie 'kitlang' (as paginas do hub seguem o cookie).
  const LANG_KEY = 'kit_lang';
  function kitLang() {
    const m = document.cookie.match(/(?:^|;\s*)kitlang=(en|pt)\b/);
    return localStorage.getItem(LANG_KEY) || (m && m[1]) || KIT.language || 'en';
  }
  function setKitLang(l) {
    localStorage.setItem(LANG_KEY, l);
    document.cookie = 'kitlang=' + l + '; Path=/; Max-Age=31536000; SameSite=Lax';
    try { if (window.OdysseusNative && OdysseusNative.setLanguage) OdysseusNative.setLanguage(l); } catch (_) { }
  }
  let I18N = null;
  const norm = x => String(x).replace(/\s+/g, ' ').trim();
  function tr(x) { if (!I18N || kitLang() === 'pt') return x; const v = I18N[norm(x)]; return v ? v : x; }
  const UMAP = [[/Uso dos modelos \(carrega para ver tudo\)/g, 'Model usage (tap to see all)'], [/uso dos modelos…/g, 'model usage…'], [/repõe/g, 'resets'], [/(^|\s)às(?=\s|$)/g, '$1at'],
    [/\bsáb\b/g, 'Sat'], [/\bseg\b/g, 'Mon'], [/\bter\b/g, 'Tue'], [/\bqua\b/g, 'Wed'], [/\bqui\b/g, 'Thu'], [/\bsex\b/g, 'Fri'], [/\bdom\b/g, 'Sun'],
    [/Sessão \(5 h\)/g, 'Session (5 h)'], [/Semana · todos/g, 'Week · all'], [/Semana · /g, 'Week · '], [/sem\./g, 'wk'], [/indisponível/g, 'unavailable'], [/sem acesso/g, 'no access'],
    [/atualizado/g, 'updated'], [/créditos extra/g, 'extra credits'], [/o plano grátis não tem API de uso/g, 'the free plan has no usage API'],
    [/Caracteres\/mês/g, 'Characters/month'], [/Consultas\/mês/g, 'Queries/month'], [/Pedidos\/dia/g, 'Requests/day'], [/(\d+) mil de (\d+) mil/g, '$1k of $2k'],
    [/(\d+) de (\d+) livres/g, '$1 of $2 free'], [/(\d+) de (\d+)/g, '$1 of $2']];
  function trU(x) { x = String(x == null ? '' : x); if (kitLang() === 'pt') return x; UMAP.forEach(([a, b]) => { x = x.replace(a, b); }); return x; }
  const KIT_OWNED = '.ody-kit-row,#ody-usage-bar,[id^="tool-"],#ody-tr,#ody-frame-modal,.ody-menu,[data-ody-tool],.ody-lang-row,.ody-order-box';
  function trNode(root) {
    if (!I18N || kitLang() === 'pt' || !root) return;
    const walker = document.createTreeWalker(root.nodeType === 1 ? root : root.parentNode || document.body, NodeFilter.SHOW_TEXT);
    let n; const nodes = [];
    while ((n = walker.nextNode())) nodes.push(n);
    nodes.forEach(t => { if (t.parentNode && t.parentNode.closest && t.parentNode.closest('[data-ody-lang]')) return; const k = norm(t.nodeValue); if (k.length > 2 && I18N[k]) t.nodeValue = t.nodeValue.replace(t.nodeValue.trim(), I18N[k]); });
    if (root.querySelectorAll) root.querySelectorAll('[placeholder],[title],[aria-label]').forEach(el => {
      ['placeholder', 'title', 'aria-label'].forEach(a => { const v = el.getAttribute(a); if (v && I18N[norm(v)]) el.setAttribute(a, I18N[norm(v)]); });
    });
  }
  function trOwned() { document.querySelectorAll(KIT_OWNED).forEach(trNode); }
  fetch('/finance/i18n.json', { credentials: 'same-origin' }).then(r => r.ok ? r.json() : {}).then(j => {
    I18N = (j && j.web) || {};
    trOwned();
    new MutationObserver(ms => ms.forEach(m => m.addedNodes.forEach(nd => {
      const el = nd.nodeType === 1 ? nd : nd.parentElement; if (!el) return;
      if (el.matches && (el.matches(KIT_OWNED) || el.closest(KIT_OWNED))) trNode(el);
      else if (el.querySelectorAll) el.querySelectorAll(KIT_OWNED).forEach(trNode);
    }))).observe(document.body || document.documentElement, { childList: true, subtree: true });
  }).catch(() => { });

  // ---- Barra de uso dos modelos (junto ao utilizador). Esconde-se em Appearance -> "Barra de uso dos modelos". ----
  (function usageBar() {
    if (window.top !== window) return;
    const css = document.createElement('style');
    css.textContent = '#ody-usage-bar{margin:4px 10px 6px;padding:6px 8px;font-size:11px;line-height:1.25;color:var(--text-secondary,var(--fg,#bbb));opacity:.85;cursor:pointer;border-top:1px solid var(--border,rgba(127,127,127,.25));user-select:none}' +
      '#ody-usage-bar:hover{opacity:1}#ody-usage-bar .u-r{display:flex;align-items:center;gap:6px;margin:3px 0}#ody-usage-bar .u-l{flex:0 0 auto;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:58%}' +
      '#ody-usage-bar .u-b{flex:1;height:3px;background:rgba(127,127,127,.25);border-radius:2px;overflow:hidden}#ody-usage-bar .u-f{height:100%;background:var(--accent-primary,var(--accent,#6ea5cf))}' +
      '#ody-usage-bar .u-f.hi{background:#d9a441}#ody-usage-bar .u-f.cr{background:#d9534f}#ody-usage-bar .u-p{flex:0 0 30px;text-align:right;font-variant-numeric:tabular-nums}' +
      '#ody-usage-bar .u-h{font-weight:600;margin-top:6px;opacity:.9}#ody-usage-bar .u-s{opacity:.6;font-size:10px;margin:-1px 0 2px}#ody-usage-bar .u-x{display:none}#ody-usage-bar.open .u-x{display:block}' +
      'html[data-theme="ryoku"] #ody-usage-bar,body.theme-ryoku #ody-usage-bar{border-radius:0;font-family:var(--mono,inherit);letter-spacing:.02em}';
    document.head.appendChild(css);
    let data = null;
    const esc = t => trU(t).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
    const row = (label, pct, sub) => { const c = pct >= 90 ? ' cr' : pct >= 70 ? ' hi' : '';
      return '<div class="u-r" title="' + esc(sub || '') + '"><span class="u-l">' + esc(label) + '</span><span class="u-b"><span class="u-f' + c + '" style="width:' + Math.min(100, Math.max(0, pct)) + '%"></span></span><span class="u-p">' + pct + '%</span></div>' + (sub ? '<div class="u-s u-x">' + esc(sub) + '</div>' : ''); };
    function render() {
      const ub = document.getElementById('sidebar-user-bar');
      if (!ub || !ub.parentNode) return;
      let el = document.getElementById('ody-usage-bar');
      if (!el) { el = document.createElement('div'); el.id = 'ody-usage-bar'; el.title = trU('Uso dos modelos (carrega para ver tudo)');
        el.addEventListener('click', () => { el.classList.toggle('open'); try { localStorage.setItem('ody-usage-open', el.classList.contains('open') ? '1' : ''); } catch (_) { } });
        if (localStorage.getItem('ody-usage-open')) el.classList.add('open'); }
      if (el.nextSibling !== ub) ub.parentNode.insertBefore(el, ub);
      if (!data) { el.innerHTML = '<div class="u-s">uso dos modelos…</div>'; return; }
      let h = '';
      const cl = (data.items || []).find(x => x.name === 'Claude');
      if (cl && cl.rows) cl.rows.slice(0, 2).forEach(r => { h += row('Claude · ' + r.label.replace('Sessão (5 h)', '5 h').replace('Semana · todos', 'sem.'), r.pct, r.reset ? 'repõe ' + r.reset : ''); });
      else if (cl) h += '<div class="u-s">Claude: ' + esc(cl.error || 'indisponível') + '</div>';
      let x = '';
      (data.items || []).forEach(it => {
        const rows = it.name === 'Claude' ? (it.rows || []).slice(2) : (it.rows || []);
        if (it.name !== 'Claude') x += '<div class="u-h">' + esc(it.name) + '</div>';
        rows.forEach(r => { x += row(it.name === 'Claude' ? 'Claude · ' + r.label.replace('Semana · ', '') + ' (sem.)' : r.label, r.pct, r.reset); });
        if (it.error) x += '<div class="u-s">' + esc(it.error) + '</div>';
        if (it.note) x += '<div class="u-s">' + esc(it.note) + '</div>';
      });
      x += '<div class="u-s" style="margin-top:4px">atualizado ' + esc(data.updated || '') + '</div>';
      el.innerHTML = h + '<div class="u-x">' + x + '</div>';
      try { applyExtraTools(); } catch (_) { }
    }
    function load() { _origFetch('/finance/usage', { credentials: 'same-origin' }).then(r => r.ok ? r.json() : null).then(d => { if (d && d.items) { data = d; render(); } }).catch(() => { }); }
    load(); setInterval(load, 5 * 60 * 1000);
    new MutationObserver(() => { if (!document.getElementById('ody-usage-bar') && document.getElementById('sidebar-user-bar')) render(); })
      .observe(document.body || document.documentElement, { childList: true, subtree: true });
    render();
  })();

  // ---- Appearance: mostrar/esconder as tools extra ----
  const EXTRA_TOOLS = [['tool-email-btn', 'Email (atalho)'], ['tool-finance-btn', 'Finanças'], ['tool-translate-btn', 'Tradução'],
    ['tool-gym-btn', 'Gym'], ['tool-routine-btn', 'Estudo'], ['tool-glucose-btn', 'Glicose'], ['tool-canva-btn', 'Canva'], ['tool-news-btn', 'Notícias'], ['tool-compose-btn', 'Compor'], ['tool-prompt-btn', 'Prompts'], ['tool-flight-btn', 'Voos'], ['tool-emails-btn', 'Emails'], ['tool-inbox-btn', 'Caixa de ideias'], ['tool-gemini-images-btn', 'Imagens (Gemini)']];
  const XT_KEY = 'ody-extra-tools-hidden';
  function xtHidden() { try { return JSON.parse(localStorage.getItem(XT_KEY) || '{}'); } catch (_) { return {}; } }
  function applyExtraTools() {
    const h = xtHidden();
    EXTRA_TOOLS.forEach(([id]) => { const el = document.getElementById(id); if (el) el.style.display = h[id] ? 'none' : ''; });
  }
  // ---- Ordem das abas (Tools) e abas escondidas: guardadas no servidor, por utilizador (o PC e a app partilham) ----
  const ORDER_KEY = 'kit-tools-order';
  function userOrder() { try { const a = JSON.parse(localStorage.getItem(ORDER_KEY) || '[]'); return Array.isArray(a) ? a : []; } catch (_) { return []; } }
  let _saveT = null;
  function savePrefs() {
    clearTimeout(_saveT);
    _saveT = setTimeout(() => {
      try { _origFetch('/finance/prefs', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ order: userOrder(), hidden: xtHidden() }) }); } catch (_) { }
    }, 600);
  }
  (function loadPrefs() {
    _origFetch('/finance/prefs', { credentials: 'same-origin' }).then(r => r.ok ? r.json() : null).then(p => {
      if (!p) return;
      if (Array.isArray(p.order) && p.order.length) localStorage.setItem(ORDER_KEY, JSON.stringify(p.order));
      if (p.hidden && typeof p.hidden === 'object' && Object.keys(p.hidden).length) localStorage.setItem(XT_KEY, JSON.stringify(p.hidden));
      const sec = document.getElementById('tools-section'); if (sec) orderTools(sec);
    }).catch(() => { });
  })();
  function addAppearanceRows() {
    const panel = document.querySelector('[data-settings-panel="appearance"]');
    if (!panel || panel.querySelector('[data-ody-lang]')) return !!panel;
    const anchor = panel.querySelector('[data-ui-key="tool-theme"]');
    const row = anchor && anchor.closest('label');
    if (!row) return false;
    const h = xtHidden();
    let last = row;
    const lr = document.createElement('label'); lr.className = 'vis-row ody-lang-row';
    lr.innerHTML = '<span class="vis-icon"></span><span class="vis-label">Language / Idioma (Kit)</span>' +
      '<select data-ody-lang style="margin-left:auto;background:var(--panel,#222);color:inherit;border:1px solid var(--border,#444);border-radius:6px;padding:3px 6px"><option value="en">English</option><option value="pt">Português</option></select>';
    const ls = lr.querySelector('select'); ls.value = kitLang();
    ls.addEventListener('change', () => { setKitLang(ls.value); location.reload(); });
    last.after(lr); last = lr;
    EXTRA_TOOLS.forEach(([id, name]) => {
      const l = document.createElement('label'); l.className = 'vis-row';
      l.innerHTML = '<span class="vis-icon"></span><span class="vis-label"></span><input type="checkbox" data-ody-tool="' + id + '"><span class="vis-switch"></span>';
      l.querySelector('.vis-label').textContent = name;
      const c = l.querySelector('input'); c.checked = !h[id];
      c.addEventListener('change', () => { const x = xtHidden(); if (c.checked) delete x[id]; else x[id] = 1; localStorage.setItem(XT_KEY, JSON.stringify(x)); applyExtraTools(); savePrefs(); });
      last.after(l); last = l;
    });
    // Ordenar as abas: botoes ▲ ▼ (funciona no PC e no telemovel); a ordem fica guardada no servidor.
    if (!panel.querySelector('[data-ody-order]')) {
      const ob = document.createElement('div'); ob.setAttribute('data-ody-order', '1'); ob.className = 'ody-order-box';
      ob.style.cssText = 'padding:10px 0';
      const tg = document.createElement('button'); tg.type = 'button'; tg.textContent = 'Ordenar as abas (Tools)';
      tg.style.cssText = 'padding:6px 12px;border-radius:8px;border:1px solid var(--border,#444);background:var(--panel,#222);color:inherit;cursor:pointer';
      const lst = document.createElement('div'); lst.style.cssText = 'display:none;margin-top:8px';
      ob.append(tg, lst); last.after(ob);
      const bs = 'padding:2px 10px;border-radius:6px;border:1px solid var(--border,#444);background:var(--panel,#222);color:inherit;cursor:pointer';
      const toolEls = () => { const sec = document.getElementById('tools-section'); return sec ? Array.from(sec.querySelectorAll(':scope > .list-item')).filter(x => x.id) : []; };
      const move = (id, d) => {
        const els = toolEls(), ids = els.map(x => x.id), i = ids.indexOf(id), j = i + d;
        if (i < 0 || j < 0 || j >= ids.length) return;
        [ids[i], ids[j]] = [ids[j], ids[i]];
        localStorage.setItem(ORDER_KEY, JSON.stringify(ids));
        orderTools(document.getElementById('tools-section')); savePrefs(); render();
      };
      const render = () => {
        const els = toolEls(); lst.innerHTML = '';
        if (!els.length) { lst.textContent = 'Abre o menu Tools primeiro.'; return; }
        els.forEach((el, i) => {
          const r = document.createElement('div'); r.style.cssText = 'display:flex;align-items:center;gap:6px;padding:3px 0';
          const nm = document.createElement('span'); nm.style.flex = '1'; nm.textContent = (el.textContent || '').trim();
          const up = document.createElement('button'); up.type = 'button'; up.textContent = '▲'; up.style.cssText = bs; up.disabled = i === 0; up.addEventListener('click', () => move(el.id, -1));
          const dn = document.createElement('button'); dn.type = 'button'; dn.textContent = '▼'; dn.style.cssText = bs; dn.disabled = i === els.length - 1; dn.addEventListener('click', () => move(el.id, 1));
          r.append(nm, up, dn); lst.appendChild(r);
        });
        const rs = document.createElement('button'); rs.type = 'button'; rs.textContent = 'Repor ordem original'; rs.style.cssText = bs + ';margin-top:8px';
        rs.addEventListener('click', () => { localStorage.removeItem(ORDER_KEY); orderTools(document.getElementById('tools-section')); savePrefs(); render(); });
        lst.appendChild(rs);
      };
      tg.addEventListener('click', () => { const open = lst.style.display === 'none'; lst.style.display = open ? 'block' : 'none'; if (open) render(); });
    }
    return true;
  }
  (function initAppearanceRows() {
    if (addAppearanceRows()) return;
    const mo = new MutationObserver(() => { if (addAppearanceRows()) mo.disconnect(); });
    mo.observe(document.documentElement, { childList: true, subtree: true });
  })();

  function orderTools(sec) {
    const items = Array.from(sec.querySelectorAll(':scope > .list-item'));
    const uo = userOrder();
    const base = uo.length ? [...uo, ...TOOL_ORDER.filter(id => !uo.includes(id))] : TOOL_ORDER;
    const first = base.map(id => items.find(x => x.id === id)).filter(Boolean);
    const rest = items.filter(x => !base.includes(x.id));
    [...first, ...rest].forEach(x => sec.appendChild(x));
    applyExtraTools();
  }

  function openGeminiImages() {
    const a = document.createElement('a');
    a.href = 'https://gemini.google.com/app'; a.target = '_blank'; a.rel = 'noopener';
    document.body.appendChild(a); a.click(); a.remove();
  }

  // ---- translator modal ----
  let modal = null, timer = null, seq = 0, trAudio = null;
  function stopAudio() { try { if (trAudio) { trAudio.pause(); trAudio = null; } } catch (_) { } }
  const LS = k => 'ody-tr-' + k;

  function css() {
    if (document.getElementById('ody-tr-css')) return;
    const s = document.createElement('style'); s.id = 'ody-tr-css';
    s.textContent = `
#ody-tr{position:fixed;inset:0;z-index:100000;background:rgba(0,0,0,.55);display:flex;align-items:center;justify-content:center}
#ody-tr .box{background:var(--panel,#171717);color:var(--fg,#ececec);border:1px solid var(--border,#424242);border-radius:14px;
 width:min(920px,96vw);max-height:92vh;display:flex;flex-direction:column;box-shadow:0 10px 40px rgba(0,0,0,.5);overflow:hidden}
#ody-tr .hd{display:flex;align-items:center;gap:8px;padding:12px 14px;border-bottom:1px solid var(--border,#424242);font-weight:600}
#ody-tr .hd .x{margin-left:auto;background:none;border:0;color:inherit;font-size:22px;cursor:pointer;line-height:1;padding:2px 8px}
#ody-tr .langs{display:flex;align-items:center;gap:8px;padding:10px 14px}
#ody-tr select{flex:1;min-width:0;padding:8px;border-radius:8px;border:1px solid var(--border,#424242);background:var(--bg,#212121);color:inherit;font-size:14px}
#ody-tr .swap{background:var(--bg,#212121);border:1px solid var(--border,#424242);color:inherit;border-radius:50%;width:36px;height:36px;cursor:pointer;font-size:16px;flex-shrink:0}
#ody-tr .panes{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:10px;padding:0 14px 10px;min-height:0;flex:1}
#ody-tr .pane{display:flex;flex-direction:column;border:1px solid var(--border,#424242);border-radius:10px;background:var(--bg,#212121);min-height:180px;min-width:0}
#ody-tr textarea{flex:1;resize:none;border:0;outline:0;background:transparent;color:inherit;padding:12px;font-size:17px;line-height:1.45;min-height:150px;font-family:inherit}
#ody-tr .out{flex:1;padding:12px;overflow-wrap:anywhere;font-size:17px;line-height:1.45;white-space:pre-wrap;overflow:auto;min-height:150px}
#ody-tr .out.ph{opacity:.45}
#ody-tr .bar{display:flex;align-items:center;gap:4px;padding:6px 8px;border-top:1px solid var(--border,#424242);font-size:12px;opacity:.9}
#ody-tr .bar button{flex-shrink:0;white-space:nowrap;background:none;border:0;color:inherit;cursor:pointer;padding:6px 8px;border-radius:6px;font-size:13px}
#ody-tr .bar button:hover{background:rgba(127,127,127,.18)}
#ody-tr .bar .info{margin-left:auto;min-width:0;flex:0 1 auto;opacity:.6;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
@media (max-width:700px){#ody-tr{align-items:stretch}#ody-tr .box{width:100vw;max-height:none;height:100%;border-radius:0}
 #ody-tr .panes{grid-template-columns:minmax(0,1fr);overflow:auto}#ody-tr .pane{min-height:150px}}`;
    document.head.appendChild(s);
  }

  function opts(sel, withAuto, val) {
    sel.innerHTML = '';
    LANGS.forEach(([c, n]) => {
      if (c === 'auto' && !withAuto) return;
      const o = document.createElement('option'); o.value = c; o.textContent = n; sel.appendChild(o);
    });
    sel.value = val;
  }

  function build() {
    css();
    const m = document.createElement('div'); m.id = 'ody-tr';
    m.innerHTML = `<div class="box" role="dialog" aria-label="Tradução">
 <div class="hd"><span>Tradução</span><button class="x" title="Fechar" aria-label="Fechar">×</button></div>
 <div class="langs"><select class="src" aria-label="Idioma de origem"></select>
  <button class="swap" title="Trocar idiomas" aria-label="Trocar idiomas">⇄</button>
  <select class="tgt" aria-label="Idioma de destino"></select></div>
 <div class="panes">
  <div class="pane"><textarea class="in" placeholder="Escreve ou cola o texto…" maxlength="15000"></textarea>
   <div class="bar"><button class="pst" title="Colar">📋 Colar</button><button class="mic" title="Ditar">🎤 Ditar</button><button class="clr" title="Limpar">✕ Limpar</button><span class="info cnt"></span></div></div>
  <div class="pane"><div class="out ph">Tradução</div>
   <div class="bar"><button class="cp" title="Copiar">⧉ Copiar</button><button class="ed" title="Editar a tradução">✎ Editar</button><button class="say" title="Ouvir">🔊 Ouvir</button><button class="shr" title="Partilhar">↗ Partilhar</button><span class="info st"></span></div></div>
 </div></div>`;
    const $ = s => m.querySelector(s);
    const src = $('.src'), tgt = $('.tgt'), inp = $('.in'), out = $('.out'), st = $('.st'), cnt = $('.cnt');
    opts(src, true, localStorage.getItem(LS('src')) || 'auto');
    opts(tgt, false, localStorage.getItem(LS('tgt')) || 'pt');
    let detected = '';

    function setOut(t, ph) { out.textContent = t; out.classList.toggle('ph', !!ph); out.contentEditable = ph ? 'false' : 'true'; }
    function run(now) {
      clearTimeout(timer);
      const text = inp.value.trim();
      cnt.textContent = inp.value.length ? inp.value.length + ' car.' : '';
      if (!text) { setOut('Tradução', true); st.textContent = ''; return; }
      timer = setTimeout(async () => {
        const my = ++seq; st.textContent = 'A traduzir…';
        try {
          const r = await _origFetch('/translate/api', { method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text, source: src.value, target: tgt.value }) });
          const j = await r.json();
          if (my !== seq) return;
          if (!r.ok || j.error) throw new Error(j.error || ('HTTP ' + r.status));
          detected = j.detected || '';
          setOut(j.translation || '', false);
          const dn = (LANGS.find(l => l[0] === detected) || [0, detected])[1];
          st.textContent = (src.value === 'auto' && detected ? 'Detetado: ' + dn + ' · ' : '') +
            ENGINE_NAME(j.engine) + ' · ' + ((j.ms || 0) / 1000).toFixed(1) + ' s';
        } catch (e) {
          if (my !== seq) return;
          setOut('Não foi possível traduzir. Verifica a ligação (Tailscale) e tenta de novo.', true);
          st.textContent = String(e.message || e).slice(0, 80);
        }
      }, now ? 0 : 700);
    }
    inp.addEventListener('input', () => run(false));
    inp.addEventListener('keydown', e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) run(true); });
    src.addEventListener('change', () => { localStorage.setItem(LS('src'), src.value); run(true); });
    tgt.addEventListener('change', () => { localStorage.setItem(LS('tgt'), tgt.value); run(true); });
    $('.swap').addEventListener('click', () => {
      const from = src.value === 'auto' ? (detected || (tgt.value === 'pt' ? 'en' : 'pt')) : src.value;
      const res = out.classList.contains('ph') ? '' : out.textContent;
      src.value = tgt.value; tgt.value = from === 'auto' ? 'en' : from;
      if (res) inp.value = res;
      localStorage.setItem(LS('src'), src.value); localStorage.setItem(LS('tgt'), tgt.value);
      run(true);
    });
    $('.pst').addEventListener('click', async () => {
      try { const t = await navigator.clipboard.readText(); if (t) { inp.value = t.slice(0, 15000); run(true); } }
      catch (_) { st.textContent = 'Cola com toque longo na caixa de texto'; inp.focus(); }
    });
    $('.shr').addEventListener('click', async () => {
      if (out.classList.contains('ph')) return; const t = out.textContent;
      try {
        if (window.OdysseusNative && OdysseusNative.shareText) OdysseusNative.shareText('', t);
        else if (navigator.share) await navigator.share({ text: t });
        else { await navigator.clipboard.writeText(t); st.textContent = 'Copiado ✓'; }
      } catch (_) { }
    });
    $('.clr').addEventListener('click', () => { inp.value = ''; run(true); inp.focus(); });
    $('.cp').addEventListener('click', async () => {
      if (out.classList.contains('ph')) return;
      try { await navigator.clipboard.writeText(out.textContent); }
      catch (_) { const t = document.createElement('textarea'); t.value = out.textContent; document.body.appendChild(t); t.select(); document.execCommand('copy'); t.remove(); }
      st.textContent = 'Copiado ✓';
    });
    $('.ed').addEventListener('click', () => {
      if (out.classList.contains('ph')) return;
      out.focus();
      const r = document.createRange(); r.selectNodeContents(out); r.collapse(false);
      const sel = window.getSelection(); sel.removeAllRanges(); sel.addRange(r);
      st.textContent = 'Podes editar a tradução';
    });
    // Voz do aparelho: só é usada se a voz do servidor falhar.
    const speakFallback = (text) => {
      // App Android: a WebView não tem voz; usa a voz do telemóvel.
      const N = window.OdysseusNative;
      if (N && typeof N.speak === 'function') {
        try { N.speak(text, SPEECH[tgt.value] || tgt.value); st.textContent = 'A ler…'; setTimeout(() => { if (st.textContent === 'A ler…') st.textContent = ''; }, 2500); }
        catch (_) { st.textContent = 'Não consegui ler em voz alta'; }
        return;
      }
      if (!window.speechSynthesis || !window.SpeechSynthesisUtterance) { st.textContent = 'Voz indisponível neste aparelho'; return; }
      speechSynthesis.cancel();
      speechSynthesis.resume();
      const speak = () => {
        const u = new SpeechSynthesisUtterance(text);
        u.lang = SPEECH[tgt.value] || tgt.value;
        const vs = speechSynthesis.getVoices();
        const v = vs.find(v => v.lang === u.lang) || vs.find(v => v.lang.startsWith(tgt.value));
        if (v) u.voice = v;
        u.onerror = e => { st.textContent = 'Não consegui ler em voz alta (' + (e.error || 'erro') + ')'; };
        u.onstart = () => { st.textContent = 'A ler…'; };
        u.onend = () => { if (st.textContent === 'A ler…') st.textContent = ''; };
        speechSynthesis.speak(u);
      };
      setTimeout(speak, 80); // o Chrome perde a frase se speak() vier logo a seguir a cancel()
    };
    // "Ouvir": voz neural do servidor (/translate/tts, MP3); igual no browser e na app.
    $('.say').addEventListener('click', async () => {
      if (out.classList.contains('ph')) return;
      const text = out.textContent.trim();
      if (!text) return;
      stopAudio();
      st.textContent = 'A preparar a voz…';
      try {
        const r = await _origFetch('/translate/tts', { method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text, lang: tgt.value }) });
        if (!r.ok) throw new Error('HTTP ' + r.status);
        const url = URL.createObjectURL(await r.blob());
        const a = new Audio(url); trAudio = a;
        a.onended = a.onerror = () => { URL.revokeObjectURL(url); if (st.textContent === 'A ler…') st.textContent = ''; };
        await a.play();
        st.textContent = 'A ler…';
      } catch (_) { speakFallback(text); }
    });
    // Ditado por gravação: grava no aparelho e transcreve no servidor (funciona em qualquer telemóvel/browser)
    const canRec = !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia && window.MediaRecorder);
    let curRec = null;
    const recordText = (lang, btn) => new Promise(async (res, rej) => {
      if (curRec) { curRec.stop(); return res(null); }
      let stream;
      try { stream = await navigator.mediaDevices.getUserMedia({ audio: true }); }
      catch (e) {
        const Nn = window.OdysseusNative;
        if (Nn && typeof Nn.dictate === 'function') { window.__odyDictated = t => { st.textContent = ''; res(t || ''); }; st.textContent = 'A ouvir…'; try { Nn.dictate(SPEECH[lang] || lang); return; } catch (_) { } }
        return rej(new Error('Sem permissão para o microfone: ativa-a nas definições da app'));
      }
      const mr = new MediaRecorder(stream); const chunks = []; const old = btn ? btn.textContent : '';
      if (btn) btn.textContent = '⏹ Parar';
      st.textContent = '🔴 A gravar… toca outra vez para parar';
      const done = () => { try { stream.getTracks().forEach(t => t.stop()); } catch (_) { } curRec = null; if (btn) btn.textContent = old; clearTimeout(tm); };
      const tm = setTimeout(() => { try { mr.stop(); } catch (_) { } }, 25000);
      curRec = { stop: () => { try { mr.stop(); } catch (_) { } } };
      mr.ondataavailable = e => { if (e.data.size) chunks.push(e.data); };
      mr.onstop = async () => {
        done();
        try {
          const blob = new Blob(chunks, { type: mr.mimeType || 'audio/webm' });
          if (blob.size < 1500) { st.textContent = ''; return res(''); }
          st.textContent = 'A transcrever…';
          const b64 = await new Promise(ok => { const fr = new FileReader(); fr.onload = () => ok(String(fr.result).split(',')[1]); fr.readAsDataURL(blob); });
          const r = await _origFetch('/translate/api/stt', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ audio: b64, mime: blob.type, lang: lang }) });
          const j = await r.json(); if (!r.ok || j.error) throw new Error(j.error || ('HTTP ' + r.status));
          st.textContent = ''; res((j.text || '').trim());
        } catch (e) { st.textContent = ''; rej(e); }
      };
      mr.start();
    });
    if (canRec) {
      const micBtn = $('.mic');
      micBtn.style.display = '';
      micBtn.addEventListener('click', async ev => {
        ev.stopImmediatePropagation();
        try { const t = await recordText(src.value, micBtn); if (t) { inp.value = (inp.value ? inp.value + ' ' : '') + t; run(true); } }
        catch (e) { st.textContent = String(e.message || e).slice(0, 80); }
      }, true);
    }
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    const NB = window.OdysseusNative;
    if (canRec) { /* ditado por gravação já ligado acima */ }
    else if (NB && typeof NB.dictate === 'function') $('.mic').addEventListener('click', () => {
      window.__odyDictated = t => { if (t) { inp.value = (inp.value ? inp.value + ' ' : '') + t; run(true); } st.textContent = ''; };
      st.textContent = 'A ouvir…';
      try { NB.dictate(SPEECH[src.value] || (src.value === 'auto' ? '' : src.value)); } catch (_) { st.textContent = 'Ditado indisponível'; }
    });
    else if (NB || !SR) $('.mic').style.display = 'none';   // app antiga ou browser sem ditado
    else $('.mic').addEventListener('click', () => {
      const r = new SR(); r.lang = SPEECH[src.value] || (src.value === 'auto' ? 'pt-PT' : src.value); r.interimResults = false;
      r.onresult = e => { inp.value = (inp.value ? inp.value + ' ' : '') + e.results[0][0].transcript; run(true); };
      r.onerror = () => { st.textContent = 'Ditado indisponível'; };
      st.textContent = 'A ouvir…'; r.start();
    });
    $('.x').addEventListener('click', closeTranslator);
    m.addEventListener('mousedown', e => { if (e.target === m) closeTranslator(); });
    m.addEventListener('keydown', e => { if (e.key === 'Escape') { e.stopPropagation(); closeTranslator(); } });

    // ---- extras: foto, resposta a hóspedes, modo conversa ----
    if (!document.getElementById('ody-tr-css2')) {
      const c2 = document.createElement('style'); c2.id = 'ody-tr-css2';
      c2.textContent = `#ody-tr .extras{display:flex;flex-wrap:wrap;gap:6px;padding:0 14px 8px;align-items:center}
#ody-tr .extras button,#ody-tr .rep button,#ody-tr .conv button{background:var(--bg,#212121);border:1px solid var(--border,#424242);color:inherit;border-radius:8px;padding:7px 10px;cursor:pointer;font-size:13px}
#ody-tr .extras .note{flex:1;min-width:140px;padding:7px;border-radius:8px;border:1px solid var(--border,#424242);background:var(--bg,#212121);color:inherit;font-size:13px}
#ody-tr .rep,#ody-tr .conv{margin:0 14px 10px;padding:10px;border:1px solid var(--border,#424242);border-radius:10px;font-size:14px;overflow:auto;max-height:34vh}
#ody-tr .rep .lbl{opacity:.6;font-size:12px;margin-top:6px}#ody-tr .rep .txt{white-space:pre-wrap}
#ody-tr .conv .row{display:flex;gap:6px;margin-bottom:8px;flex-wrap:wrap;align-items:center}
#ody-tr .conv .big{flex:1;min-width:120px;padding:12px;font-size:15px}
#ody-tr .conv .log div{padding:6px 8px;margin:4px 0;border-radius:10px;background:var(--bg,#212121)}
#ody-tr .conv .log .o{opacity:.65;font-size:12px}`;
      document.head.appendChild(c2);
    }
    const ex = document.createElement('div'); ex.className = 'extras';
    ex.innerHTML = '<button class="b-photo" title="Fotografar um texto e traduzir">📷 Foto</button>' +
      '<button class="b-reply" title="Sugerir resposta ao hóspede">💬 Sugerir resposta</button>' +
      '<button class="b-conv" title="Conversa entre duas línguas">🗣 Conversa</button>' +
      '<input class="note" placeholder="O que queres responder (opcional)" maxlength="300">' +
      '<input class="file" type="file" accept="image/*" capture="environment" style="display:none">';
    $('.langs').after(ex);
    const rep = document.createElement('div'); rep.className = 'rep'; rep.style.display = 'none';
    const conv = document.createElement('div'); conv.className = 'conv'; conv.style.display = 'none';
    $('.panes').after(rep); rep.after(conv);
    const esc = t => String(t == null ? '' : t).replace(/[&<>]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
    const playTts = async (text, lang) => {
      stopAudio();
      try {
        const r = await _origFetch('/translate/tts', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text, lang }) });
        if (!r.ok) throw new Error('HTTP ' + r.status);
        const url = URL.createObjectURL(await r.blob()); const a = new Audio(url); trAudio = a;
        a.onended = a.onerror = () => URL.revokeObjectURL(url); await a.play();
      } catch (_) { speakFallbackLang(text, lang); }
    };
    const speakFallbackLang = (text, lang) => {
      const Nn = window.OdysseusNative;
      if (Nn && typeof Nn.speak === 'function') { try { Nn.speak(text, SPEECH[lang] || lang); } catch (_) { } return; }
      if (window.speechSynthesis && window.SpeechSynthesisUtterance) { const u = new SpeechSynthesisUtterance(text); u.lang = SPEECH[lang] || lang; speechSynthesis.speak(u); }
    };
    // Foto -> texto + tradução
    const fileIn = ex.querySelector('.file');
    ex.querySelector('.b-photo').addEventListener('click', () => fileIn.click());
    fileIn.addEventListener('change', async () => {
      const f = fileIn.files[0]; fileIn.value = ''; if (!f) return;
      st.textContent = 'A ler a foto…';
      try {
        const bm = await createImageBitmap(f); const k = Math.min(1, 1600 / Math.max(bm.width, bm.height));
        const cv = document.createElement('canvas'); cv.width = Math.round(bm.width * k); cv.height = Math.round(bm.height * k);
        cv.getContext('2d').drawImage(bm, 0, 0, cv.width, cv.height);
        const b64 = cv.toDataURL('image/jpeg', 0.85).split(',')[1];
        const r = await _origFetch('/translate/image', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ image: b64, target: tgt.value }) });
        const j = await r.json(); if (!r.ok || j.error) throw new Error(j.error || ('HTTP ' + r.status));
        if (!j.original && !j.translation) { st.textContent = 'Não encontrei texto na foto.'; return; }
        inp.value = j.original || ''; cnt.textContent = inp.value.length + ' car.'; detected = j.detected || ''; setOut(j.translation || '', false);
        st.textContent = 'Foto · ' + ((j.ms || 0) / 1000).toFixed(1) + ' s';
      } catch (e) { st.textContent = 'Erro na foto: ' + String(e.message || e).slice(0, 60); }
    });
    // Sugerir resposta ao hóspede
    ex.querySelector('.b-reply').addEventListener('click', async () => {
      const message = inp.value.trim(); if (!message) { st.textContent = 'Cola primeiro a mensagem do hóspede.'; return; }
      rep.style.display = 'block'; rep.textContent = 'A preparar a resposta…';
      try {
        const lang = detected || (src.value !== 'auto' ? src.value : '');
        const r = await _origFetch('/translate/reply', { method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message, lang, note: ex.querySelector('.note').value }) });
        const j = await r.json(); if (!r.ok || j.error) throw new Error(j.error || ('HTTP ' + r.status));
        rep.innerHTML = '<div class="lbl">Resposta para o hóspede (' + esc(j.lang) + ')</div><div class="txt r1">' + esc(j.reply) + '</div>' +
          '<div class="lbl">Em português (para confirmares)</div><div class="txt">' + esc(j.reply_pt) + '</div>' +
          '<div style="margin-top:8px;display:flex;gap:6px"><button class="rc">⧉ Copiar resposta</button><button class="rs">🔊 Ouvir</button><button class="rx">✕</button></div>';
        rep.querySelector('.rc').onclick = async () => { try { await navigator.clipboard.writeText(j.reply); } catch (_) { } st.textContent = 'Resposta copiada ✓'; };
        rep.querySelector('.rs').onclick = () => playTts(j.reply, j.lang || 'en');
        rep.querySelector('.rx').onclick = () => { rep.style.display = 'none'; };
      } catch (e) { rep.textContent = 'Não consegui preparar a resposta: ' + String(e.message || e).slice(0, 80); }
    });
    // Modo conversa
    const dictate = (lang, btn) => canRec ? recordText(lang, btn) : new Promise((res, rej) => {
      const Nn = window.OdysseusNative, SRn = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (Nn && typeof Nn.dictate === 'function') { window.__odyDictated = t => res(t || ''); try { Nn.dictate(SPEECH[lang] || lang); } catch (e) { rej(e); } }
      else if (SRn) { const r = new SRn(); r.lang = SPEECH[lang] || lang; r.interimResults = false; r.onresult = e => res(e.results[0][0].transcript); r.onerror = () => rej(new Error('Ditado indisponível')); r.onend = () => res(''); r.start(); }
      else rej(new Error('Ditado indisponível: usa a caixa de texto'));
    });
    conv.innerHTML = '<div class="row"><span>Outra pessoa fala:</span><select class="cl"></select></div>' +
      '<div class="row"><button class="big ca">🎤 Eu (português)</button><button class="big cb">🎤 Outra pessoa</button></div>' +
      '<div class="row"><input class="ct" placeholder="…ou escreve aqui e toca num dos botões" style="flex:1;min-width:140px;padding:8px;border-radius:8px;border:1px solid var(--border,#424242);background:var(--bg,#212121);color:inherit"></div>' +
      '<div class="log"></div>';
    const cl = conv.querySelector('.cl'); opts(cl, false, localStorage.getItem(LS('conv')) || 'en');
    const updCb = () => { const nm = (LANGS.find(l => l[0] === cl.value) || [0, cl.value])[1]; conv.querySelector('.cb').textContent = '🎤 ' + tr(nm); };
    cl.addEventListener('change', () => { localStorage.setItem(LS('conv'), cl.value); updCb(); }); updCb();
    ex.querySelector('.b-conv').addEventListener('click', () => { conv.style.display = conv.style.display === 'none' ? 'block' : 'none'; });
    const talk = async (from, to) => {
      const ctIn = conv.querySelector('.ct'); const log = conv.querySelector('.log');
      try {
        let text = ctIn.value.trim(); ctIn.value = '';
        if (!text) { if (curRec) { curRec.stop(); return; } const bt = conv.querySelector(from === 'pt' ? '.ca' : '.cb'); const tt = await dictate(from, bt); if (tt === null) return; text = tt.trim(); }
        if (!text) return;
        const r = await _origFetch('/translate/api', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text, source: from, target: to }) });
        const j = await r.json(); if (!r.ok || j.error) throw new Error(j.error || ('HTTP ' + r.status));
        const d = document.createElement('div');
        d.innerHTML = '<div class="o">' + esc(text) + '</div>' + esc(j.translation); log.prepend(d);
        playTts(j.translation, to);
      } catch (e) { st.textContent = String(e.message || e).slice(0, 80); }
    };
    conv.querySelector('.ca').addEventListener('click', () => talk('pt', cl.value));
    conv.querySelector('.cb').addEventListener('click', () => talk(cl.value, 'pt'));

    m._focus = () => setTimeout(() => inp.focus(), 50);
    m._set = t => { inp.value = t; run(true); };
    return m;
  }

  function ENGINE_NAME(e) {
    e = String(e || '');
    if (e.startsWith('gemini-3.6')) return 'Gemini 3.6 Flash';
    if (e.startsWith('gemini-3.5')) return 'Gemini 3.5 Flash';
    if (e.startsWith('gemini')) return 'Gemini';
    if (e.startsWith('claude')) return 'Claude Haiku (reserva)';
    return e || 'Tradução';
  }

  function openTranslator(text) {
    if (!modal) modal = build();
    if (!modal.isConnected) document.body.appendChild(modal);
    modal.style.display = 'flex';
    if (typeof text === 'string' && text) modal._set(text);
    modal._focus();
  }
  // ---- painel embebido (Finanças / Gym) dentro do Odysseus ----
  let frameModal = null;
  // Tema Ryoku nas ferramentas: o servidor das ferramentas le este cookie e aplica a mesma paleta/tipografia.
  (function themeSync() {
    const html = document.documentElement;
    const apply = () => {
      const r = html.classList.contains('theme-ryoku');
      document.cookie = 'kittheme=' + (r ? 'ryoku' : '') + ';path=/;max-age=31536000;SameSite=Lax';
      try { if (window.OdysseusNative && OdysseusNative.setTheme) OdysseusNative.setTheme(r ? 'ryoku' : ''); } catch (_) { }
      const m = document.getElementById('ody-frame-modal');
      if (m) {
        const box = m.firstChild, fr = m.querySelector('iframe');
        if (box) box.style.background = r ? '#0a0a0a' : '#282c34';
        if (fr) fr.style.background = r ? '#000' : '#282c34';
      }
    };
    apply();
    new MutationObserver(apply).observe(html, { attributes: true, attributeFilter: ['class'] });
    window.__odyThemeApply = apply;
  })();

  function openFrame(title, url) {
    setTimeout(() => window.__odyThemeApply && window.__odyThemeApply(), 0);
    if (!frameModal) {
      frameModal = document.createElement('div');
      frameModal.id = 'ody-frame-modal';
      frameModal.style.cssText = 'position:fixed;inset:0;z-index:10000;background:rgba(0,0,0,.6);display:none;align-items:center;justify-content:center;padding:12px;box-sizing:border-box';
      const box = document.createElement('div');
      box.style.cssText = 'background:#282c34;border-radius:12px;width:min(1000px,100%);height:100%;display:flex;flex-direction:column;overflow:hidden';
      const bar = document.createElement('div');
      bar.style.cssText = 'display:flex;align-items:center;gap:8px;padding:10px 14px;color:#fff;font:600 16px system-ui,sans-serif';
      const h = document.createElement('span'); h.className = 'ody-frame-title'; h.style.flex = '1';
      const x = document.createElement('button'); x.textContent = '✕'; x.setAttribute('aria-label', 'Fechar');
      x.style.cssText = 'background:none;border:0;color:#fff;font-size:20px;cursor:pointer;padding:4px 8px';
      x.addEventListener('click', closeFrame);
      bar.append(h, x);
      const fr = document.createElement('iframe'); fr.className = 'ody-frame';
      fr.style.cssText = 'flex:1;border:0;width:100%;background:#282c34';
      box.append(bar, fr); frameModal.appendChild(box);
      frameModal.addEventListener('click', e => { if (e.target === frameModal) closeFrame(); });
      document.addEventListener('keydown', e => { if (e.key === 'Escape') closeFrame(); });
      document.body.appendChild(frameModal);
    }
    frameModal.querySelector('.ody-frame-title').textContent = title;
    const fr = frameModal.querySelector('.ody-frame');
    fr.setAttribute('src', url); // recarrega sempre: o utilizador pode ter navegado dentro do painel
    frameModal.style.display = 'flex';
  }

  // Finanças: ao esconder a app/separador a sessão fecha (exceto ~2 min depois de abrir a câmara para um recibo/refeição).
  let keepUntil = 0;
  window.addEventListener('message', e => { if (e.data === 'fin-keep') keepUntil = Date.now() + 120000; });
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState !== 'hidden' || Date.now() < keepUntil) return;
    // Só as páginas das Finanças fecham ao esconder a app; Gym, Glicose, Caixa e Canva ficam abertas (uploads de ficheiros).
    try {
      const fr0 = frameModal && frameModal.querySelector('.ody-frame');
      const pth = fr0 && fr0.contentWindow ? fr0.contentWindow.location.pathname : '';
      if (/gym|glucose|inbox|canva|treino/.test(pth)) return;
    } catch (_) { }
    try { fetch('/finance/logout', { credentials: 'same-origin', keepalive: true }); } catch (_) { }
    if (frameModal && frameModal.style.display !== 'none') { frameModal.style.display = 'none'; const f = frameModal.querySelector('.ody-frame'); if (f) f.setAttribute('src', 'about:blank'); }
  });
  function closeFrame() { if (frameModal) { frameModal.style.display = 'none'; const f = frameModal.querySelector('.ody-frame'); try { fetch('/finance/logout', { credentials: 'same-origin', keepalive: true }); } catch (_) { } if (f) f.setAttribute('src', 'about:blank'); } }

  function closeTranslator() { stopAudio(); if (modal) modal.style.display = 'none'; if (window.speechSynthesis) speechSynthesis.cancel();
    try { const N = window.OdysseusNative; if (N && typeof N.stopSpeak === 'function') N.stopSpeak(); } catch (_) { } }
  window.odyOpenTranslator = openTranslator;


  // ---- botões de escolha no chat: o Claude termina com [[opcoes: Sim | Não]] e aqui viram botões ----
  (function choiceButtons() {
    const RX = /\[\[\s*(?:opcoes|opções|options)\s*:\s*([^\]]+?)\s*\]\]/i;
    function send(text) {
      const inp = Array.from(document.querySelectorAll('textarea#message, #message-input')).find(x => x.offsetParent) || document.querySelector('textarea#message'); const btn = document.querySelector('.send-btn');
      if (!inp || !btn) return;
      const proto = inp.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
      const set = Object.getOwnPropertyDescriptor(proto, 'value');
      if (set && set.set) set.set.call(inp, text); else inp.value = text;
      inp.dispatchEvent(new Event('input', { bubbles: true }));
      setTimeout(() => btn.click(), 50);
    }
    function scan() {
      const msgs = document.querySelectorAll('.msg-ai');
      msgs.forEach((m, i) => {
        const body = m.querySelector('.body') || m;
        const last = !Array.from(document.querySelectorAll('.msg-user')).some(u => m.compareDocumentPosition(u) & Node.DOCUMENT_POSITION_FOLLOWING);
        const old = m.querySelector(':scope .ody-choice-btns');
        const t = body.textContent || '';
        const mt = t.match(RX);
        if (old) { if (!last) old.remove(); return; }
        if (!mt) return;
        // tirar o marcador do texto visível
        const w = document.createTreeWalker(body, NodeFilter.SHOW_TEXT); let n;
        while ((n = w.nextNode())) { if (RX.test(n.nodeValue)) { n.nodeValue = n.nodeValue.replace(RX, '').trimEnd(); } }
        if (!last) return;
        const opts = mt[1].split('|').map(x => x.trim()).filter(Boolean).slice(0, 6);
        if (!opts.length) return;
        const box = document.createElement('div'); box.className = 'ody-choice-btns';
        box.style.cssText = 'display:flex;flex-wrap:wrap;gap:8px;margin:10px 0';
        opts.forEach((o, k) => {
          const b = document.createElement('button'); b.type = 'button'; b.textContent = o;
          const neg = /^(n[ãa]o|recusar|cancelar|no|decline)\b/i.test(o);
          b.style.cssText = 'padding:8px 14px;border-radius:8px;cursor:pointer;font:inherit;border:1px solid ' + (neg ? 'rgba(220,90,90,.7)' : 'var(--accent,#5b8abf)') + ';background:' + (neg ? 'rgba(220,90,90,.12)' : 'var(--accent,#5b8abf)') + ';color:' + (neg ? 'inherit' : '#fff');
          b.addEventListener('click', () => { box.querySelectorAll('button').forEach(x => { x.disabled = true; x.style.opacity = '.5'; }); b.style.opacity = '1'; send(o); });
          box.appendChild(b);
        });
        body.appendChild(box);
      });
    }
    let _ct; new MutationObserver(() => { clearTimeout(_ct); _ct = setTimeout(scan, 300); }).observe(document.documentElement, { childList: true, subtree: true, characterData: true });
  })();

  // ---- botão "🌐" em cada resposta do chat: traduz para português de Portugal ----
  function addMsgBtns() {
    document.querySelectorAll('.msg-footer .msg-actions:not([data-odytr])').forEach(acts => {
      acts.dataset.odytr = '1';
      { const pm = acts.closest('.msg-footer'); if (pm && pm.parentElement && pm.parentElement.classList.contains('msg-user')) return; }
      const b = document.createElement('button'); b.type = 'button'; b.className = 'msg-action-btn'; b.title = 'Traduzir para português de Portugal'; b.textContent = '🌐';
      b.addEventListener('click', async e => {
        e.stopPropagation();
        const footer = acts.closest('.msg-footer'); const msg = footer && footer.parentElement; if (!msg) return;
        const old = msg.querySelector(':scope > .ody-msg-tr'); if (old) { old.remove(); return; }
        let raw = msg.dataset.raw || (msg.querySelector('.body') && msg.querySelector('.body').textContent) || '';
        raw = raw.replace(/<think[\s\S]*?<\/think>/gi, '').trim().slice(0, 15000);
        if (!raw) return;
        const box = document.createElement('div'); box.className = 'ody-msg-tr';
        box.style.cssText = 'margin:8px 0;padding:8px 10px;border-left:3px solid #5b8abf;background:rgba(91,138,191,.1);border-radius:6px;white-space:pre-wrap;font-size:14px';
        box.textContent = 'A traduzir…'; footer.after(box);
        try {
          const r = await _origFetch('/translate/api', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text: raw, source: 'auto', target: 'pt' }) });
          const j = await r.json(); if (!r.ok || j.error) throw new Error(j.error || ('HTTP ' + r.status));
          box.textContent = j.translation || '(sem texto)';
        } catch (err) { box.textContent = 'Não consegui traduzir agora.'; }
      });
      acts.appendChild(b);
      const sb = document.createElement('button'); sb.type = 'button'; sb.className = 'msg-action-btn'; sb.title = 'Enviar por email ou WhatsApp'; sb.textContent = '📤';
      sb.addEventListener('click', e => { e.stopPropagation(); const footer = acts.closest('.msg-footer'); const msg = footer && footer.parentElement; if (msg) sendMenu(sb, msg); });
      acts.appendChild(sb);
    });
  }
  // ---- 📤 Enviar: abre o seletor de apps do telemóvel (como a app do Claude) ----
  function draftOf(msg) {
    let raw = msg.dataset.raw || (msg.querySelector('.body') && msg.querySelector('.body').innerText) || '';
    raw = raw.replace(/<think[\s\S]*?<\/think>/gi, '').trim();
    const fence = raw.match(/```[a-z]*\n([\s\S]*?)```/i); if (fence) raw = fence[1].trim();
    let subject = '';
    const m = raw.match(/^\s*(?:\*\*)?(?:Assunto|Subject|Asunto|Objet|Betreff|Oggetto)\s*:\s*(?:\*\*)?\s*(.+)$/im);
    if (m) { subject = m[1].replace(/\*+/g, '').trim(); raw = raw.replace(m[0], '').trim(); }
    raw = raw.replace(/\*\*(.+?)\*\*/g, '$1').replace(/^#{1,6}\s+/gm, '');
    return { subject, body: raw.slice(0, 6000) };
  }
  function sendMenu(anchor, msg) {
    document.querySelectorAll('.ody-send-menu').forEach(x => x.remove());
    const d = draftOf(msg); const N = window.OdysseusNative;
    const enc = encodeURIComponent;
    const menu = document.createElement('div'); menu.className = 'ody-send-menu';
    menu.style.cssText = 'position:fixed;z-index:99999;background:#25282e;border:1px solid #444;border-radius:12px;padding:6px;box-shadow:0 6px 24px rgba(0,0,0,.5);min-width:210px;font-size:14px';
    const item = (label, fn) => { const b = document.createElement('div'); b.textContent = label; b.style.cssText = 'padding:10px 14px;cursor:pointer;border-radius:8px;color:#eee';
      b.onmouseenter = () => b.style.background = '#343842'; b.onmouseleave = () => b.style.background = ''; b.onclick = () => { menu.remove(); fn(); }; menu.appendChild(b); };
    const open = u => window.open(u, '_blank', 'noopener');
    if (N && N.sendMail) {
      item('✉️  Email…', () => N.sendMail(d.subject, d.body));
      item('💬  WhatsApp…', () => N.sendWhatsApp(d.body));
      item('↗️  Outras apps…', () => N.shareText(d.subject, d.body));
    } else {
      item('✉️  Gmail', () => open('https://mail.google.com/mail/?view=cm&fs=1&su=' + enc(d.subject) + '&body=' + enc(d.body)));
      item('✉️  Outlook', () => open('https://outlook.live.com/mail/0/deeplink/compose?subject=' + enc(d.subject) + '&body=' + enc(d.body)));
      item('✉️  App de email (Proton, etc.)', () => { location.href = 'mailto:?subject=' + enc(d.subject) + '&body=' + enc(d.body); });
      item('💬  WhatsApp', () => open('https://wa.me/?text=' + enc(d.body)));
      if (navigator.share) item('↗️  Outras apps…', () => navigator.share({ title: d.subject, text: d.body }).catch(() => {}));
    }
    item('📋  Copiar', () => { const t = (d.subject ? d.subject + '\n\n' : '') + d.body; (navigator.clipboard ? navigator.clipboard.writeText(t) : Promise.reject()).catch(() => { const ta = document.createElement('textarea'); ta.value = t; document.body.appendChild(ta); ta.select(); document.execCommand('copy'); ta.remove(); }); });
    document.body.appendChild(menu);
    const r = anchor.getBoundingClientRect();
    menu.style.left = Math.max(8, Math.min(r.left, innerWidth - menu.offsetWidth - 8)) + 'px';
    menu.style.top = Math.max(8, Math.min(r.bottom + 6, innerHeight - menu.offsetHeight - 8)) + 'px';
    setTimeout(() => document.addEventListener('click', function h() { menu.remove(); document.removeEventListener('click', h); }, { once: true }), 0);
  }
  let _mt = 0;
  new MutationObserver(() => { clearTimeout(_mt); _mt = setTimeout(addMsgBtns, 400); }).observe(document.documentElement, { childList: true, subtree: true });

  function init() {
    if (addTools()) return;
    const mo = new MutationObserver(() => { if (addTools()) mo.disconnect(); });
    mo.observe(document.documentElement, { childList: true, subtree: true });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
  // Android app: "#translate" deep link opens the translator.
  function hash() { if (location.hash === '#translate') { openTranslator(); history.replaceState(null, '', location.pathname + location.search); } }
  window.addEventListener('hashchange', hash); window.addEventListener('load', hash);

  // ---- Botao de ditar no chat: grava, transcreve no servidor e poe o texto na caixa de mensagem ----
  (function chatDictate() {
    let rec = null;
    function mount() {
      const msg = document.getElementById('message');
      if (!msg || document.getElementById('ody-chat-mic')) return !!document.getElementById('ody-chat-mic');
      if (!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia && window.MediaRecorder) && !(window.OdysseusNative && window.OdysseusNative.dictate)) return true;
      const b = document.createElement('button');
      b.type = 'button'; b.id = 'ody-chat-mic'; b.title = 'Ditar mensagem';
      b.style.cssText = 'background:none;border:0;cursor:pointer;color:inherit;padding:6px;border-radius:8px;display:inline-flex;align-items:center;opacity:.85;position:relative;z-index:5';
      b.innerHTML = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="3" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/></svg>';
      const put = t => {
        if (!t) return;
        msg.value = (msg.value ? msg.value + ' ' : '') + t;
        msg.dispatchEvent(new Event('input', { bubbles: true })); msg.focus();
      };
      const state = txt => { b.title = txt || 'Ditar mensagem'; };
      b.addEventListener('click', async ev => {
        ev.preventDefault(); ev.stopPropagation();
        if (rec) { rec.stop(); return; }
        let stream;
        try { stream = await navigator.mediaDevices.getUserMedia({ audio: true }); }
        catch (e) {
          const N = window.OdysseusNative;
          if (N && typeof N.dictate === 'function') { window.__odyDictated = put; try { N.dictate('pt-PT'); return; } catch (_) { } }
          alert('Sem permissão para o microfone. Ativa-a nas definições da app.'); return;
        }
        const mr = new MediaRecorder(stream); const chunks = [];
        const stop = () => { try { mr.stop(); } catch (_) { } };
        const tm = setTimeout(stop, 60000);
        rec = { stop };
        b.style.color = '#ff5b5b'; state('A gravar… toca para parar');
        mr.ondataavailable = e => { if (e.data.size) chunks.push(e.data); };
        mr.onstop = async () => {
          clearTimeout(tm); rec = null; try { stream.getTracks().forEach(t => t.stop()); } catch (_) { }
          b.style.color = ''; 
          const blob = new Blob(chunks, { type: mr.mimeType || 'audio/webm' });
          if (blob.size < 1500) { state(); return; }
          state('A transcrever…'); b.style.opacity = '.4';
          try {
            const b64 = await new Promise(ok => { const fr = new FileReader(); fr.onload = () => ok(String(fr.result).split(',')[1]); fr.readAsDataURL(blob); });
            const r = await _origFetch('/translate/api/stt', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ audio: b64, mime: blob.type, lang: 'pt' }) });
            const j = await r.json(); if (!r.ok || j.error) throw new Error(j.error || ('HTTP ' + r.status));
            put((j.text || '').trim());
          } catch (e) { alert('Não consegui transcrever: ' + String(e.message || e).slice(0, 120)); }
          b.style.opacity = '.85'; state();
        };
        mr.start();
      });
      const left = document.querySelector('.chat-input-left') || document.querySelector('.chat-input-top');
      left.appendChild(b);
      return true;
    }
    let n = 0; const iv = setInterval(() => { if (mount() || ++n > 60) clearInterval(iv); }, 500);
  })();


  // Estudo: para o utilizador 'member' (e conta de testes).
  (function () {
    fetch('/api/auth/status', { credentials: 'same-origin' }).then(r => r.json()).then(d => {
      const un = String(d && d.username || ''); if (un !== KIT.member && un !== KIT.tester && un !== KIT.owner) return;
      let n = 0;
      const t = setInterval(() => {
        const sec = document.getElementById('tools-section');
        if (sec && !document.getElementById('tool-routine-btn')) {
          const rt = toolItem('tool-routine-btn', 'Rotina', '<rect x="4" y="5" width="16" height="15" rx="2"/><path d="M8 3v4M16 3v4M4 10h16M9 15l2 2 4-4"/>');
          rt.addEventListener('click', () => openFrame('Estudo', '/finance/study'));
          sec.appendChild(rt); orderTools(sec);
        }
        if (document.getElementById('tool-routine-btn') || ++n > 40) clearInterval(t);
      }, 1000);
    }).catch(() => { });
  })();


  // Setup: so para administradores. Abre o assistente de configuracao (/finance/setup/); na primeira vez abre-se sozinho.
  (function () {
    fetch('/api/auth/status', { credentials: 'same-origin' }).then(r => r.json()).then(d => {
      if (!d || !d.is_admin) return;
      let n = 0;
      const t = setInterval(() => {
        const sec = document.getElementById('tools-section');
        if (sec && !document.getElementById('tool-setup-btn')) {
          const st = toolItem('tool-setup-btn', 'Setup', '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>');
          st.addEventListener('click', () => openFrame('Setup', '/finance/setup/'));
          sec.appendChild(st); orderTools(sec);
        }
        if (document.getElementById('tool-setup-btn') || ++n > 40) clearInterval(t);
      }, 1000);
      if (!localStorage.getItem('kit_setup_prompted')) {
        fetch('/finance/setup/status', { credentials: 'same-origin' }).then(r => r.ok ? r.json() : null).then(j => {
          if (j && j.done === false) { localStorage.setItem('kit_setup_prompted', '1'); setTimeout(() => openFrame('Setup', '/finance/setup/'), 1500); }
        }).catch(() => { });
      }
    }).catch(() => { });
  })();
})();

// ---------- 3) legibilidade do ecrã inicial (contraste) ----------
// O texto de dica estava com opacity 0.2 (quase invisível) e o subtítulo com 0.6.
(function () {
  if (document.getElementById('ody-a11y-css')) return;
  const s = document.createElement('style');
  s.id = 'ody-a11y-css';
  s.textContent = '#welcome-tip{opacity:.7 !important}#welcome-sub{opacity:.85 !important}';
  (document.head || document.documentElement).appendChild(s);
})();
