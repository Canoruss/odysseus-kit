// Private Browser: Chromium persistente por perfil, controlado por HTTP local (127.0.0.1:8794).
import http from 'node:http';
import { chromium } from 'playwright';
import fs from 'node:fs';
import crypto from 'node:crypto';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const DIR = process.env.PB_DIR || path.dirname(fileURLToPath(import.meta.url)), SHOTS = DIR + '/shots', INDEX = SHOTS + '/index.json';
const MAX_SHOTS = 200, MAX_AGE_MS = 7 * 86400e3;
const profiles = {};            // nome -> {ctx, page}
let cur;                        // perfil em uso no pedido
const safe = (p) => (p || 'default').toLowerCase().replace(/[^a-z0-9_-]/g, '').slice(0, 24) || 'default';
const pdir = (p) => p === 'default' ? DIR + '/profile' : `${DIR}/profiles/${p}`;
async function ensure(name) {
  let P = profiles[name]; if (!P) P = profiles[name] = {};
  if (!P.ctx) { P.ctx = await chromium.launchPersistentContext(pdir(name), {
    headless: true, viewport: { width: 1280, height: 900 }, locale: process.env.PB_LOCALE || 'en-US', timezoneId: process.env.PB_TZ || Intl.DateTimeFormat().resolvedOptions().timeZone,
    args: ['--disable-blink-features=AutomationControlled'] }); P.ctx.on('close', () => { P.ctx = null; P.page = null; }); }
  if (!P.page || P.page.isClosed()) P.page = P.ctx.pages()[0] || await P.ctx.newPage();
  cur = P; return P;
}
const pg = () => cur.page;
const COOKIE_WORDS = /^(aceitar tudo|aceitar todos|aceitar todos os cookies|aceitar cookies|aceitar|concordo|permitir tudo|permitir todos|accept all|accept all cookies|accept cookies|accept|i agree|agree|allow all|allow all cookies|got it|ok|entendi|continuar)$/i;
async function dismissCookies() {
  const p = pg();
  const sels = ['#onetrust-accept-btn-handler', '#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll', '#CybotCookiebotDialogBodyButtonAccept', 'button#accept-all', '[id*=cookie] button[id*=accept]', '[class*=cookie] button[class*=accept]'];
  for (const s of sels) { const l = p.locator(s).first(); if (await l.isVisible({ timeout: 150 }).catch(() => false)) { await l.click({ timeout: 1500 }).catch(() => {}); return true; } }
  const btns = p.locator('button, [role=button], a.button, input[type=button], input[type=submit]');
  const n = Math.min(await btns.count().catch(() => 0), 80);
  for (let i = 0; i < n; i++) {
    const b = btns.nth(i);
    const t = ((await b.innerText({ timeout: 100 }).catch(() => '')) || (await b.getAttribute('value').catch(() => '')) || '').trim();
    if (t && t.length < 40 && COOKIE_WORDS.test(t) && await b.isVisible().catch(() => false)) {
      const inBanner = await b.evaluate(e => !!e.closest('[id*=cookie i],[class*=cookie i],[id*=consent i],[class*=consent i],[id*=gdpr i],[class*=gdpr i],[id*=privacy i],[class*=privacy i],[role=dialog],[aria-modal=true]')).catch(() => false);
      if (inBanner) { await b.click({ timeout: 1500 }).catch(() => {}); return true; }
    }
  }
  return false;
}
async function elements() {
  return await pg().evaluate(() => {
    document.querySelectorAll('[data-pb]').forEach(e => e.removeAttribute('data-pb'));
    const sel = 'a[href],button,input,select,textarea,[role=button],[role=link],[role=tab],[role=menuitem],[onclick]';
    const out = []; let n = 1;
    for (const el of document.querySelectorAll(sel)) {
      const r = el.getBoundingClientRect(); const st = getComputedStyle(el);
      if (r.width < 4 || r.height < 4 || st.visibility === 'hidden' || st.display === 'none') continue;
      if (r.bottom < 0 || r.top > innerHeight) continue;
      const label = (el.innerText || el.value || el.placeholder || el.getAttribute('aria-label') || el.title || el.alt || '').trim().replace(/\s+/g, ' ').slice(0, 70);
      if (!label && el.tagName !== 'INPUT') continue;
      el.setAttribute('data-pb', n);
      out.push(`@e${n} ${el.tagName.toLowerCase()}${el.type && el.tagName === 'INPUT' ? '[' + el.type + ']' : ''} ${label}`);
      n++; if (n > 60) break;
    }
    return out;
  });
}
function readIndex() { try { return JSON.parse(fs.readFileSync(INDEX, 'utf8')); } catch { return {}; } }
function cleanup(idx) {
  const now = Date.now(); const files = fs.readdirSync(SHOTS).filter(f => f.endsWith('.jpg')).map(f => [f, fs.statSync(`${SHOTS}/${f}`).mtimeMs]).sort((a, b) => b[1] - a[1]);
  files.forEach(([f, m], i) => { if (i >= MAX_SHOTS || now - m > MAX_AGE_MS) { fs.unlinkSync(`${SHOTS}/${f}`); delete idx[f.replace('.jpg', '')]; } });
}
async function shoot(opts = {}) {
  const name = crypto.randomBytes(9).toString('hex');
  const o = { path: `${SHOTS}/${name}.jpg`, type: 'jpeg', quality: 70 };
  if (opts.full) o.fullPage = true;
  if (opts.clip) o.clip = opts.clip;
  if (opts.el) await opts.el.screenshot({ path: o.path, type: 'jpeg', quality: 80 }); else await pg().screenshot(o);
  const idx = readIndex(); idx[name] = { t: Date.now(), profile: cur.name, url: pg().url(), title: await pg().title().catch(() => ''), conv: process.env.PB_CONV || '' };
  cleanup(idx); fs.writeFileSync(INDEX, JSON.stringify(idx));
  return name;
}
async function snapshot(action, opts = {}) {
  const p = pg();
  await p.waitForLoadState('domcontentloaded', { timeout: 8000 }).catch(() => {});
  await p.waitForTimeout(900);
  const name = await shoot(opts);
  const els = await elements().catch(() => []);
  return `${action}\nPERFIL: ${cur.name}\nURL: ${p.url()}\nTITLE: ${await p.title().catch(() => '')}\nSHOT: ${name}.jpg\nELEMENTOS:\n${els.join('\n')}`;
}
const loc = (t) => /^@e\d+$/.test(t) ? pg().locator(`[data-pb="${t.slice(2)}"]`).first() : null;
const RISKY = /(comprar|finalizar compra|finalizar encomenda|pagar|confirmar (compra|encomenda|pedido|pagamento)|efetuar pagamento|place order|buy now|pay now|checkout|complete purchase|submit order|reservar agora|book now|enviar pedido|submeter|enviar formul|subscrever|subscribe|apagar conta|delete account)/i;
async function riskCheck(l, label, a) {
  if (a.confirm) return null;
  const txt = ((await l.innerText({ timeout: 1000 }).catch(() => '')) || (await l.getAttribute('value').catch(() => '')) || (await l.getAttribute('aria-label').catch(() => '')) || label || '').trim();
  const isSubmit = await l.evaluate(e => (e.tagName === 'BUTTON' || e.tagName === 'INPUT') && (e.type === 'submit') && !!e.form).catch(() => false);
  if (RISKY.test(txt) || RISKY.test(label || '') || (isSubmit && /pagamento|payment|checkout|encomenda|order/i.test(pg().url()))) return txt || label;
  return null;
}
async function extractProducts() {
  return await pg().evaluate(() => {
    const priceRe = /(\d{1,3}(?:[.\s]\d{3})*(?:[.,]\d{1,2})?)\s?(?:€|EUR)|(?:€|EUR)\s?(\d{1,3}(?:[.\s]\d{3})*(?:[.,]\d{1,2})?)/;
    const seen = new Set(), items = [];
    const cands = document.querySelectorAll('article, li, [class*=product i], [class*=card i], [class*=item i], [data-testid*=product i], [data-product-id]');
    for (const c of cands) {
      const t = (c.innerText || '').trim(); if (!t || t.length > 600) continue;
      const m = t.match(priceRe); if (!m) continue;
      const a = c.querySelector('a[href]') || c.closest('a[href]'); if (!a) continue;
      const href = a.href; if (seen.has(href)) continue;
      const heading = c.querySelector('h1,h2,h3,h4,[class*=name i],[class*=title i]');
      const lines = t.split('\n').map(s => s.trim()).filter(Boolean);
      const name = (heading ? heading.innerText : lines.find(l => !priceRe.test(l) && l.length > 2) || lines[0]).replace(/\s+/g, ' ').slice(0, 90);
      const detail = lines.filter(l => !priceRe.test(l) && l !== name && l.length < 80).slice(0, 2).join(' | ');
      seen.add(href); items.push({ nome: name, preco: m[0].replace(/\s+/g, ' '), detalhe: detail, link: href });
      if (items.length >= 25) break;
    }
    return items;
  });
}
const actions = {
  async open({ url }) { if (!/^https?:\/\//.test(url)) url = 'https://' + url; await pg().goto(url, { timeout: 30000, waitUntil: 'domcontentloaded' }); await pg().waitForTimeout(700); const c = await dismissCookies(); return `open ${url}${c ? ' (cookies aceites)' : ''}`; },
  async click(a) {
    const { target } = a; const l = loc(target) || pg().getByText(target, { exact: false }).first();
    const risk = await riskCheck(l, target, a); if (risk) return { confirm: `CONFIRMAÇÃO NECESSÁRIA: "${risk}" parece uma compra/envio. Pergunta ao utilizador; se autorizar repete o comando com --confirm.` };
    await l.click({ timeout: 8000 }); await pg().waitForTimeout(500); await dismissCookies(); return `click ${target}`; },
  async type({ target, text, enter, confirm }) {
    const l = loc(target) || pg().getByPlaceholder(target).first(); await l.fill(text, { timeout: 8000 });
    if (enter) { const isSearch = await l.evaluate(e => !!(e.closest('form') && /search|pesquis|busca/i.test((e.closest('form').action || '') + (e.closest('form').getAttribute('role') || '') + (e.placeholder || '') + (e.type || '')))).catch(() => false);
      const risk = !isSearch && !confirm && /checkout|payment|pagamento|encomenda|order/i.test(pg().url()); if (risk) return { confirm: 'CONFIRMAÇÃO NECESSÁRIA: enviar este formulário de pagamento/encomenda. Pergunta ao utilizador; repete com --confirm.' };
      await l.press('Enter'); }
    return `type ${target}: ${text}`; },
  async key({ key }) { await pg().keyboard.press(key); return `key ${key}`; },
  async scroll({ dir }) { await pg().mouse.wheel(0, dir === 'up' ? -650 : 650); return `scroll ${dir || 'down'}`; },
  async back() { await pg().goBack({ timeout: 8000 }).catch(() => {}); return 'back'; },
  async snap() { return 'snap'; },
  async text() { const t = await pg().evaluate(() => document.body.innerText); return 'TEXT:\n' + t.replace(/\n{3,}/g, '\n\n').slice(0, 6000); },
  async full() { return { snapOpts: { full: true }, msg: 'captura da página inteira' }; },
  async zoom({ target }) { const l = loc(target); if (!l) throw new Error('zoom precisa de @eN'); await l.scrollIntoViewIfNeeded({ timeout: 4000 }); return { snapOpts: { el: l }, msg: `zoom ${target}` }; },
  async extract() {
    const items = await extractProducts();
    if (!items.length) return 'EXTRACT: nenhum produto com preço encontrado (usa "text" ou scroll).\nURL: ' + pg().url();
    const rows = items.map((it, i) => `| ${i + 1} | ${it.nome} | ${it.preco} | ${it.detalhe} | ${it.link} |`);
    return `EXTRACT ${pg().url()}\n| # | Produto | Preço | Detalhe | Link |\n|---|---|---|---|---|\n` + rows.join('\n');
  },
  async compare({ urls }) {
    const out = [];
    for (const u of urls) {
      const p = await cur.ctx.newPage();
      try {
        const url = /^https?:\/\//.test(u) ? u : 'https://' + u;
        await p.goto(url, { timeout: 30000, waitUntil: 'domcontentloaded' }); await p.waitForTimeout(1200);
        const prev = cur.page; cur.page = p; await dismissCookies(); const items = await extractProducts(); const title = await p.title();
        const text = items.length ? '' : (await p.evaluate(() => document.body.innerText)).replace(/\s+/g, ' ').slice(0, 800);
        const shot = await shoot(); cur.page = prev;
        out.push(`### ${title}\n${url}\nSHOT: ${shot}.jpg\n` + (items.length ? items.slice(0, 8).map(i => `- ${i.nome} — ${i.preco} — ${i.link}`).join('\n') : 'Sem produtos detetados. Texto: ' + text));
      } catch (e) { out.push(`### ${u}\nERRO: ${String(e.message).split('\n')[0]}`); } finally { await p.close().catch(() => {}); }
    }
    return 'COMPARE\n' + out.join('\n\n');
  },
  async mouse({ x, y }) { await pg().mouse.click(+x, +y); await pg().waitForTimeout(300); return 'mouse'; },
  async typeraw({ text }) { await pg().keyboard.type(String(text).slice(0, 500)); return 'typeraw'; },
  async close() { await cur.ctx.close(); cur.ctx = null; cur.page = null; return 'close'; },
  async gallery() { const idx = readIndex(); return 'GALERIA: /finance/pbgallery (' + Object.keys(idx).length + ' capturas)'; },
};
http.createServer(async (req, res) => {
  if (req.method === 'GET' && req.url.startsWith('/live.jpg')) {
    try { if (!cur || !cur.page || cur.page.isClosed()) { res.statusCode = 204; return res.end(); }
      const b = await cur.page.screenshot({ type: 'jpeg', quality: 60 });
      res.setHeader('Content-Type', 'image/jpeg'); res.setHeader('X-Url', encodeURIComponent(cur.page.url())); return res.end(b);
    } catch (e) { res.statusCode = 500; return res.end(); }
  }
  let body = ''; for await (const c of req) body += c;
  try {
    const a = JSON.parse(body || '{}'); const fn = actions[a.cmd];
    if (!fn) throw new Error('comando desconhecido: ' + a.cmd);
    const name = safe(a.profile); await ensure(name); cur.name = name;
    let r = await fn(a), snapOpts = {};
    if (r && typeof r === 'object') { if (r.confirm) { res.end(r.confirm); return; } snapOpts = r.snapOpts || {}; r = r.msg; }
    if (['text', 'extract', 'compare', 'gallery', 'mouse', 'typeraw'].includes(a.cmd)) { res.end(r); return; }
    if (a.cmd === 'close') { res.end('fechado'); return; }
    res.end(await snapshot(r, snapOpts));
  } catch (e) {
    let extra = ''; try { if (cur && cur.page && !cur.page.isClosed()) extra = '\n' + await snapshot('ERRO'); } catch {}
    res.statusCode = 500; res.end('ERRO: ' + String(e.message).split('\n')[0] + extra);
  }
}).listen(8794, '127.0.0.1');
