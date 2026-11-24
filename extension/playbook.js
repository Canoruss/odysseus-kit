// Recipes ("playbooks") and site notes: learned by the model once, replayed without the model later.
// A recipe step stores WHAT to find (tag, label, data-testid, role), never coordinates or element ids.
const norm = (s) => String(s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9 ]+/g, ' ').split(/\s+/).filter((w) => w.length > 2);
export function sim(a, b) {
  const A = new Set(norm(a)), B = new Set(norm(b)); if (!A.size || !B.size) return 0;
  let i = 0; for (const x of A) if (B.has(x)) i++;
  return i / (A.size + B.size - i);
}
export const hostOf = (url) => { try { return new URL(url).hostname.replace(/^www\./, ''); } catch { return ''; } };
export const RISKY = /\b(send|enviar|delete|apagar|eliminar|remove|remover|pay|pagar|submit|confirm|confirmar|cancel|cancelar|save|guardar|publish|publicar|buy|comprar|checkout|refund|reembolsar|approve|aprovar)\b/i;
export const RECORDABLE = ['click', 'type', 'select', 'key', 'scroll', 'goto', 'newtab', 'search', 'back', 'wait', 'extract'];
export const locOf = (el) => ({ tag: el.tag, label: el.label, testid: el.testid, role: el.role });
export function findEl(els, loc) {
  const L = (s) => String(s || '').trim().toLowerCase(), want = L(loc.label);
  if (loc.testid) {
    const m = els.filter((e) => e.testid === loc.testid);
    const exact = m.find((e) => L(e.label) === want);
    if (exact) return exact;
    if (m.length === 1) return m[0];
  }
  const same = els.filter((e) => e.tag === loc.tag);
  const exact = same.find((e) => L(e.label) === want);
  if (exact) return exact;
  if (want.length >= 4) {
    const part = same.filter((e) => e.label.length >= 4 && (L(e.label).includes(want) || want.includes(L(e.label))));
    if (part.length === 1) return part[0];
  }
  if (want.length > 30) { // long labels (chat rows) contain changing previews: match on the stable start (the name)
    const head = want.slice(0, 18), part = same.filter((e) => L(e.label).startsWith(head));
    if (part.length >= 1) return part[0];
  }
  return null;
}
async function load() { return (await chrome.storage.local.get('playbooks')).playbooks || {}; }
export async function findPlaybook(host, goal) {
  const list = (await load())[host] || []; let best = null, bs = 0;
  for (const p of list) { const s = sim(p.goal, goal); if (s > bs) { bs = s; best = p; } }
  return bs >= 0.75 ? best : null;
}
export async function savePlaybook(host, goal, steps) {
  const all = await load(), list = all[host] || [], old = list.findIndex((p) => sim(p.goal, goal) >= 0.75);
  const pb = { goal, steps, runs: 0, fails: 0, saved: new Date().toISOString().slice(0, 10) };
  if (old >= 0) list[old] = pb; else list.push(pb);
  all[host] = list.slice(-10); await chrome.storage.local.set({ playbooks: all });
}
export async function markPlaybook(host, pb, ok) {
  const all = await load(), list = all[host] || [], i = list.findIndex((p) => p.goal === pb.goal);
  if (i < 0) return 0;
  let dropped = 0;
  if (ok) { list[i].runs++; list[i].fails = 0; } else if (++list[i].fails >= 2) { list.splice(i, 1); dropped = 1; }
  all[host] = list; await chrome.storage.local.set({ playbooks: all }); return dropped;
}
export async function getNotes(host) { return ((await chrome.storage.local.get('siteNotes')).siteNotes || {})[host] || []; }
export async function addNote(host, note) {
  const all = (await chrome.storage.local.get('siteNotes')).siteNotes || {}, list = all[host] || [], n = String(note || '').replace(/\s+/g, ' ').trim().slice(0, 300);
  if (!n || list.some((x) => sim(x, n) >= 0.8)) return;
  list.push(n); all[host] = list.slice(-12); await chrome.storage.local.set({ siteNotes: all });
}
