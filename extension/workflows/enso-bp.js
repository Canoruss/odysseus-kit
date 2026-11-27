// Optional Domain Workflow: Enso Connect Boarding Pass deterministic batch audit.
// Extracted from core agent loop to keep Odysseus site-agnostic while preserving 100% backward compatibility.
import { domEngine } from '../dom-engine.js';
import { t, lang } from '../i18n.js';

const sleep = ms => new Promise(r => setTimeout(r, ms));

export function matchesEnsoAuditGoal(goal) {
  return /boarding|embarque/i.test(goal) && /\b(circles?|c[ií]rculos?|enter details|id upload|verific\w*|check\w*|audit\w*|todos|all|every)\b/i.test(goal);
}

export async function findEnsoTab(currentTab) {
  if (/ensoconnect/.test(currentTab?.url || '')) return currentTab;
  const found = await chrome.tabs.query({ url: '*://*.ensoconnect.com/*' });
  return found[0] || null;
}

export async function bpFn(op, arg) {
  const vis = (el) => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== 'hidden'; };
  const delay = (ms) => new Promise((r) => setTimeout(r, ms));
  const nameOf = (row) => { const ls = (row.innerText || '').split('\n').map((s) => s.trim()).filter(Boolean); const i = /^[A-Z0-9]{1,3}$/.test(ls[0] || '') ? 1 : 0; return { name: ls[i] || '', key: ls.slice(i, i + 3).join(' | ').slice(0, 200) }; };
  const box = () => { let b = null, best = 0; for (const el of document.querySelectorAll('div,ul,section,main')) { if (el.scrollHeight > el.clientHeight + 40 && el.clientHeight > 150 && /auto|scroll/.test(getComputedStyle(el).overflowY)) { const n = el.querySelectorAll('[role=gridcell]').length; if (n > best) { best = n; b = el; } } } return b; };
  const rows = () => [...document.querySelectorAll('[role=gridcell]')].filter((c) => vis(c) && (c.innerText || '').trim().length > 3 && !c.parentElement.closest('[role=gridcell]'));
  const find = (key) => rows().find((c) => nameOf(c).key === key);
  if (op === 'rows') return rows().sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top).map((c) => nameOf(c)).filter((x) => x.name);
  if (op === 'top' || op === 'scroll') { const b = box(); if (!b) return { moved: false, nobox: true }; const s = b.scrollTop; if (op === 'top') b.scrollTop = 0; else b.scrollBy({ top: b.clientHeight * 0.7, behavior: 'instant' }); await delay(450); return { moved: b.scrollTop !== s }; }
  if (op === 'click' || op === 'rect') {
    const c = find(arg); if (!c) return { ok: false };
    c.scrollIntoView({ block: 'nearest' }); const t = c.firstElementChild || c, r = t.getBoundingClientRect();
    const x = r.left + Math.min(r.width / 2, 120), y = r.top + r.height / 2;
    if (op === 'rect') return { ok: true, x, y };
    const o = { bubbles: true, cancelable: true, view: window, clientX: x, clientY: y, button: 0 };
    const tgt = document.elementFromPoint(x, y) || t;
    for (const ty of ['pointerdown', 'mousedown', 'pointerup', 'mouseup']) tgt.dispatchEvent(new (ty.startsWith('pointer') ? PointerEvent : MouseEvent)(ty, o));
    tgt.click(); return { ok: true };
  }
  if (op === 'steps') {
    const name = String(arg || '').toLowerCase();
    const own = (el) => [...el.childNodes].filter((n) => n.nodeType === 3).map((n) => n.textContent).join(' ').replace(/\s+/g, ' ').trim().toLowerCase();
    const hdr = () => [...document.querySelectorAll('[data-testid=inbox-boarding-pass-expand]')].find(vis);
    let opened = false, h = null;
    for (let i = 0; i < 80; i++) {
      if (!opened) opened = [...document.querySelectorAll('body *')].some((el) => !el.closest('[role=gridcell]') && own(el).includes(name) && vis(el));
      h = hdr();
      if (opened && h && i >= 2) break;
      if (!opened && i >= 30) break;
      await delay(250);
    }
    if (!opened) return { ok: false, why: 'open' };
    if (!h) return { ok: false, why: 'nobp' };
    await delay(250); h = hdr() || h;
    const dd = h.closest('[class*=dropdown]') || h.parentElement.parentElement.parentElement;
    const stat = () => [...dd.querySelectorAll('[data-testid^="inbox-bp-step-status-"]')].filter(vis);
    if (stat().length < 2) {
      const arrow = dd.querySelector('[class*=arrow]');
      for (const tgt of [arrow, h, h.querySelector('p')]) {
        if (!tgt || stat().length >= 2) continue;
        const r = tgt.getBoundingClientRect(), o = { bubbles: true, cancelable: true, view: window, clientX: r.left + r.width / 2, clientY: r.top + r.height / 2, button: 0 };
        for (const ty of ['pointerdown', 'mousedown', 'pointerup', 'mouseup']) tgt.dispatchEvent(new (ty.startsWith('pointer') ? PointerEvent : MouseEvent)(ty, o));
        tgt.click();
        for (let i = 0; i < 20 && stat().length < 2; i++) await delay(150);
      }
    }
    const st = stat();
    if (st.length < 2) return { ok: false, why: 'closed' };
    const steps = {};
    for (const el of st) steps[el.getAttribute('data-testid').replace('inbox-bp-step-status-', '').trim()] = (el.innerText || '').replace(/\s+/g, ' ').trim().toLowerCase();
    const badge = (dd.querySelector('[data-testid=inbox-boarding-pass-expand] [class*=chip]')?.innerText || '').trim();
    return { ok: true, steps, badge };
  }
  return null;
}

export async function runEnsoBpAudit(tabId, signal, ui, cdpClick) {
  const run = async (op, arg) => (await chrome.scripting.executeScript({ target: { tabId }, func: bpFn, args: [op, arg ?? null] }))[0].result;
  const realClick = async (key) => {
    const p = await run('rect', key);
    if (!p?.ok) return false;
    return cdpClick(tabId, p.x, p.y);
  };
  try { await chrome.scripting.executeScript({ target: { tabId }, func: domEngine, args: ['banner', { on: true, label: t('working'), stopLabel: t('stop') }] }); } catch {}
  const seen = new Set(), bad = [], unk = [], good = [];
  let stuck = 0;
  const pt = lang() === 'pt-PT';
  try {
    ui.step('▸ ' + t('bpAuditStart'));
    try {
      await chrome.scripting.executeScript({
        target: { tabId },
        func: () => {
          const b = [...document.querySelectorAll('button,[role=tab],a')].find((e) => /^\s*resolved\b/i.test(e.innerText || ''));
          if (b) b.click();
          return !!b;
        }
      });
      await sleep(1200);
    } catch {}
    await run('top');
    while (seen.size < 400) {
      signal.throwIfAborted();
      const rows = (await run('rows')) || [], fresh = rows.filter((r) => !seen.has(r.key));
      if (!fresh.length) { const s = await run('scroll'); if (!s?.moved && ++stuck >= 2) break; continue; }
      stuck = 0;
      for (const r of fresh) {
        signal.throwIfAborted(); seen.add(r.key);
        ui.step('▸ ' + seen.size + '. ' + r.name);
        await run('click', r.key);
        let res = await run('steps', r.name);
        if (!res?.ok && res?.why === 'open' && await realClick(r.key)) res = await run('steps', r.name);
        if (!res?.ok) {
          unk.push(r.name + ' — ' + (res?.why === 'nobp' ? t('bpNoPass') : res?.why === 'closed' ? t('bpClosed') : t('bpNoChat')));
          continue;
        }
        const want = ['Enter details', 'Id upload'], get = (k) => res.steps[Object.keys(res.steps).find((x) => x.toLowerCase() === k.toLowerCase())] || '?';
        const sn = (v) => pt ? ({ complete: 'Completo', active: 'Ativo', incomplete: 'Incompleto', disabled: 'Desativado' }[v] || v) : v.charAt(0).toUpperCase() + v.slice(1);
        const line = want.map((k) => k + ': ' + sn(get(k))).join(', ');
        ui.step('   ' + line);
        if (want.every((k) => get(k) === 'complete')) good.push(r.name + ' — ' + line); else bad.push(r.name + ' — ' + line);
      }
    }
    const L = [pt ? `**Verificados ${seen.size} hóspedes:** ${good.length} OK (Enter details e Id upload Completos), ${bad.length} em falta.` : `**Checked ${seen.size} guests:** ${good.length} OK (Enter details and Id upload Complete), ${bad.length} missing.`];
    L.push('', pt ? '**Em falta:**' : '**Missing:**', ...(bad.length ? bad.map((x) => '- ' + x) : [pt ? '- nenhum' : '- none']));
    L.push('', '**OK:**', ...(good.length ? good.map((x) => '- ' + x) : [pt ? '- nenhum' : '- none']));
    if (unk.length) L.push('', pt ? '**Não verificados:**' : '**Not verified:**', ...unk.map((x) => '- ' + x));
    ui.final(L.join('\n'));
  } finally {
    try { await chrome.scripting.executeScript({ target: { tabId }, func: domEngine, args: ['banner', { on: false }] }); } catch {}
  }
}
