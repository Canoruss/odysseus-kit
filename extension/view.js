import { t } from './i18n.js';

export function el(tag, cls, text) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = text;
  return node;
}
export function button(text, fn, cls) {
  const b = el('button', cls, text); b.type = 'button'; b.addEventListener('click', fn); return b;
}
function inline(node, text) {
  const re = /`([^`\n]+)`|\*\*([^*\n]+)\*\*|\[([^\]\n]{1,500})\]\((https?:\/\/[^\s)]+)\)/g;
  let pos = 0;
  for (const m of text.matchAll(re)) {
    node.append(text.slice(pos, m.index)); pos = m.index + m[0].length;
    if (m[1] || m[2]) node.append(el(m[1] ? 'code' : 'strong', '', m[1] || m[2]));
    else {
      let url; try { url = new URL(m[4]); } catch {}
      if (url && ['https:', 'http:'].includes(url.protocol) && !url.username && !url.password) {
        const a = el('a', '', m[3]); a.href = url.href; a.title = url.href; a.target = '_blank'; a.rel = 'noopener noreferrer'; node.append(a);
      } else node.append(m[0]);
    }
  }
  node.append(text.slice(pos));
}
// Render untrusted Markdown as nodes. Code and raw HTML remain literal text.
export function markdown(text) {
  const frag = document.createDocumentFragment();
  let paragraph = [], list, code = null, language;
  function flush() { if (paragraph.length) { const p = el('p'); inline(p, paragraph.join('\n')); frag.append(p); paragraph = []; } }
  function finishCode() {
    const box = el('div', 'code-block'), top = el('div', 'code-head');
    if (language) top.append(el('span', '', language));
    const raw = code.join('\n'); top.append(copyButton(raw, 'copyCode'));
    const pre = el('pre'); pre.append(el('code', '', raw)); box.append(top, pre); frag.append(box); code = null;
  }
  for (const line of String(text).split(/\r?\n/)) {
    if (code !== null) { if (/^\s*```\s*$/.test(line)) finishCode(); else code.push(line); continue; }
    const fence = /^\s*```([^`\s]{0,32})\s*$/.exec(line);
    if (fence) { flush(); list = null; code = []; language = fence[1]; continue; }
    if (!line.trim()) { flush(); list = null; continue; }
    const item = /^\s*(?:([-*])|(\d{1,5})\.)\s+(.*)$/.exec(line);
    if (item) {
      flush(); const tag = item[1] ? 'ul' : 'ol';
      if (list?.localName !== tag) { list = el(tag); if (tag === 'ol') list.start = Number(item[2]); frag.append(list); }
      const li = el('li'); inline(li, item[3]); list.append(li); continue;
    }
    list = null;
    const heading = /^(#{1,4})\s+(.*)$/.exec(line);
    if (heading) { flush(); const h = el('h' + Math.min(heading[1].length + 2, 6)); inline(h, heading[2]); frag.append(h); }
    else paragraph.push(line);
  }
  flush(); if (code !== null) finishCode(); return frag;
}
export function copyButton(text, key = 'copy') {
  const b = button(t(key), async () => {
    try { await navigator.clipboard.writeText(text); b.textContent = t('copied'); }
    catch { b.textContent = t('copyFail'); }
    setTimeout(() => { b.textContent = t(key); }, 2000);
  }, 'text-button');
  return b;
}
