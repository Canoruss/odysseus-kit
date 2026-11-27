// Autonomous Agent Orchestrator: fluid, adaptive, site-agnostic execution loop.
import { agentStep, agentLook } from './api.js';
import { domEngine } from './dom-engine.js';
import { formatState, computeStateDiff, AGENT_TOOLS, AGENT_SYS, callsToActions } from './autofns.js';
import { t, tf, lang } from './i18n.js';
import { hostOf, findPlaybook, savePlaybook, markPlaybook, getNotes, addNote, findEl, locOf, RISKY, RECORDABLE } from './playbook.js';
import { matchesEnsoAuditGoal, findEnsoTab, runEnsoBpAudit } from './workflows/enso-bp.js';

const sleep = ms => new Promise(r => setTimeout(r, ms));
const RUN_STATE_KEY = 'activeAgentRun';

// Session-scoped Chrome Debugger manager (Proposal 3: avoids repeated infobar jumping)
function createDebuggerSession() {
  let attachedTabId = null;
  let available = null;

  async function canUse() {
    if (available === null) available = await chrome.permissions.contains({ permissions: ['debugger'] }).catch(() => false);
    return available;
  }
  async function ensure(tabId) {
    if (!(await canUse())) return false;
    if (attachedTabId === tabId) return true;
    await detach();
    try {
      await chrome.debugger.attach({ tabId }, '1.3');
      attachedTabId = tabId;
      return true;
    } catch {
      attachedTabId = null;
      return false;
    }
  }
  async function clickAt(tabId, x, y) {
    if (!(await ensure(tabId))) return false;
    try {
      const tgt = { tabId };
      const send = (type, extra) => chrome.debugger.sendCommand(tgt, 'Input.dispatchMouseEvent', { type, x, y, button: 'left', ...extra });
      await send('mouseMoved', { buttons: 0 });
      await send('mousePressed', { buttons: 1, clickCount: 1 });
      await sleep(35);
      await send('mouseReleased', { buttons: 0, clickCount: 1 });
      return true;
    } catch {
      await detach();
      return false;
    }
  }
  async function detach() {
    if (attachedTabId != null) {
      const old = attachedTabId;
      attachedTabId = null;
      await chrome.debugger.detach({ tabId: old }).catch(() => {});
    }
  }
  return { clickAt, detach };
}

// Adaptive DOM + Tab Load Settling (Proposal 2: replaces fixed 1000-1500ms sleeps)
async function waitSettle(tabId, isNavigation = false, signal) {
  const started = performance.now();
  const maxTotal = isNavigation ? 8500 : 2800;
  if (isNavigation) await sleep(60);

  while (performance.now() - started < maxTotal) {
    signal?.throwIfAborted();
    let tb;
    try { tb = await chrome.tabs.get(tabId); } catch { break; }
    if (tb.status === 'complete') break;
    await sleep(90);
  }
  signal?.throwIfAborted();
  try {
    await chrome.scripting.executeScript({
      target: { tabId },
      func: domEngine,
      args: ['settle', { minMs: isNavigation ? 110 : 65, quietMs: isNavigation ? 150 : 100, maxMs: isNavigation ? 3200 : 1400 }]
    });
  } catch {
    await sleep(150);
  }
}

async function snap(tabId) {
  const tb = await chrome.tabs.get(tabId);
  if (!/^https?:/.test(tb.url || '')) throw new Error('unsupported page');
  const [r] = await chrome.scripting.executeScript({ target: { tabId }, func: domEngine, args: ['agentSnapshot', { maxElements: 160 }] });
  if (!r?.result || r.result.error) throw new Error(r?.result?.error || 'noPage');
  return r.result;
}

async function setBanner(tabId, on) {
  if (!tabId) return;
  try {
    await chrome.scripting.executeScript({
      target: { tabId },
      func: domEngine,
      args: ['banner', on ? { on: true, label: t('working'), stopLabel: t('stop') } : { on: false }]
    });
  } catch {}
}

export async function cleanupOrphanedRun() {
  try {
    const data = await chrome.storage.session.get(RUN_STATE_KEY);
    const run = data[RUN_STATE_KEY];
    if (!run) return false;
    for (const tid of run.BannerTabs || []) await setBanner(tid, false);
    await chrome.storage.session.remove(RUN_STATE_KEY);
    return true;
  } catch { return false; }
}

function describe(a, state) {
  const el = state?.els?.find(e => e.id === a.id);
  const label = el ? `${el.tag} “${el.label}”${el.href ? ' → ' + el.href : ''}` : (a.id ? `[${a.id}]` : '');
  switch (a.a) {
    case 'click': return `${t('aClick')} ${label}`;
    case 'hover': return `${t('aHover')} ${label}`;
    case 'type': return `${t('aType')} “${a.text}” → ${label}${a.submit ? ' ⏎' : ''}`;
    case 'clear': return `${t('aClear')} ${label}`;
    case 'select': return `${t('aSelect')} “${a.value}” → ${label}`;
    case 'scroll': return `${t('aScroll')} ${a.dir === 'up' ? '↑' : '↓'}${label ? ' ' + label : ''}`;
    case 'goto': return `${t('aGoto')} ${a.url}`;
    case 'look': return `${t('aLook')}: ${a.question}`;
    case 'remember': return `${t('aRemember')}: ${a.note}`;
    case 'memo': return `${t('aMemo')}: ${a.text.slice(0, 90)}${a.text.length > 90 ? '…' : ''}`;
    case 'inspect_region':
    case 'rowicons': return `${t('aInspect')}: ${a.label}`;
    case 'clickxy': return `${t('aClickxy')} (${a.x}, ${a.y})`;
    case 'search': return `${t('aSearch')} “${a.text}”`;
    case 'newtab': return `${t('aNewtab')} ${a.url}`;
    case 'switch_tab': return `${t('aSwitchTab')} #${a.tabId}`;
    case 'list_tabs': return t('aListTabs');
    case 'key': return `${t('aKey')} ${a.key}`;
    case 'wait': return `${t('aWait')} ${a.ms} ms`;
    case 'back': return t('aBack');
    default: return t('aExtract');
  }
}

async function execAction(c, a, tabId, windowId, signal, tabs, dbg, bannerTabs) {
  // Set-of-Marks (SoM) grounded visual inspection (Proposal 3)
  if (a.a === 'look') {
    const tb = await chrome.tabs.get(tabId);
    if (!tb.active) {
      await chrome.tabs.update(tabId, { active: true });
      await sleep(120);
    }
    // Render temporary numbered Set-of-Marks badges, hide agent banner during capture, then restore
    await setBanner(tabId, false);
    try {
      await chrome.scripting.executeScript({ target: { tabId }, func: domEngine, args: ['som', { on: true }] }).catch(() => {});
      const { src } = await tabs.captureImage(tabId, 68);
      await chrome.scripting.executeScript({ target: { tabId }, func: domEngine, args: ['som', { on: false }] }).catch(() => {});
      signal.throwIfAborted();
      const promptQ = `${a.question}\n(Note: Interactive controls on the page have orange numbered badges matching their [id] in the element list; reference [id] or normalized 0-1000 x,y coordinates if needed.)`;
      const d = await agentLook(c, src.slice(src.indexOf(',') + 1), promptQ, signal);
      return { ok: true, data: String(d.text || '') };
    } finally {
      await chrome.scripting.executeScript({ target: { tabId }, func: domEngine, args: ['som', { on: false }] }).catch(() => {});
      await setBanner(tabId, true);
    }
  }

  if (a.a === 'clickxy') {
    const [p] = await chrome.scripting.executeScript({ target: { tabId }, func: domEngine, args: ['probeXY', a] });
    if (!p?.result?.ok) return { ...(p?.result || { ok: false, msg: 'probe failed' }), settle: false };
    if (await dbg.clickAt(tabId, p.result.px, p.result.py)) {
      return { ok: true, data: p.result.data + ' (CDP)', settle: true, nav: false };
    }
    const [r] = await chrome.scripting.executeScript({ target: { tabId }, func: domEngine, args: ['clickXY', a] });
    return { ...(r?.result || { ok: false }), settle: true, nav: false };
  }

  if (a.a === 'list_tabs') {
    const openTabs = await chrome.tabs.query({ windowId });
    const lines = openTabs
      .filter(tb => /^https?:/.test(tb.url || ''))
      .map(tb => `tabId=${tb.id}${tb.id === tabId ? ' (current)' : ''} · "${(tb.title || '').slice(0, 80)}" · ${(tb.url || '').slice(0, 140)}`);
    return { ok: true, data: lines.join('\n') || 'No readable HTTP/HTTPS tabs.' };
  }

  if (a.a === 'switch_tab') {
    const target = await chrome.tabs.get(a.tabId).catch(() => null);
    if (!target || !/^https?:/.test(target.url || '')) return { ok: false, msg: `tab ${a.tabId} is not an accessible web page` };
    await setBanner(tabId, false);
    await chrome.tabs.update(target.id, { active: true });
    bannerTabs.add(target.id);
    return { ok: true, nav: false, settle: true, tabId: target.id };
  }

  if (a.a === 'goto') { await chrome.tabs.update(tabId, { url: a.url }); return { ok: true, nav: true }; }
  if (a.a === 'search') { await chrome.search.query({ text: a.text, tabId }); return { ok: true, nav: true }; }
  if (a.a === 'back') { await chrome.tabs.goBack(tabId); return { ok: true, nav: true }; }
  if (a.a === 'wait') { await sleep(a.ms); return { ok: true }; }
  if (a.a === 'newtab') {
    await setBanner(tabId, false);
    const nt = await chrome.tabs.create({ url: a.url, active: true, windowId });
    bannerTabs.add(nt.id);
    return { ok: true, nav: true, tabId: nt.id };
  }

  // Track any popup/new-tab opened synchronously by a link click (`target="_blank"` or `window.open`)
  let spawnedTabId = null;
  const onCreated = (nt) => {
    if (nt.openerTabId === tabId || (nt.windowId === windowId && nt.active)) spawnedTabId = nt.id;
  };
  if (a.a === 'click') chrome.tabs.onCreated.addListener(onCreated);
  try {
    const [r] = await chrome.scripting.executeScript({ target: { tabId }, func: domEngine, args: ['act', a] });
    const res = r?.result || { ok: false, msg: 'script failed' };
    if (a.a === 'click' && res.ok) await sleep(55); // allow browser to register new tab if target="_blank"
    if (spawnedTabId) {
      const st = await chrome.tabs.get(spawnedTabId).catch(() => null);
      if (st && (/^https?:/.test(st.url || st.pendingUrl || ''))) {
        await setBanner(tabId, false);
        bannerTabs.add(spawnedTabId);
        return { ...res, nav: true, tabId: spawnedTabId };
      }
    }
    const causesNav = a.a === 'click' || (a.a === 'type' && a.submit) || (a.a === 'key' && a.key === 'Enter');
    const causesSettle = causesNav || a.a === 'select' || a.a === 'hover' || a.a === 'key';
    return { ...res, nav: causesNav, settle: causesSettle };
  } finally {
    if (a.a === 'click') chrome.tabs.onCreated.removeListener(onCreated);
  }
}

// Replay a saved playbook recipe without LLM calls
async function replay(c, pb, tabId, windowId, signal, ui, tabs, dbg, bannerTabs) {
  const done = [], collected = [];
  for (let i = 0; i < pb.steps.length; i++) {
    signal.throwIfAborted();
    const s = pb.steps[i], a = { ...s.act };
    ui.step(`▸ [${i + 1}/${pb.steps.length}] ` + (s.loc ? `${a.a} “${s.loc.label}”` : a.a + (a.url ? ' ' + a.url : a.text ? ' “' + a.text + '”' : '')));
    if (s.loc) {
      let id = null;
      for (let k = 0; k < 10 && id == null; k++) {
        const st = await snap(tabId).catch(() => null);
        const e = st && findEl(st.els, s.loc);
        if (e) id = e.id;
        else await sleep(350);
      }
      if (id == null) return { ok: false, at: i, why: t('agentElNotFound') + s.loc.label, done, collected, tabId };
      a.id = id;
    }
    let res;
    try { res = await execAction(c, a, tabId, windowId, signal, tabs, dbg, bannerTabs); }
    catch (e) { res = { ok: false, msg: String(e.message || e) }; }
    if (!res.ok) return { ok: false, at: i, why: res.msg || 'failed', done, collected, tabId };
    if (res.tabId) tabId = res.tabId;
    if (res.nav || res.settle) await waitSettle(tabId, !!res.nav, signal);
    if (a.a === 'extract' && res.data) collected.push(`[step ${i + 1}]\n` + String(res.data).slice(0, 2000));
    done.push(s);
  }
  return { ok: true, done, collected, tabId };
}

const HOSTS = { origins: ['<all_urls>'] };
const HOSTS_DBG = { origins: ['<all_urls>'], permissions: ['debugger'] };

export async function runAuto(c, goal, signal, ui, tabs) {
  if (!(await chrome.permissions.contains(HOSTS_DBG))) {
    const ok = await chrome.permissions.request(HOSTS_DBG).catch(() => false)
      || (!(await chrome.permissions.contains(HOSTS)) && await chrome.permissions.request(HOSTS).catch(() => false));
    if (!ok && !(await chrome.permissions.contains(HOSTS))) { ui.error(t('agentPerm')); return; }
  }

  await cleanupOrphanedRun();

  const [cur] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
  let tab = cur;
  if (!tab?.id || !/^https?:/.test(tab.url || '')) {
    tab = await chrome.tabs.create({ url: 'https://www.google.com/', active: true });
    await waitSettle(tab.id, true, signal);
  }

  let tabId = tab.id;
  const windowId = tab.windowId;
  const dbg = createDebuggerSession();
  const bannerTabs = new Set([tabId]);

  const checkpoint = async (stepNum, scratchpad, hist) => {
    try {
      await chrome.storage.session.set({
        [RUN_STATE_KEY]: { goal, step: stepNum, tabId, scratchpad, hist: hist.slice(-10), BannerTabs: [...bannerTabs], at: Date.now() }
      });
    } catch {}
  };

  ui.step('▸ Odysseus ' + chrome.runtime.getManifest().version);

  // Optional domain workflow plug-in: Enso Connect Boarding Pass Audit (Proposal 6)
  if (matchesEnsoAuditGoal(goal)) {
    const enso = await findEnsoTab(tab);
    if (enso) {
      try {
        if (enso.id !== tab.id) {
          await chrome.tabs.update(enso.id, { active: true });
          await chrome.windows.update(enso.windowId, { focused: true }).catch(() => {});
          await waitSettle(enso.id, false, signal);
        }
        return await runEnsoBpAudit(enso.id, signal, ui, (tid, x, y) => dbg.clickAt(tid, x, y));
      } finally {
        await dbg.detach();
      }
    }
  }

  const pt = lang() === 'pt-PT';
  const host = hostOf(tab.url);
  const stepFn = c.stepFn || agentStep;
  let rec = [], recOK = true, recWhy = '', notesAdded = 0;
  let note = '', scratchpad = '', hist = [], nudges = 0, retries = 0;

  const notes = host ? await getNotes(host) : [];
  const SYS = AGENT_SYS + (notes.length ? `\n\nLEARNED SITE NOTES FOR ${host} (verify against live page):\n` + notes.map(n => '- ' + n).join('\n') : '');

  try {
    // Saved Playbook fast-path replay
    if (host && !/\b(sem receita|no recipe|reaprender|relearn)\b/i.test(goal)) {
      const pb = await findPlaybook(host, goal);
      if (pb) {
        ui.step('▸ ' + tf('agentReplay', pb.steps.length, pb.runs));
        await setBanner(tabId, true);
        const rr = await replay(c, pb, tabId, windowId, signal, ui, tabs, dbg, bannerTabs);
        tabId = rr.tabId || tabId;
        bannerTabs.add(tabId);
        if (rr.ok) {
          await markPlaybook(host, pb, true);
          let st = null; try { st = await snap(tabId); } catch {}
          const ctx = rr.collected.join('\n\n').slice(0, 24000);
          try {
            const r = await stepFn(
              c,
              [{ role: 'system', content: AGENT_SYS }, { role: 'user', content: `User goal: ${goal}\n\nThe recorded recipe steps succeeded.${ctx ? `\nCollected page text:\n<page_text>\n${ctx}\n</page_text>\n` : ''}\n${st ? formatState(st) : ''}\n\nAnswer the user's goal from this verified state and call done.` }],
              AGENT_TOOLS.filter(x => x.function.name === 'done'),
              tx => ui.live(tx),
              signal
            );
            const d = callsToActions(r.calls);
            ui.final(d.done || r.text || ctx || '✓');
          } catch (e) { if (signal.aborted) throw e; ui.final(ctx || '✓'); }
          return;
        }
        const dropped = await markPlaybook(host, pb, false);
        ui.step('▸ ' + tf('agentReplayFail', rr.at + 1, rr.why) + (dropped ? t('agentReplayDropped') : ''));
        rec = rr.done.slice();
        note = `Saved recipe stopped at step ${rr.at + 1} (${rr.why}). Steps 1..${rr.done.length} already ran; continue dynamically from the current page.`;
      }
    }

    let prevState = null;
    let lastClickKey = '', repeatedNoOpClicks = 0;

    for (let step = 1; step <= 250; step++) {
      signal.throwIfAborted();
      bannerTabs.add(tabId);
      await setBanner(tabId, true);
      await checkpoint(step, scratchpad, hist);

      let state;
      try { state = await snap(tabId); }
      catch {
        // Recover once if active tab navigated to an interstitial or took extra time
        await sleep(400);
        try { state = await snap(tabId); } catch { ui.error(t('agentNoRead')); return; }
      }

      const diffLine = prevState ? computeStateDiff(prevState, state) : null;
      const contextBlocks = [`User goal: ${goal}`];
      if (scratchpad) contextBlocks.push(`Working scratchpad (memo):\n${scratchpad}`);
      if (hist.length) contextBlocks.push(`Recent steps:\n${hist.slice(-10).join('\n')}`);
      if (diffLine) contextBlocks.push(`State diff since last turn: ${diffLine}`);
      if (note) contextBlocks.push(`Last action output:\n${note}`);
      contextBlocks.push(formatState(state));

      const msgs = [
        { role: 'system', content: SYS },
        { role: 'user', content: contextBlocks.join('\n\n') }
      ];

      let r;
      try {
        r = await stepFn(c, msgs, AGENT_TOOLS, tx => ui.live(tx), signal);
        retries = 0;
      } catch (e) {
        if (signal.aborted) throw e;
        if (!e.status || e.status >= 500 || e.status === 429 || e.code === 'serverStream' || e.code === 'emptyReply' || e.code === 'network') {
          if (++retries > 6) { ui.error(t('agentBusy')); return; }
          ui.step(`… ${t('agentRetry')} (${retries}/6)`);
          await sleep(Math.min(20000, 2200 * 2 ** (retries - 1)) + Math.random() * 1000);
          step--;
          continue;
        }
        throw e;
      }

      const d = callsToActions(r.calls);
      if (d.done != null) {
        if (host && recOK && /(n[aã]o consegui|n[aã]o foi poss[ií]vel|n[aã]o encontrei|n[aã]o abriu|could not|couldn't|unable to|did not open|failed to|not found)/i.test(String(d.done).slice(0, 400))) {
          recOK = false;
          recWhy = pt ? 'a tarefa não terminou com sucesso' : 'the task did not finish successfully';
        }
        if (host && recOK && rec.length >= 2 && rec.length <= 60) {
          await savePlaybook(host, goal, rec);
          ui.step('▸ ' + tf('agentRecipeSaved', rec.length));
        } else if (host && !recOK && recWhy) {
          ui.step('▸ ' + t('agentRecipeNotSaved') + recWhy);
        }
        ui.final(d.done || '✓');
        return;
      }

      if (!d.acts.length) {
        if (++nudges > 3) { ui.final(r.text || t('agentMax')); return; }
        note = 'You did not invoke a tool. Call the next action tool, or call "done" with the verified result.';
        prevState = state;
        continue;
      }
      nudges = 0;
      prevState = state;

      const results = [];
      for (const a of d.acts) {
        signal.throwIfAborted();
        ui.step('▸ ' + describe(a, state));

        if (a.a === 'memo') {
          scratchpad = a.append && scratchpad ? `${scratchpad}\n${a.text}`.slice(-6000) : a.text.slice(0, 6000);
          results.push(`${describe(a, state)}: ${t('aResult')}`);
          continue;
        }
        if (a.a === 'remember') {
          if (host && notesAdded++ < 3) await addNote(host, a.note);
          results.push(`${describe(a, state)}: ${t('aResult')}`);
          continue;
        }

        const targetEl = state.els.find(e => e.id === a.id);
        const clickKey = a.a === 'clickxy'
          ? `xy:${Math.round(a.x / 20)}:${Math.round(a.y / 20)}`
          : a.a === 'click'
            ? `el:${targetEl?.tag}:${targetEl?.label}`
            : '';

        let res;
        try {
          res = await execAction(c, a, tabId, windowId, signal, tabs, dbg, bannerTabs);
        } catch (e) {
          res = { ok: false, msg: String(e.message || e) };
        }

        // Playbook recording eligibility
        if (res.ok && recOK) {
          if (!RECORDABLE.includes(a.a)) {
            recOK = false;
            recWhy = pt ? `usou "${a.a}" (coordenadas/inspeção dinâmica)` : `used "${a.a}" (dynamic inspection/coordinates)`;
          } else {
            const isElAct = ['click', 'hover', 'type', 'clear', 'select'].includes(a.a);
            const el = isElAct ? targetEl : null;
            const act = { ...a };
            delete act.id;
            if (isElAct && !el) {
              recOK = false;
              recWhy = pt ? 'elemento sem referência' : 'element without reference';
            } else if (el && (el.secret || (a.a === 'click' && el.label.length <= 60 && RISKY.test(el.label)))) {
              recOK = false;
              recWhy = pt ? `passo sensível (“${el.label}”)` : `sensitive step (“${el.label}”)`;
            } else if (el && a.a === 'click' && !el.testid && el.label.length > 55) {
              recOK = false;
              recWhy = pt ? 'linha dinâmica com texto variável' : 'dynamic list item with changing preview text';
            } else {
              rec.push(el ? { act, loc: locOf(el) } : { act });
            }
          }
        }

        const switchedTab = res.tabId && res.tabId !== tabId;
        if (res.tabId) tabId = res.tabId;

        if (res.nav || res.settle) await waitSettle(tabId, !!res.nav, signal);

        // Check immediate state change on clicks to auto-escalate to native CDP click if synthetic click was swallowed!
        let postSnap = null;
        if (clickKey && res.ok && !switchedTab) {
          postSnap = await snap(tabId).catch(() => null);
          const immediateDiff = postSnap ? computeStateDiff(state, postSnap) : null;
          if (immediateDiff === 'NO_VISIBLE_CHANGE') {
            // Automatic CDP hardware-click fallback when a framework swallows synthetic DOM click on first repeat!
            if (a.a === 'click' && clickKey === lastClickKey && repeatedNoOpClicks === 1) {
              const [probe] = await chrome.scripting.executeScript({
                target: { tabId },
                func: (id) => {
                  const el = globalThis.__odyRefs?.map?.get(id)?.el;
                  if (!el) return null;
                  const r = el.getBoundingClientRect();
                  return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
                },
                args: [a.id]
              }).catch(() => []);
              if (probe?.result && await dbg.clickAt(tabId, probe.result.x, probe.result.y)) {
                await waitSettle(tabId, false, signal);
                postSnap = await snap(tabId).catch(() => postSnap);
              }
            }
            const afterRetryDiff = postSnap ? computeStateDiff(state, postSnap) : 'NO_VISIBLE_CHANGE';
            if (afterRetryDiff === 'NO_VISIBLE_CHANGE') {
              repeatedNoOpClicks = clickKey === lastClickKey ? repeatedNoOpClicks + 1 : 1;
              lastClickKey = clickKey;
              if (repeatedNoOpClicks >= 3) { ui.error(t('agentLoopClick')); return; }
            } else {
              repeatedNoOpClicks = 0; lastClickKey = '';
            }
          } else {
            repeatedNoOpClicks = 0; lastClickKey = clickKey;
          }
        } else if (!['look', 'inspect_region', 'rowicons', 'extract', 'wait', 'list_tabs'].includes(a.a)) {
          lastClickKey = ''; repeatedNoOpClicks = 0;
        }

        let nowUrl = '';
        if (res.nav || switchedTab) {
          try { nowUrl = (await chrome.tabs.get(tabId)).url || ''; } catch {}
        }

        results.push(
          `${describe(a, state)}: ` +
          (res.ok ? (res.msg ? `${t('aResult')} (${res.msg})` : t('aResult')) : `${t('aFail')}: ${res.msg || ''}`) +
          (switchedTab ? ` [switched to tabId=${tabId}]` : '') +
          (nowUrl ? ` [now at ${nowUrl.slice(0, 180)}]` : '') +
          (res.data ? `\n<page_text>\n${res.data}\n</page_text>` : '')
        );

        // Stop multi-action batch early if an action failed, navigated, or mutated interactive controls
        if (!res.ok || res.nav || switchedTab || res.settle) break;
      }

      note = results.join('\n');
      if (repeatedNoOpClicks >= 1) {
        note += `\nNOTICE: Clicking ${lastClickKey} caused NO_VISIBLE_CHANGE on the page. Check if a modal/cookie banner is blocking it, hover first, try an inner control, scroll, or use look/clickxy instead of clicking the same [id] again.`;
      }

      const stepSummaries = results.map(x => x.split('\n')[0].replace(/\s*\[now at.*$/, ''));
      const recentHist = hist.slice(-8).map(x => x.replace(/^\d+\.\s*/, ''));
      const repeatedAct = stepSummaries.find(l => !/^(Scroll|Deslizar|Scratchpad|Notas)/.test(l) && recentHist.filter(x => x === l).length >= 2);
      if (repeatedAct) {
        note += `\nWARNING: You already performed "${repeatedAct.slice(0, 80)}" multiple times recently without advancing. Choose a different strategy or finish with "done".`;
      }

      results.forEach(x => hist.push(`${hist.length + 1}. ${x.split('\n')[0].slice(0, 200)}`));
      if (hist.slice(-6).filter(x => /^\d+\.\s*(Look at the page|Ver a página)/.test(x)).length >= 5) {
        ui.error(t('agentLoopLook'));
        return;
      }
    }
    ui.error(t('agentMax'));
  } finally {
    await dbg.detach();
    for (const tid of bannerTabs) await setBanner(tid, false);
    await chrome.storage.session.remove(RUN_STATE_KEY).catch(() => {});
  }
}
