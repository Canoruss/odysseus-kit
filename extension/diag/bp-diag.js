
// Odysseus — diagnóstico Boarding Pass. Cola na consola (F12 > Console) com um chat do Enso aberto.
(async () => {
async function bpFn(op, arg) {
  const vis = (el) => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== 'hidden'; };
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const nameOf = (row) => { const ls = (row.innerText || '').split('\n').map((s) => s.trim()).filter(Boolean); const i = /^[A-Z0-9]{1,3}$/.test(ls[0] || '') ? 1 : 0; return { name: ls[i] || '', key: ls.slice(i, i + 3).join(' | ').slice(0, 200) }; };
  const box = () => { let b = null, best = 0; for (const el of document.querySelectorAll('div,ul,section,main')) { if (el.scrollHeight > el.clientHeight + 40 && el.clientHeight > 150 && /auto|scroll/.test(getComputedStyle(el).overflowY)) { const n = el.querySelectorAll('[role=gridcell]').length; if (n > best) { best = n; b = el; } } } return b; };
  const rows = () => [...document.querySelectorAll('[role=gridcell]')].filter((c) => vis(c) && (c.innerText || '').trim().length > 3 && !c.parentElement.closest('[role=gridcell]'));
  const find = (key) => rows().find((c) => nameOf(c).key === key);
  if (op === 'rows') return rows().sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top).map((c) => nameOf(c)).filter((x) => x.name);
  if (op === 'top' || op === 'scroll') { const b = box(); if (!b) return { moved: false, nobox: true }; const s = b.scrollTop; if (op === 'top') b.scrollTop = 0; else b.scrollBy({ top: b.clientHeight * 0.7, behavior: 'instant' }); await sleep(500); return { moved: b.scrollTop !== s }; }
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
  if (op === 'read') {
    // wait until the opened conversation shows this guest (name present outside the list) and a Boarding Pass row exists
    const name = String(arg || ''), want = 'boarding pass';
    const own = (el) => [...el.childNodes].filter((n) => n.nodeType === 3).map((n) => n.textContent).join(' ').replace(/\s+/g, ' ').trim().toLowerCase();
    let lab = null, opened = false;
    for (let i = 0; i < 30; i++) {
      const outside = [...document.querySelectorAll('body *')].some((el) => !el.closest('[role=gridcell]') && own(el).includes(name.toLowerCase()) && vis(el));
      lab = [...document.querySelectorAll('body *')].find((el) => own(el) === want && vis(el));
      if (outside) opened = true;
      if (opened && lab && i >= 3) break;
      await sleep(250);
    }
    if (!opened) return { ok: false, why: 'open' };
    await sleep(500);
    lab = [...document.querySelectorAll('body *')].find((el) => own(el) === want && vis(el));
    if (!lab) return { ok: false, why: 'nobp' };
    const parse = (c) => { const m = (c || '').match(/rgba?\(([\d.]+)[, ]+([\d.]+)[, ]+([\d.]+)(?:[,/ ]+([\d.]+))?/); return m && (m[4] === undefined || +m[4] > 0.15) ? [+m[1], +m[2], +m[3]] : null; };
    const cname = ([r, g, b]) => {
      const mx = Math.max(r, g, b), mn = Math.min(r, g, b), l = (mx + mn) / 510, sat = mx === mn ? 0 : (mx - mn) / (255 - Math.abs(mx + mn - 255));
      if (sat < 0.22 || mx - mn < 30) return l > 0.9 ? 'white' : l < 0.12 ? 'black' : 'grey';
      let h = mx === r ? ((g - b) / (mx - mn)) % 6 : mx === g ? (b - r) / (mx - mn) + 2 : (r - g) / (mx - mn) + 4; h = (h * 60 + 360) % 360;
      return h < 15 || h >= 345 ? 'red' : h < 45 ? 'orange' : h < 70 ? 'yellow' : h < 170 ? 'green' : h < 200 ? 'teal' : h < 260 ? 'blue' : 'purple';
    };
    const score = (c) => { if (!c) return -1; const n = cname(c); return n === 'white' || n === 'black' ? 0 : n === 'grey' ? 1 : 2; };
    const colourOf = (el, stop) => {
      let best = null, bs = -1; const consider = (c) => { const s = score(c); if (s > bs) { bs = s; best = c; } };
      const nodes = [el, ...el.querySelectorAll('*')].slice(0, 40);
      let p = el.parentElement; for (let i = 0; i < 2 && p && p !== stop && p.getBoundingClientRect().width < 64; i++, p = p.parentElement) nodes.push(p);
      for (const n of nodes) { const cs = getComputedStyle(n); for (const k of ['fill', 'stroke', 'backgroundColor', 'borderTopColor', 'color']) { if ((k === 'fill' || k === 'stroke') && !(n instanceof SVGElement)) continue; if (k === 'borderTopColor' && parseFloat(cs.borderTopWidth) < 1) continue; if (k === 'color' && !(n instanceof SVGElement) && !n.querySelector('svg')) continue; consider(parse(cs[k])); } }
      return best ? cname(best) : 'unknown';
    };
    // Real Enso DOM (saved page 2026-11-23): div[class*=dropdown] > div[class*=header] (label, Unverified chip, ⋮, arrow)
    //   + div[class*=content] (gets a "contentVisible" class when open) > first row of div[class*=chip] = the status circles.
    // Open the dropdown if it is closed, then read the chips in order.
    const dd = lab.closest('[class*=dropdown]');
    const content = dd && [...dd.children].find((c) => /content/i.test(String(c.className)) && !/header/i.test(String(c.className)));
    const chipsOf = () => { if (!content) return []; const a = [...content.querySelectorAll('[class*=chip]')]; return a.filter((x) => !a.some((y) => y !== x && y.contains(x))); };
    const shown = () => chipsOf().filter(vis).length >= 2;
    if (content && !shown()) {
      const hdr = dd.querySelector('[data-testid=inbox-boarding-pass-expand]') || dd.querySelector('[class*=header]') || dd.firstElementChild;
      const arrow = dd.querySelector('[class*=arrow]');
      for (const tgt of [hdr, arrow]) {
        if (!tgt || shown()) continue;
        tgt.click();
        for (let i = 0; i < 16 && !shown(); i++) await sleep(150);
      }
      await sleep(250);
    }
    if (shown()) {
      const chips = chipsOf().filter(vis); const t0 = Math.min(...chips.map((x) => x.getBoundingClientRect().top));
      const line = chips.filter((x) => x.getBoundingClientRect().top < t0 + 12).sort((p, q) => p.getBoundingClientRect().left - q.getBoundingClientRect().left);
      return { ok: true, colours: line.slice(0, 2).map((x) => colourOf(x, content)) };
    }
    if (content) return { ok: false, why: 'closed' };
    // Fallback for other layouts: icons on the line BELOW the label, then same-line icons.
    const lr = lab.getBoundingClientRect();
    const grab = (r) => { let a = [...r.querySelectorAll('svg,img,[class*=icon i],[class*=circle i]')].filter((x) => vis(x) && !x.contains(lab) && !(x.innerText || '').trim() && x.getBoundingClientRect().width < 64 && !(x.parentElement && x.parentElement.closest('svg'))); return a.filter((x) => !a.some((y) => y !== x && y.contains(x))); };
    let row = lab, icons = [], fallback = null;
    for (let i = 0; i < 8 && row.parentElement; i++) {
      row = row.parentElement; if (row.getBoundingClientRect().height > 260) break;
      const all = grab(row);
      const below = all.filter((x) => { const r = x.getBoundingClientRect(); return r.top >= lr.bottom - 2 && r.top < lr.bottom + 120; });
      if (below.length >= 2) { const t0 = Math.min(...below.map((x) => x.getBoundingClientRect().top)); icons = below.filter((x) => x.getBoundingClientRect().top < t0 + 12); break; }
      if (!fallback && all.length >= 3) fallback = all.filter((x) => x.getBoundingClientRect().left > lr.left);
    }
    if (!icons.length && fallback) icons = fallback;
    icons.sort((p, q) => p.getBoundingClientRect().left - q.getBoundingClientRect().left);
    return { ok: true, colours: icons.slice(0, 2).map((x) => colourOf(x, row)) };
  }
  return null;
}

  const cls = (e) => e ? (e.tagName.toLowerCase() + '.' + String(e.className && e.className.baseVal !== undefined ? e.className.baseVal : e.className).split(/\s+/).slice(0,4).join('.')) : null;
  const vis = (el) => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== 'hidden'; };
  const own = (el) => [...el.childNodes].filter((n) => n.nodeType === 3).map((n) => n.textContent).join(' ').replace(/\s+/g, ' ').trim().toLowerCase();
  const out = { url: location.href, when: new Date().toISOString(), size: [innerWidth, innerHeight] };
  try { out.rows = (await bpFn('rows')).slice(0, 5); } catch (e) { out.rowsErr = String(e); }
  const labs = [...document.querySelectorAll('body *')].filter((el) => own(el) === 'boarding pass');
  out.labels = labs.map((l) => ({ el: cls(l), visible: vis(l), chain: (() => { const a = []; let p = l; for (let i = 0; i < 8 && p; i++, p = p.parentElement) a.push(cls(p)); return a; })() }));
  const lab = labs.find(vis) || labs[0];
  const snap = (tag) => {
    const r = { tag };
    if (!lab) return r;
    const dd = lab.closest('[class*=dropdown]'); r.dropdown = cls(dd);
    const host = dd || lab.parentElement?.parentElement?.parentElement;
    if (!host) return r;
    r.children = [...host.children].map((c) => ({ el: cls(c), visible: vis(c), h: Math.round(c.getBoundingClientRect().height) }));
    r.ariaExpanded = [...host.querySelectorAll('[aria-expanded]')].map((e) => cls(e) + '=' + e.getAttribute('aria-expanded'));
    r.testids = [...host.querySelectorAll('[data-testid]')].map((e) => e.getAttribute('data-testid')).slice(0, 30);
    const chips = [...host.querySelectorAll('[class*=chip], svg, [class*=circle], [class*=status], [class*=icon]')].slice(0, 25);
    r.items = chips.map((c) => { const cs = getComputedStyle(c), b = c.getBoundingClientRect(); return { el: cls(c), vis: vis(c), x: Math.round(b.left), y: Math.round(b.top), w: Math.round(b.width), h: Math.round(b.height), bg: cs.backgroundColor, color: cs.color, fill: cs.fill, border: cs.borderTopColor + ' ' + cs.borderTopWidth, text: (c.textContent || '').trim().slice(0, 30) }; });
    r.html = host.outerHTML.replace(/\s+/g, ' ').slice(0, 6000);
    return r;
  };
  out.before = snap('antes');
  const name = (out.rows && out.rows[0] && out.rows[0].name) || '';
  try { out.read = await bpFn('read', name); } catch (e) { out.readErr = String(e && e.stack || e); }
  out.after = snap('depois do read');
  const txt = JSON.stringify(out, null, 1);
  console.log(txt);
  try { copy(txt); console.log('%c✔ Copiado. Cola no chat do Odysseus.', 'color:green;font-size:16px'); }
  catch { console.log('Copia o texto acima e cola no chat.'); }
})();
