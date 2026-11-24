import { agentModels, address, chat, getCfg, hasPerm, listModels, newSession, Problem, scopeOf, validate } from './api.js';
import { applyUpdate, checkUpdate, getHandle } from './updater.js';
import { guideTurn } from './guide.js';
import { runAuto } from './auto.js';
import { applyI18n, explain, lang, t } from './i18n.js';
import { bindTabs } from './tabs.js';
import { deleteArchived, downloadTranscript, durableConversation, historyEnabledKey, renameArchived, resumeArchived, saveArchived, setHistoryEnabled, titleFor } from './history.js';
import { bindHistoryView } from './history-view.js';
import { Attachments } from './attachments.js';
import { blankThread, restoreThread, snapshotThread } from './thread.js';
import { turnTiming } from './timing.js';
import { button, copyButton, el, markdown } from './view.js';

applyI18n();
const $ = id => document.getElementById(id);
const inp = $('inp'), log = $('log'), scroller = $('conversation');
const [win, initial, historySetting] = await Promise.all([chrome.windows.getCurrent(), getCfg(), chrome.storage.local.get(historyEnabledKey)]);
const threadKey = 'thread:' + win.id, menuKey = 'menu:' + win.id;
const catalogKey = 'modelCatalog', catalogTtl = 5 * 60_000;
const initialState = await chrome.storage.session.get([threadKey, menuKey, catalogKey]);
const catalogScope = c => JSON.stringify([c.url, c.profileId, c.insecureHttpOrigin]);
let catalog = initialState[catalogKey];
const tabs = bindTabs(win.id), attachments = new Attachments();
let cfg = initial, thread = restoreThread(initialState[threadKey], scopeOf(cfg));
const restored = initialState[threadKey];
const contextMode = $('contextMode');
contextMode.value = 'focused';
if (restored?.scope === scopeOf(cfg)) {
  if (Array.isArray(restored.comparison)) attachments.add(...restored.comparison);
  if (restored.contextMode === 'full') contextMode.value = 'full';
}
let mode = 'chat', task = null, operation = null, modelRequest = null;
let saveQueue = Promise.resolve(), archiveQueue = Promise.resolve(), draftTimer, contextTimer, configReads = 0, pendingMenu, lastMenu;
let historyEnabled = !!historySetting[historyEnabledKey];
const number = new Intl.NumberFormat(lang());
const ms = new Intl.NumberFormat(lang(), { style: 'unit', unit: 'millisecond', unitDisplay: 'short', maximumFractionDigits: 0 });
const seconds = new Intl.NumberFormat(lang(), { style: 'unit', unit: 'second', unitDisplay: 'narrow', maximumFractionDigits: 2 });
const timingRows = [
  ['setup', 'timingSetup'], ['context', 'timingContext'], ['session', 'timingSession'], ['upload', 'timingUpload'],
  ['request', 'timingRequest'], ['waiting', 'timingWait'], ['receiving', 'timingReceive'], ['first', 'firstText'], ['total', 'totalTime']
];
const promptKey = { sum: 'promptSum', exp: 'promptExplain', tr: 'promptTranslate' };

function announce(msg) { $('live').textContent = msg; }
function notice(msg = '', settings = false) {
  const box = $('notice'); box.replaceChildren(); box.hidden = !msg;
  if (!msg) return;
  box.append(msg);
  if (settings) box.append(button(t('openSettings'), () => chrome.runtime.openOptionsPage()));
}
function persist() {
  clearTimeout(draftTimer);
  thread.draft = inp.value;
  const record = snapshotThread(thread, scopeOf(cfg));
  const comparison = attachments.items.filter(i => i.kind === 'compare');
  if (comparison.length) record.comparison = comparison;
  if (contextMode.value === 'full') record.contextMode = 'full';
  saveQueue = saveQueue.then(() => chrome.storage.session.set({ [threadKey]: record })).catch(() => notice(t('storageFail')));
  return saveQueue;
}
function archive() {
  if (!historyEnabled || !thread.messages.length) return;
  const owner = thread;
  owner.historyId ??= crypto.randomUUID();
  const record = durableConversation(owner, scopeOf(cfg));
  // Publish the window’s claim before creating a record another window could try to resume.
  const claim = persist();
  archiveQueue = archiveQueue.then(async () => {
    await claim;
    if (await saveArchived(owner.historyId, record, !owner.historySaved)) {
      owner.historySaved = true;
      if (owner === thread) persist();
    }
  }).catch(() => {
    if (owner !== thread) return;
    notice(t('historySaveFail'));
  });
}
function drawMessage(message) {
  const article = el('article', 'message ' + message.role);
  const body = el('div', 'body');
  if (message.role !== 'note') {
    const speaker = message.role === 'user' ? t('you') : 'Odysseus';
    article.append(el('div', 'byline', message.guide ? `${speaker} · ${t('guide')}` : speaker));
  }
  article.append(body);
  if (message.role === 'assistant') {
    body.append(markdown(message.text));
    const actions = el('div', 'reply-actions');
    actions.append(copyButton(message.text));
    if (message.timing) {
      const details = el('details', 'reply-timing'), metrics = el('dl');
      details.append(el('summary', '', t('replyTiming')));
      for (const [key, label] of timingRows) {
        const duration = message.timing[key];
        if (!Number.isFinite(duration)) continue;
        metrics.append(el('dt', '', t(label)), el('dd', '', duration < 1000 ? ms.format(duration) : seconds.format(duration / 1000)));
      }
      details.append(metrics);
      actions.append(details);
    }
    article.append(actions);
    if (message.partial) article.append(el('small', 'sources', t('partial')));
  } else body.textContent = message.text;
  if (message.sources?.length) article.append(el('div', 'sources', message.sources.join(' · ')));
  return article;
}
function restoreView() {
  log.replaceChildren(...thread.messages.map(drawMessage)); inp.value = thread.draft;
  scroller.scrollTop = scroller.scrollHeight;
}
function follow() { return scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight < 70; }
function addNote(text) {
  const stick = follow(), m = { role: 'note', text }; thread.messages.push(m); log.append(drawMessage(m)); archive();
  if (stick) scroller.scrollTop = scroller.scrollHeight;
}
function describe(a, snap) {
  const target = snap.elements.find(item => item.id === a.id)?.label || '';
  switch (a.a) {
    case 'goto': return `${t('goto')} · ${a.url}`;
    case 'scroll': return t(a.dir === 'up' ? 'scrollUp' : 'scrollDown');
    case 'type': return `${t('type')} “${target}” → “${a.text}”`;
    case 'select': return `${t('select')} “${a.value}” → “${target}”`;
    default: return `${t('click')} “${target}”`;
  }
}
function renderReview() {
  const box = $('review'); box.replaceChildren(); box.hidden = historyView.open || mode !== 'guide' || !task || !!operation;
  if (box.hidden) return;
  const row = el('div', 'review-actions'), card = task.card;
  if (card) {
    box.append(el('strong', '', t('proposal')), el('p', 'review-hint', card.frame.url), el('p', '', describe(card.action, card.frame)));
    if (card.destination) box.append(el('p', 'review-hint', card.destination));
    row.append(button(t('approve'), () => applyCard(card), 'primary'));
    if (card.action.id) row.append(button(t('show'), () => showCard(card)));
    row.append(button(t('dismiss'), () => {
      task.history.push(t('skipped') + ' ' + describe(card.action, card.frame)); task.card = null;
      addNote(t('skipped')); persist(); sync();
    }));
  } else {
    box.append(el('p', 'review-hint', t('nextHint')));
    row.append(button(t('next'), () => sendTurn(true), 'primary'));
  }
  box.append(row);
}
function paintContext() {
  clearTimeout(contextTimer);
  const context = attachments.prepare(inp.value, contextMode.value);
  $('contextControl').hidden = !context.eligible;
  const { before, after } = context;
  $('contextSize').textContent = `${number.format(after)}${after < before ? ' / ' + number.format(before) : ''} ${t('characters')}`;
  attachments.showPrepared(context);
}
function sync() {
  const locked = !!operation, agent = mode === 'agent', guide = mode === 'guide' || agent;
  const historyOpen = historyView.open;
  $('historyToggle').disabled = locked || historyView.busy;
  $('new').disabled = historyView.busy;
  scroller.hidden = $('composeFooter').hidden = $('modeBar').hidden = historyOpen;
  $('chatMode').setAttribute('aria-pressed', String(!guide)); $('guideMode').setAttribute('aria-pressed', String(mode === 'guide')); $('agentMode').setAttribute('aria-pressed', String(agent));
  $('chatMode').disabled = $('guideMode').disabled = $('agentMode').disabled = locked;
  $('model').hidden = guide; $('agentModel').hidden = !agent || !$('agentModel').options.length; $('agentModel').disabled = locked; $('model').disabled = locked || $('model').options.length < 2;
  $('welcome').hidden = log.childElementCount > 0;
  $('welcomeTitle').textContent = t(agent ? 'agentWelcome' : guide ? 'guideWelcome' : 'welcome'); $('guideIntro').textContent = t(agent ? 'agentIntro' : 'guideIntro');
  $('starters').hidden = guide; $('guideIntro').hidden = !guide;
  $('tools').hidden = guide; inp.readOnly = locked;
  for (const b of document.querySelectorAll('#tools button,#starters button')) b.disabled = locked;
  const hint = t(agent ? 'agentPlaceholder' : guide ? 'guidePlaceholder' : 'placeholder'); inp.placeholder = hint; $('inputLabel').textContent = hint;
  $('privacy').textContent = t(agent ? 'agentHint' : guide ? 'guideHint' : 'shareHint');
  $('send').disabled = !locked && !inp.value.trim(); $('send').textContent = t(locked ? 'stop' : 'send');
  contextMode.disabled = locked;
  attachments.render($('attachments'), locked, i => { attachments.remove(i); sync(); if (i.kind === 'compare') persist(); });
  paintContext(); renderReview();
}
function cancel(detach = false) {
  operation?.abort();
  if (detach) operation = null;
}
async function run(fn) {
  if (operation) return;
  const controller = new AbortController(); operation = controller; notice(); sync();
  try { await fn(controller.signal); }
  catch (e) {
    if (operation !== controller) return;
    if (controller.signal.aborted) { notice(t('stopped')); announce(t('stopped')); }
    else notice(explain(e), ['setup', 'denied', 'httpConsent', 'invalidUrl', 'auth'].includes(e.code));
  } finally {
    if (operation === controller) { operation = null; sync(); persist(); takeMenu(); }
  }
}
function reset() {
  cancel(true); attachments.clear(); task = null; thread = blankThread(); mode = 'chat'; contextMode.value = 'focused';
  restoreView(); notice(); sync(); persist();
}
function setMode(next) {
  if (operation || next === mode) return;
  if (next === 'guide' && attachments.items.length) { notice(t('guideAttachments')); return; }
  mode = next; task = null; notice(); sync(); inp.focus();
}
async function connected(signal) {
  const c = await getCfg(); signal.throwIfAborted();
  if (scopeOf(c) !== scopeOf(cfg)) throw new Problem('serverChanged');
  validate(c);
  if (!await hasPerm(c)) throw new Problem('denied');
  signal.throwIfAborted(); return c;
}
async function stage(kind, prompt) {
  await run(async signal => {
    const item = kind === 'screenshot' ? await tabs.screenshot() : await tabs.capture(kind === 'compare' ? 'page' : kind);
    signal.throwIfAborted();
    if (kind !== 'screenshot' && !item.text?.trim()) throw new Problem(kind === 'selection' ? 'emptySelection' : 'emptyPage');
    const { documentId, ...source } = item;
    attachments.add({ ...source, kind });
    if (kind === 'compare') {
      const count = attachments.items.filter(i => i.kind === 'compare').length;
      if (count >= 2 && !inp.value.trim()) inp.value = t('comparePrompt');
      notice(t(count < 3 ? 'compareMore' : 'compareReady'));
    } else if (prompt && !inp.value.trim()) inp.value = t(prompt);
    announce(t('captured')); inp.focus();
  });
}
function showCard(card) {
  run(async signal => {
    try { await tabs.review(card.frame, card.action, 'show', signal); }
    catch (e) { if (task?.card === card) task.card = null; throw e; }
  });
}
function applyCard(card) {
  const owner = task;
  run(async signal => {
    try {
      await tabs.review(card.frame, card.action, 'apply', signal);
      signal.throwIfAborted();
      const line = `${t('applied')} ${describe(card.action, card.frame)}`;
      owner.history.push(line); addNote(line); announce(t('applied'));
    } finally { owner.card = null; }
  });
}

// Keep stream updates cheap. Build Markdown only after completion or interruption.
function liveTurn(user, timing) {
  const userNode = drawMessage(user), replyNode = el('article', 'message assistant'), body = el('div', 'body streaming', t('receiving'));
  replyNode.append(el('div', 'byline', user.guide ? `Odysseus · ${t('guide')}` : 'Odysseus'), body); log.append(userNode, replyNode);
  $('welcome').hidden = true; scroller.scrollTop = scroller.scrollHeight;
  let value = '', frame, pending = '', replace = true, chunks = 0;
  function update(text, delta) {
    timing.seeText(text);
    value = text;
    if (delta === undefined) { replace = true; pending = ''; }
    else if (!replace) pending += delta;
    if (frame) return;
    frame = requestAnimationFrame(() => {
      frame = 0;
      const stick = follow();
      if (replace || chunks >= 300) { body.textContent = value || '…'; chunks = 0; }
      else if (pending) { body.append(pending); chunks++; }
      pending = ''; replace = !value;
      if (stick) scroller.scrollTop = scroller.scrollHeight;
    });
  }
  function finish(text, partial = false) {
    cancelAnimationFrame(frame);
    if (!replyNode.isConnected) return;
    const stick = follow();
    const assistant = { role: 'assistant', text, partial, guide: !!user.guide, timing: timing.report() };
    if (text) replyNode.replaceWith(drawMessage(assistant)); else replyNode.remove();
    thread.messages.push(user); if (text) thread.messages.push(assistant);
    archive();
    if (stick) scroller.scrollTop = scroller.scrollHeight;
  }
  function fail() {
    cancelAnimationFrame(frame);
    if (value.trim()) finish(value, true); else { userNode.remove(); replyNode.remove(); }
  }
  return { update, finish, fail };
}
function sendAgent(goal) {
  run(async signal => {
    const c = await connected(signal);
    const user = { role: 'user', text: goal, sources: [], guide: true };
    const userNode = drawMessage(user); log.append(userNode); thread.messages.push(user); $('welcome').hidden = true; inp.value = '';
    let liveNode = null;
    const keep = () => { scroller.scrollTop = scroller.scrollHeight; };
    const clearLive = () => { liveNode?.remove(); liveNode = null; };
    const ui = {
      live(text) { if (!liveNode) { liveNode = el('article', 'message assistant'); liveNode.append(el('div', 'body streaming', '')); log.append(liveNode); } liveNode.lastChild.textContent = text || '…'; keep(); },
      step(text) { clearLive(); addNote(text); keep(); },
      final(text) { clearLive(); const m = { role: 'assistant', text, partial: false, guide: true }; thread.messages.push(m); log.append(drawMessage(m)); archive(); keep(); announce(t('replyReady')); },
      error(text) { clearLive(); notice(text); }
    };
    try { await runAuto(c, goal, signal, ui, tabs); }
    catch (e) { clearLive(); if (signal.aborted) addNote(t('agentStopped')); else throw e; }
  });
}
function sendTurn(next = false) {
  if (operation) return;
  const goal = next ? task?.goal : inp.value.trim(); if (!goal) return;
  if (mode === 'agent') return sendAgent(goal);
  const guided = mode === 'guide', timing = turnTiming(performance.now());
  const prompt = guided ? null : timing.context(() => attachments.prompt(goal, attachments.prepare(goal, contextMode.value)));
  run(async signal => {
    const c = await timing.measure('setup', () => connected(signal));
    let frame;
    if (guided) {
      frame = await timing.measure('context', () => tabs.capture('snapshot', next ? task.tabId : undefined)); signal.throwIfAborted();
      if (!next) task = { goal, tabId: frame.tabId, history: [], card: null, fallback: false, sid: null };
      task.card = null;
    }
    const sources = guided ? [frame.title || frame.url] : attachments.items.map(i => attachments.label(i));
    const live = liveTurn({ role: 'user', text: next ? t('next') : goal, sources, guide: guided }, timing);
    const write = (text, delta) => { if (!signal.aborted) live.update(text, delta); };
    try {
      let final;
      if (guided) {
        const result = await guideTurn(c, task, frame, write, signal, timing); signal.throwIfAborted();
        if (result.action) {
          const details = await tabs.review(frame, result.action, 'inspect', signal); signal.throwIfAborted();
          task.card = { action: result.action, frame, destination: details.destination };
        } else task = null;
        final = result.text;
      } else {
        if (thread.sid == null) {
          const sid = await timing.measure('session', () => newSession(c, signal)); signal.throwIfAborted(); thread.sid = sid; persist();
        }
        const pendingFiles = attachments.items.some(item => item.file && (item.forSession !== thread.sid || !item.ids));
        const upload = () => attachments.uploadFor(c, thread.sid, signal);
        if (pendingFiles) announce(t('uploading'));
        const ids = await (pendingFiles ? timing.measure('upload', upload) : upload()); signal.throwIfAborted();
        final = await timing.stream(() => chat(c, thread.sid, prompt, ids, write, signal)); signal.throwIfAborted();
        attachments.clear();
      }
      live.finish(final); if (!next) inp.value = ''; announce(t(guided && task?.card ? 'proposal' : 'replyReady'));
    } catch (e) { live.fail(); throw e; }
  });
}

function renderModels(models = []) {
  const select = $('model'); select.replaceChildren();
  function add(ep, model, label) { const opt = el('option', '', label); opt.value = JSON.stringify([ep, model]); select.append(opt); }
  add('', '', t('serverDefault'));
  const count = new Map();
  for (const m of models) count.set(m.label, (count.get(m.label) || 0) + 1);
  for (const m of models) add(m.ep, m.model, count.get(m.label) > 1 && m.ep ? `${m.label} · ${m.ep}` : m.label);
  const current = JSON.stringify([cfg.endpointId || '', cfg.model || '']);
  if (![...select.options].some(o => o.value === current)) add(cfg.endpointId, cfg.model, cfg.model || `${t('serverDefault')} · ${cfg.endpointId}`);
  select.value = current; sync();
}
async function loadModels() {
  modelRequest?.abort(); const controller = new AbortController(); modelRequest = controller;
  renderModels();
  try {
    const c = await connected(controller.signal);
    const scope = catalogScope(c);
    if (catalog?.scope === scope && Date.now() - catalog.at < catalogTtl) { renderModels(catalog.models); return; }
    const models = await listModels(c, controller.signal);
    if (controller.signal.aborted) return;
    catalog = { scope, at: Date.now(), models };
    renderModels(models);
    chrome.storage.session.set({ [catalogKey]: catalog }).catch(() => {});
  } catch (e) {
    if (controller.signal.aborted || operation) return;
    const setup = ['setup', 'auth', 'denied', 'httpConsent', 'invalidUrl'].includes(e.code);
    notice(setup ? explain(e) : t('modelListFail'), setup);
  }
}
async function configChanged() {
  const revision = ++configReads, current = await getCfg(); if (revision !== configReads) return;
  if (scopeOf(current) === scopeOf(cfg) && current.token === cfg.token && current.insecureHttpOrigin === cfg.insecureHttpOrigin) return;
  const sameConnection = catalogScope(current) === catalogScope(cfg) && current.token === cfg.token;
  cfg = current; reset(); setHost(); notice(t('serverChanged'));
  if (sameConnection) renderModels(catalog?.scope === catalogScope(cfg) ? catalog.models : []);
  else { catalog = null; loadModels(); }
}
function setHost() {
  let host = t('offline'); try { address(cfg.url); host = 'Odysseus'; } catch {}
  $('host').textContent = host; $('host').removeAttribute('title');
}
function takeMenu() {
  if (operation || historyView.busy || !pendingMenu) return;
  const item = pendingMenu; pendingMenu = null;
  if (item.id === lastMenu || !item.text?.trim() || Date.now() - item.at > 120000) return;
  lastMenu = item.id; task = null; mode = 'chat';
  if (historyView.open) historyView.change(false);
  attachments.add({ kind: 'selection', title: item.title, url: item.url, text: item.text, clipped: item.clipped });
  if (!inp.value.trim() && promptKey[item.kind]) inp.value = t(promptKey[item.kind]);
  notice(t('staged')); sync(); persist(); inp.focus();
  chrome.storage.session.get(menuKey).then(d => { if (d[menuKey]?.id === item.id) return chrome.storage.session.remove(menuKey); });
}
const historyView = bindHistoryView({
  changed: sync,
  enabled: () => historyEnabled,
  hasCurrent: () => thread.messages.length > 0,
  compatible: item => item.scope === scopeOf(cfg),
  message: drawMessage,
  ready: () => archiveQueue,
  rename: renameArchived,
  async setEnabled(value) {
    await setHistoryEnabled(value); historyEnabled = value;
    if (value) { archive(); await archiveQueue; }
  },
  exportCurrent: () => downloadTranscript(titleFor(thread.messages), thread.messages),
  async resume(id) {
    if (id === thread.historyId) { await historyView.change(false); return; }
    if (inp.value.trim() || attachments.items.length) throw new Problem('historyDraft');
    await persist();
    const scope = scopeOf(cfg), record = await resumeArchived(id, threadKey, scope);
    if (scope !== scopeOf(cfg)) { persist(); throw new Problem('historyScope'); }
    thread = restoreThread(record, scope); task = null; mode = 'chat'; contextMode.value = 'focused';
    restoreView(); notice(); await historyView.change(false); inp.focus();
  },
  async remove(id) {
    await archiveQueue; await deleteArchived(id, threadKey);
    if (thread.historyId === id) reset();
  }
});
$('historyToggle').onclick = () => historyView.change(!historyView.open).then(takeMenu);
$('cfg').onclick = () => chrome.runtime.openOptionsPage();
$('new').onclick = () => { if (historyView.open) historyView.change(false); reset(); takeMenu(); inp.focus(); };
$('chatMode').onclick = () => setMode('chat'); $('guideMode').onclick = () => setMode('guide'); $('agentMode').onclick = () => setMode('agent');
$('bPage').onclick = () => stage('page'); $('bSel').onclick = () => stage('selection'); $('bShot').onclick = () => stage('screenshot');
$('bCompare').onclick = () => stage('compare');
$('bFile').onclick = () => $('file').click();
$('file').onchange = () => {
  if (!operation) {
    try { attachments.add(...Array.from($('file').files, file => ({ kind: 'file', file }))); notice(); announce(t('captured')); }
    catch (e) { notice(explain(e)); }
  }
  $('file').value = ''; sync();
};
for (const b of document.querySelectorAll('[data-prompt]')) b.onclick = () => stage(b.dataset.prompt === 'sum' ? 'page' : 'selection', promptKey[b.dataset.prompt]);
$('agentModel').onchange = () => chrome.storage.local.set({ agentModel: $('agentModel').value }).catch(() => {});
async function loadAgentModels() {
  try {
    const list = await agentModels(await getCfg()); if (!list.length) return;
    const { agentModel } = await chrome.storage.local.get('agentModel'); const s = $('agentModel'); s.replaceChildren();
    for (const m of list) { const o = el('option', '', m.label); o.value = m.id; s.append(o); }
    s.value = list.some(m => m.id === agentModel) ? agentModel : 'auto'; sync();
  } catch {}
}
$('model').onchange = async () => {
  const [endpointId, model] = JSON.parse($('model').value);
  try { await chrome.storage.local.set({ endpointId, model }); }
  catch { notice(t('storageFail')); renderModels(catalog?.scope === catalogScope(cfg) ? catalog.models : []); }
};
$('composer').onsubmit = e => { e.preventDefault(); if (operation) cancel(); else sendTurn(); };
contextMode.onchange = () => { paintContext(); persist(); };
inp.addEventListener('input', () => {
  $('send').disabled = !inp.value.trim();
  clearTimeout(contextTimer); contextTimer = setTimeout(paintContext, 150);
  clearTimeout(draftTimer); draftTimer = setTimeout(persist, 180);
});
inp.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing && e.keyCode !== 229) { e.preventDefault(); if (!operation) sendTurn(); }
});
document.addEventListener('keydown', e => { if (e.key === 'Escape' && operation) cancel(); });
chrome.runtime.onMessage.addListener(m => { if (m && m.odyStop && operation && mode === 'agent') cancel(); });
window.addEventListener('pagehide', () => { clearTimeout(contextTimer); persist(); cancel(true); modelRequest?.abort(); attachments.clear(); });
chrome.storage.onChanged.addListener((changes, area) => {
  if (area === 'local' && changes[historyEnabledKey]) historyEnabled = !!changes[historyEnabledKey].newValue;
  if (area === 'local' && Object.keys(changes).some(k => Object.hasOwn(cfg, k))) configChanged();
  if (area === 'session' && changes[menuKey]?.newValue) { pendingMenu = changes[menuKey].newValue; takeMenu(); }
});
setHost(); restoreView(); sync(); loadModels(); loadAgentModels(); pendingMenu = initialState[menuKey]; takeMenu();

// ---- auto-update ----
(async () => {
  try {
    const { justUpdated } = await chrome.storage.local.get('justUpdated');
    if (justUpdated) { await chrome.storage.local.remove('justUpdated'); notice(t('u_done') + ' ' + justUpdated); setTimeout(() => notice(''), 6000); return; }
    const m = await checkUpdate(); if (!m) return;
    const h = await getHandle();
    const ui = (msg, label, fn) => { notice(msg); if (label) $('notice').append(' ', button(label, fn)); };
    if (!h) { ui(m.version, t('u_on'), () => chrome.runtime.openOptionsPage()); return; }
    try { await applyUpdate(m, false); return; } catch (e) { if (e.message !== 'permission') { ui(t('u_fail') + ': ' + e.message); return; } }
    ui(m.version, t('u_btn') + ' ' + m.version, async () => { try { await applyUpdate(m, true); } catch (e) { ui(t('u_fail') + ': ' + e.message); } });
  } catch {}
})();
