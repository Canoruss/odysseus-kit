// Self-update: downloads the new files from the server and writes them into the user's extension folder.
import { address, getCfg, isNewer } from './api.js';
const base = (c) => address(c.url).base;
const DB = 'ody-upd', ST = 'h';
function db() { return new Promise((res, rej) => { const r = indexedDB.open(DB, 1); r.onupgradeneeded = () => r.result.createObjectStore(ST); r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error); }); }
export async function saveHandle(h) { const d = await db(); return new Promise((res, rej) => { const q = d.transaction(ST, 'readwrite').objectStore(ST).put(h, 'dir'); q.onsuccess = res; q.onerror = () => rej(q.error); }); }
export async function getHandle() { const d = await db(); return new Promise((res) => { const q = d.transaction(ST).objectStore(ST).get('dir'); q.onsuccess = () => res(q.result || null); q.onerror = () => res(null); }); }
export async function isExtDir(h) {
  try { const f = await (await h.getFileHandle('manifest.json')).getFile(); const m = JSON.parse(await f.text()); const key = chrome.runtime.getManifest().key; return typeof key === 'string' && key.length > 0 && m.key === key; } catch { return false; }
}
// Returns {version, files} when the server has a newer version, else null.
export async function checkUpdate() {
  const c = await getCfg(); if (!c.url || !c.token) return null;
  const r = await fetch(base(c) + '/agent/version', { headers: { Authorization: 'Bearer ' + c.token }, cache: 'no-store' });
  if (!r.ok) return null; const m = await r.json();
  return typeof m.version === 'string' && isNewer(m.version, chrome.runtime.getManifest().version) ? m : null;
}
export async function canWrite(h) { return h && (await h.queryPermission({ mode: 'readwrite' })) === 'granted'; }
// Downloads everything first, then writes (manifest last) and reloads. Needs a user gesture if permission must be asked.
export async function applyUpdate(m, ask) {
  const h = await getHandle(); if (!h) throw new Error('no folder');
  if (!(await canWrite(h))) { if (!ask || (await h.requestPermission({ mode: 'readwrite' })) !== 'granted') throw new Error('permission'); }
  if (!(await isExtDir(h))) throw new Error('wrong folder');
  const c = await getCfg(), got = [];
  for (const f of m.files) {
    const r = await fetch(base(c) + '/agent/ext/' + f, { headers: { Authorization: 'Bearer ' + c.token }, cache: 'no-store' });
    if (!r.ok) throw new Error(f + ' ' + r.status);
    const blob = await r.blob();
    if (!f.endsWith('.json')) { const t = (await blob.slice(0, 40).text()).trimStart(); if (/^\{\s*"(ok|error)"/.test(t)) throw new Error(f + ' bad content'); }
    got.push([f, blob]);
  }
  got.sort((a, b) => (a[0] === 'manifest.json') - (b[0] === 'manifest.json'));
  for (const [f, blob] of got) {
    const parts = f.split('/'); let d = h;
    for (const p of parts.slice(0, -1)) d = await d.getDirectoryHandle(p, { create: true });
    const w = await (await d.getFileHandle(parts.at(-1), { create: true })).createWritable(); await w.write(blob); await w.close();
  }
  await chrome.storage.local.set({ justUpdated: m.version });
  chrome.runtime.reload();
}
