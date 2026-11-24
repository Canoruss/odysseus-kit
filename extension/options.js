import { address, advertisedVersion, getCfg, isNewer, listModels, Problem, validate } from './api.js';
import { saveHandle, getHandle, isExtDir } from './updater.js';
import { applyI18n, t, explain } from './i18n.js';
applyI18n();
const $ = id => document.getElementById(id);
const installed = chrome.runtime.getManifest().version;
$('version').textContent = `Odysseus ${installed}`;
let saved = await getCfg(), consentOrigin = '', editing = false;
const status = (msg, error = false) => { $('st').textContent = msg; $('st').classList.toggle('error', error); };
function refresh() {
  let server, old;
  try { server = address($('url').value); } catch {}
  try { old = address(saved.url); } catch {}
  if (server?.origin !== consentOrigin) {
    consentOrigin = server?.origin || '';
    $('allowHttp').checked = !!server && consentOrigin === saved.insecureHttpOrigin;
  }
  $('httpRow').hidden = !server?.needsOptIn;
  $('disconnect').hidden = !saved.token;
  $('token').placeholder = saved.token && server?.base === old?.base ? t('keepToken') : t('enterToken');
}
$('url').value = saved.url; $('ep').value = saved.endpointId; $('model').value = saved.model; refresh();
$('url').addEventListener('input', refresh);
function fromForm() {
  const server = address($('url').value);
  let same = false; try { same = server.base === address(saved.url).base; } catch {}
  const c = { url: server.base, token: $('token').value.trim() || (same ? saved.token : ''), endpointId: $('ep').value.trim(), model: $('model').value.trim(), insecureHttpOrigin: server.needsOptIn && $('allowHttp').checked ? server.origin : '' };
  if (!c.token) throw new Problem('needToken');
  validate(c); return { server, c };
}
async function currentSettings() {
  const current = await getCfg();
  if (Object.keys(current).some(key => current[key] !== saved[key])) throw new Problem('settingsChanged');
  return current;
}
async function handle(action) {
  if (editing) return;
  editing = true;
  let temporary;
  try {
    const { server, c } = fromForm();
    // Request during the click, before doing asynchronous work.
    if (!await chrome.permissions.request({ origins: [server.pattern] })) throw new Problem('denied');
    temporary = server.pattern;
    for (const node of $('settingsForm').elements) node.disabled = true;
    await currentSettings();
    if (action !== 'save') {
      if (action === 'version') {
        status(t('checkingVersion'));
        const version = await advertisedVersion(c);
        const newer = isNewer(version, installed);
        status(`${t('serverVersion')} ${version}. ${t(newer ? 'updateManual' : 'upToDate')}`);
        return;
      }
      status(t('testing'));
      await listModels(c); status(t('testOk')); return;
    }
    const unchanged = Object.entries(c).every(([key, value]) => value === saved[key]);
    c.profileId = unchanged && saved.profileId ? saved.profileId : crypto.randomUUID();
    await chrome.storage.local.setAccessLevel({ accessLevel: 'TRUSTED_CONTEXTS' });
    await chrome.storage.local.set(c); saved = c; temporary = null;
    $('token').value = ''; refresh();
    const { origins = [] } = await chrome.permissions.getAll();
    const stale = origins.filter(p => p !== server.pattern);
    if (stale.length) await chrome.permissions.remove({ origins: stale });
    status(t('saved'));
  } catch (e) { status(action !== 'save' && [404, 405, 501].includes(e.status) ? t(action === 'version' ? 'noVersion' : 'modelApiMissing') : explain(e), true); }
  finally {
    try {
      if (temporary) {
        const current = await getCfg(); let keep; try { if (current.token) keep = address(current.url).pattern; } catch {}
        if (keep !== temporary) await chrome.permissions.remove({ origins: [temporary] });
      }
    } finally { editing = false; for (const node of $('settingsForm').elements) node.disabled = false; }
  }
}
$('settingsForm').onsubmit = ev => { ev.preventDefault(); handle('save'); };
$('test').onclick = () => { if ($('settingsForm').reportValidity()) handle('test'); };

$('checkVersion').onclick = () => { if ($('settingsForm').reportValidity()) handle('version'); };

$('disconnect').onclick = async () => {
  if (editing) return;
  editing = true;
  try {
    const current = await currentSettings();
    const patch = { token: '', profileId: crypto.randomUUID(), insecureHttpOrigin: '' };
    await chrome.storage.local.set(patch);
    saved = { ...current, ...patch };
    $('token').value = ''; consentOrigin = ''; refresh();
    const { origins = [] } = await chrome.permissions.getAll();
    if (origins.length) await chrome.permissions.remove({ origins });
    status(t('forgotToken'));
  } catch (e) { status(explain(e), true); }
  finally { editing = false; }
};

(async () => { if (await getHandle()) $('upd').textContent = t('u_on2') + ' ✓'; })();
$('upd').onclick = async () => {
  try {
    const h = await showDirectoryPicker({ mode: 'readwrite', id: 'odysseus-ext' });
    if (!(await isExtDir(h))) { status(t('u_bad'), true); return; }
    await saveHandle(h); $('upd').textContent = t('u_on2') + ' ✓'; status(t('u_on2'));
  } catch (e) { if (e.name !== 'AbortError') status(t('u_fail') + ': ' + e.message, true); }
};
