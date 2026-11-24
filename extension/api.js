// All authenticated requests pass through one origin-checked transport.
export const DEFAULTS = { url: '', token: '', endpointId: '', model: '', profileId: '', insecureHttpOrigin: '' };
export const getCfg = () => chrome.storage.local.get(DEFAULTS);
export const scopeOf = c => JSON.stringify([c.url, c.profileId, c.endpointId, c.model]);

export class Problem extends Error {
  constructor(code, status = 0) { super(code); this.code = code; this.status = status; }
}

export function address(raw) {
  let u;
  try { u = new URL(String(raw).trim()); } catch { throw new Problem('invalidUrl'); }
  if (!['https:', 'http:'].includes(u.protocol) || !u.hostname || u.hostname.includes('*') || u.username || u.password || /[?#]/.test(u.href)) throw new Problem('invalidUrl');
  const loopback = u.hostname === 'localhost' || u.hostname.endsWith('.localhost') || u.hostname === '[::1]' || /^127\./.test(u.hostname) && /^\d+\.\d+\.\d+\.\d+$/.test(u.hostname);
  return { base: u.href.replace(/\/+$/, ''), origin: u.origin, pattern: u.origin + '/*', needsOptIn: u.protocol === 'http:' && !loopback };
}
export function validate(c) {
  if (!c.url || !c.token?.trim()) throw new Problem('setup');
  const server = address(c.url);
  if (server.needsOptIn && c.insecureHttpOrigin !== server.origin) throw new Problem('httpConsent');
  return server;
}
export async function hasPerm(c) {
  return chrome.permissions.contains({ origins: [validate(c).pattern] });
}

const EVENT_LIMIT = 1024 * 1024;
const REPLY_LIMIT = 256 * 1024;
// SSE lines can end in LF, CRLF or CR. A chunk may split either a line ending or a Unicode character.
export async function readEvents(stream, onEvent, activity = () => {}) {
  if (!stream) throw new Problem('badResponse');
  const reader = stream.getReader(), decoder = new TextDecoder();
  let lineBuffer = '', skipLF = false, data = [], size = 0, event = '', ended = false;
  function dispatch() {
    if (data.length) {
      const raw = data.join('\n');
      if (raw.trim() === '[DONE]') ended = true;
      else if (raw.trim()) {
        let value;
        try { value = JSON.parse(raw); } catch { throw new Problem('badStream'); }
        if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Problem('badStream');
        onEvent(value, event);
      }
    }
    data = []; size = 0; event = '';
  }
  function line(s) {
    if (!s) { dispatch(); return; }
    const sep = s.indexOf(':');
    const key = sep < 0 ? s : s.slice(0, sep);
    const value = sep < 0 ? '' : s.slice(sep + 1).replace(/^ /, '');
    if (key === 'data') {
      size += value.length + 1;
      if (size > EVENT_LIMIT) throw new Problem('tooLarge');
      data.push(value);
    } else if (key === 'event') event = value;
  }
  function feed(chunk) {
    if (!chunk) return;
    if (skipLF && chunk.startsWith('\n')) chunk = chunk.slice(1);
    skipLF = false;
    const parts = chunk.split(/(\r\n|\r|\n)/);
    for (let i = 0; i < parts.length && !ended; i += 2) {
      lineBuffer += parts[i];
      if (lineBuffer.length > EVENT_LIMIT) throw new Problem('tooLarge');
      if (i + 1 < parts.length) { line(lineBuffer); lineBuffer = ''; }
    }
    skipLF = chunk.endsWith('\r');
  }
  try {
    while (!ended) {
      const { done, value } = await reader.read();
      if (done) { feed(decoder.decode()); if (lineBuffer) line(lineBuffer); if (!ended) dispatch(); break; }
      activity(); feed(decoder.decode(value, { stream: true }));
    }
  } finally {
    try { await reader.cancel(); } catch { /* Already closed or aborted. */ }
    reader.releaseLock();
  }
  return ended;
}

async function request(c, path, options, consume, signal, timeout = 90000) {
  const server = validate(c);
  signal?.throwIfAborted();
  const controller = new AbortController();
  const abort = () => controller.abort(signal.reason);
  signal?.addEventListener('abort', abort, { once: true });
  let timer;
  const touch = () => { clearTimeout(timer); timer = setTimeout(() => controller.abort(new Problem('timeout')), timeout); };
  touch();
  try {
    const r = await fetch(server.base + path, { ...options, headers: { ...options.headers, Authorization: 'Bearer ' + c.token }, signal: controller.signal, redirect: 'error', credentials: 'omit', referrerPolicy: 'no-referrer', cache: 'no-store' });
    if (!r.ok) { await r.body?.cancel(); throw new Problem(r.status === 401 || r.status === 403 ? 'auth' : r.status === 429 ? 'rateLimit' : 'httpError', r.status); }
    return await consume(r, touch);
  } catch (e) {
    if (controller.signal.aborted) throw controller.signal.reason;
    if (e instanceof Problem) throw e;
    throw new Problem(e instanceof SyntaxError ? 'badResponse' : 'network');
  } finally { clearTimeout(timer); signal?.removeEventListener('abort', abort); }
}

async function json(r) {
  // Bound metadata as well as streams. A misconfigured proxy may serve a whole HTML page.
  if (!r.body) throw new Problem('badResponse');
  const reader = r.body.getReader(), decoder = new TextDecoder();
  let size = 0, body = '';
  try {
    for (;;) {
      const chunk = await reader.read(); if (chunk.done) break;
      size += chunk.value.byteLength; if (size > EVENT_LIMIT) throw new Problem('tooLarge');
      body += decoder.decode(chunk.value, { stream: true });
    }
    return JSON.parse(body + decoder.decode());
  } finally { try { await reader.cancel(); } catch {} reader.releaseLock(); }
}
const isId = v => (typeof v === 'string' && v.trim().length > 0 && v.length <= 512) || Number.isSafeInteger(v);

export async function newSession(c, signal) {
  const body = new FormData(); body.set('name', 'Odysseus extension');
  if (c.endpointId) body.set('endpoint_id', c.endpointId);
  if (c.model) body.set('model', c.model);
  const result = await request(c, '/api/session', { method: 'POST', body }, json, signal, 30000);
  if (!isId(result?.id)) throw new Problem('badSession');
  return result.id;
}
export async function upload(c, file, name, sid, signal) {
  const body = new FormData(); body.set('files', file, name); body.set('session_id', sid);
  const result = await request(c, '/api/upload', { method: 'POST', body }, json, signal);
  if (!Array.isArray(result?.files) || !result.files.length) throw new Problem('badUpload');
  const ids = result.files.map(f => f?.id);
  if (!ids.every(isId)) throw new Problem('badUpload');
  return ids;
}
export async function listModels(c, signal) {
  const d = await request(c, '/api/models', {}, json, signal, 15000);
  if (!Array.isArray(d?.items)) throw new Problem('badModels');
  const out = [], seen = new Set();
  for (const it of d.items) {
    if (!Array.isArray(it?.models)) continue;
    const ep = String(it.id ?? it.endpoint_id ?? '');
    for (const [i, model] of it.models.entries()) {
      if (typeof model !== 'string' || !model || model.length > 512) continue;
      const key = JSON.stringify([ep, model]); if (seen.has(key)) continue;
      const display = it.models_display?.[i];
      if (out.length >= 500) return out;
      seen.add(key); out.push({ ep, model, label: typeof display === 'string' && display ? display.slice(0, 200) : model });
    }
  }
  return out;
}
export async function advertisedVersion(c, signal) {
  const data = await request(c, '/agent/version', {}, json, signal, 15000);
  const version = data?.version;
  if (typeof version !== 'string' || !/^(?:0|[1-9]\d{0,4})(?:\.(?:0|[1-9]\d{0,4})){0,3}$/.test(version) || version.split('.').some(n => Number(n) > 65535)) throw new Problem('badResponse');
  return version;
}
export async function pullCommands(c) {
  const data = await request(c, '/agent/cmd', {}, json, undefined, 15000);
  return Array.isArray(data?.cmds) ? data.cmds : [];
}
export function isNewer(candidate, installed) {
  const a = candidate.split('.').map(Number), b = installed.split('.').map(Number);
  for (let i = 0; i < 4; i++) {
    const difference = (a[i] || 0) - (b[i] || 0);
    if (difference) return difference > 0;
  }
  return false;
}
async function streamReply(c, path, options, onText, signal, isGuide = false) {
  let text = '', calls = [], final = false;
  await request(c, path, options, async (r, touch) => {
    const ended = await readEvents(r.body, (ev, eventName) => {
      const kind = ev.type || eventName;
      if (ev.error || kind === 'error') throw new Problem('serverStream');
      if (isGuide && Array.isArray(ev.tool_calls)) calls = ev.tool_calls.slice(0, 5);
      let next, appended;
      if (kind === 'final_response' && typeof ev.content === 'string') { next = ev.content; final = true; }
      else if (!final && (!kind || ['message', 'delta', 'text_delta', 'content_delta', 'content_block_delta', 'token'].includes(kind))) {
        const delta = typeof ev.delta === 'string' ? ev.delta : ev.delta?.text;
        if (typeof delta === 'string' && delta) { appended = delta; next = text + delta; }
      }
      if (next !== undefined) {
        if (next.length > REPLY_LIMIT) throw new Problem('tooLarge');
        text = next; onText?.(text, appended);
      }
    }, touch);
    if (!ended && !final && !calls.length && text) throw new Problem('incomplete');
  }, signal);
  if (!text.trim() && !calls.length) throw new Problem('emptyReply');
  return { text, calls };
}
export async function chat(c, sid, message, attachments, onText, signal) {
  const body = new FormData(); body.set('session', sid); body.set('message', message);
  if (attachments?.length) body.set('attachments', JSON.stringify(attachments));
  return (await streamReply(c, '/api/chat_stream', { method: 'POST', body }, onText, signal)).text;
}
export async function agentModels(c) {
  const d = await request(c, '/agent/models', {}, json, undefined, 15000);
  return Array.isArray(d?.models) ? d.models.filter(m => typeof m?.id === 'string' && typeof m?.label === 'string') : [];
}
export async function agentLook(c, image, question, signal) {
  return request(c, '/agent/look', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ image, question }) }, async (r) => r.json(), signal, 70000);
}
export async function agentStep(c, messages, tools, onText, signal) {
  const { agentModel } = await chrome.storage.local.get('agentModel');
  return streamReply(c, '/agent/step', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ messages, tools, model: agentModel || 'auto' }) }, onText, signal, true);
}
