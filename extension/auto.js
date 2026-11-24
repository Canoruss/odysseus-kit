// Autonomous agent mode: the model drives the browser (open tabs, search, click) until the goal is done.
import { agentStep, agentLook, hasPerm } from './api.js';
import { snapshotFn, bannerFn, actFn, clickXYFn, probeXYFn, bpFn, formatState, AGENT_TOOLS, AGENT_SYS, callsToActions } from './autofns.js';
import { t } from './i18n.js';
import { hostOf, findPlaybook, savePlaybook, markPlaybook, getNotes, addNote, findEl, locOf, RISKY, RECORDABLE } from './playbook.js';

const sleep = ms => new Promise(r => setTimeout(r, ms));
async function waitLoad(tabId) {
  await sleep(700);
  for (let i = 0; i < 25; i++) { const tb = await chrome.tabs.get(tabId); if (tb.status === 'complete') break; await sleep(400); }
  await sleep(300);
}
async function snap(tabId) {
  const tb = await chrome.tabs.get(tabId);
  if (!/^https?:/.test(tb.url || '')) throw new Error('unsupported page');
  const [r] = await chrome.scripting.executeScript({ target: { tabId }, func: snapshotFn }); return r.result;
}
function describe(a, state) {
  const el = state.els.find(e => e.id === a.id);
  const label = el ? `${el.tag} “${el.label}”${el.href ? ' → ' + el.href : ''}` : '';
  switch (a.a) {
    case 'click': return `${t('aClick')} ${label}`;
    case 'type': return `${t('aType')} “${a.text}” → ${label}${a.submit ? ' ⏎' : ''}`;
    case 'select': return `${t('aSelect')} “${a.value}” → ${label}`;
    case 'scroll': return `${t('aScroll')} ${a.dir === 'up' ? '↑' : '↓'}`;
    case 'goto': return `${t('aGoto')} ${a.url}`;
    case 'look': return `${t('aLook')}: ${a.question}`;
    case 'remember': return (t('aBack') === 'Voltar' ? 'Guardar nota: ' : 'Remember: ') + a.note;
    case 'rowicons': return `${t('aRowicons')}: ${a.label}`;
    case 'clickxy': return `${t('aClickxy')} (${a.x}, ${a.y})`;
    case 'search': return `${t('aSearch')} “${a.text}”`;
    case 'newtab': return `${t('aNewtab')} ${a.url}`;
    case 'key': return `${t('aKey')} ${a.key}`;
    case 'wait': return `${t('aWait')} ${a.ms} ms`;
    case 'back': return t('aBack');
    default: return t('aExtract');
  }
}
async function exec(a, tabId, signal, tabs) {
  if (a.a === 'look') {
    const tb = await chrome.tabs.get(tabId);
    if (!tb.active) await chrome.tabs.update(tabId, { active: true });
    await sleep(250);
    const { src } = await tabs.captureImage(tabId, 60);
    signal.throwIfAborted();
    const d = await agentLook(C, src.slice(src.indexOf(',') + 1), a.question, signal);
    return { ok: true, data: String(d.text || '') };
  }
  if (a.a === 'clickxy') {
    const dbg = { tabId };
    if (await chrome.permissions.contains({ permissions: ['debugger'] })) {
      const [p] = await chrome.scripting.executeScript({ target: { tabId }, func: probeXYFn, args: [a] });
      if (!p.result.ok) return { ...p.result, nav: true };
      let attached = false;
      try {
        await chrome.debugger.attach(dbg, '1.3'); attached = true;
        const m = (type, extra) => chrome.debugger.sendCommand(dbg, 'Input.dispatchMouseEvent', { type, x: p.result.px, y: p.result.py, button: 'left', ...extra });
        await m('mouseMoved', { buttons: 0 }); await m('mousePressed', { buttons: 1, clickCount: 1 }); await sleep(60); await m('mouseReleased', { buttons: 0, clickCount: 1 });
        await sleep(600);
        return { ok: true, data: p.result.data + ' (real click)', nav: true };
      } catch {} finally { if (attached) await chrome.debugger.detach(dbg).catch(() => {}); }
    }
    const [r] = await chrome.scripting.executeScript({ target: { tabId }, func: clickXYFn, args: [a] }); await sleep(600); return { ...r.result, nav: true };
  }
  if (a.a === 'goto') { await chrome.tabs.update(tabId, { url: a.url }); return { ok: true, nav: true }; }
  if (a.a === 'search') { await chrome.search.query({ text: a.text, tabId }); return { ok: true, nav: true }; }
  if (a.a === 'back') { await chrome.tabs.goBack(tabId); return { ok: true, nav: true }; }
  if (a.a === 'wait') { await sleep(a.ms); return { ok: true }; }
  if (a.a === 'newtab') { const nt = await chrome.tabs.create({ url: a.url, active: true }); return { ok: true, nav: true, tabId: nt.id }; }
  const [r] = await chrome.scripting.executeScript({ target: { tabId }, func: actFn, args: [a] });
  if (a.a === 'select' && r.result?.ok) await sleep(1500); // dependent selects/postbacks: let the page repopulate, then re-read it
  return { ...r.result, nav: a.a === 'select' || a.a === 'click' || a.a === 'key' || (a.a === 'type' && a.submit) };
}
// Replay a saved recipe without the model: find each element by what it is (testid/label), not by position.
async function replay(pb, tabId, signal, ui, tabs, pt) {
  const done = [], collected = [];
  for (let i = 0; i < pb.steps.length; i++) {
    signal.throwIfAborted();
    const s = pb.steps[i], a = { ...s.act };
    ui.step(`▸ [${i + 1}/${pb.steps.length}] ` + (s.loc ? `${a.a} “${s.loc.label}”` : a.a + (a.url ? ' ' + a.url : a.text ? ' “' + a.text + '”' : '')));
    if (s.loc) {
      let id = null;
      for (let k = 0; k < 10 && id == null; k++) { const st = await snap(tabId).catch(() => null); const e = st && findEl(st.els, s.loc); if (e) id = e.id; else await sleep(500); }
      if (id == null) return { ok: false, at: i, why: (pt ? 'elemento não encontrado: ' : 'element not found: ') + s.loc.label, done, collected, tabId };
      a.id = id;
    }
    let res; try { res = await exec(a, tabId, signal, tabs); } catch (e) { res = { ok: false, msg: String(e.message || e) }; }
    if (!res.ok) return { ok: false, at: i, why: res.msg || 'failed', done, collected, tabId };
    if (res.tabId) tabId = res.tabId;
    if (res.nav) await waitLoad(tabId); else await sleep(700);
    if (a.a === 'extract' && res.data) collected.push(`[step ${i + 1}]\n` + String(res.data).slice(0, 1500));
    done.push(s);
  }
  return { ok: true, done, collected, tabId };
}
const HOSTS = { origins: ['<all_urls>'] };
const HOSTS_DBG = { origins: ['<all_urls>'], permissions: ['debugger'] };
// ui: { step(text), live(text), final(text), error(text) }. Resolves when finished; throws on abort.
let C;
export async function runAuto(c, goal, signal, ui, tabs) {
  C = c;
  if (!(await chrome.permissions.contains(HOSTS_DBG))) {
    const ok = await chrome.permissions.request(HOSTS_DBG).catch(() => false) || (!(await chrome.permissions.contains(HOSTS)) && await chrome.permissions.request(HOSTS).catch(() => false));
    if (!ok && !(await chrome.permissions.contains(HOSTS))) { ui.error(t('agentPerm')); return; }
  }
  const [cur] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
  let tab = cur;
  if (!tab?.id || !/^https?:/.test(tab.url || '')) tab = await chrome.tabs.create({ url: 'https://www.google.com/', active: true }), await waitLoad(tab.id);
  let tabId = tab.id, note = '', hist = [], nudges = 0, retries = 0;
  ui.step('▸ Odysseus ' + chrome.runtime.getManifest().version);
  if (/boarding|embarque/i.test(goal) && /\b(circles?|c[ií]rculos?|enter details|id upload|verific\w*|check\w*|audit\w*|todos|all|every)\b/i.test(goal)) {
    let enso = /ensoconnect/.test(tab.url || '') ? tab : (await chrome.tabs.query({ url: '*://*.ensoconnect.com/*' }))[0];
    if (enso) { if (enso.id !== tab.id) { await chrome.tabs.update(enso.id, { active: true }); await chrome.windows.update(enso.windowId, { focused: true }).catch(() => {}); await sleep(800); } return bpAudit(enso.id, signal, ui); }
  }
  const pt = t('aBack') === 'Voltar', host = hostOf(tab.url);
  const stepFn = c.stepFn || agentStep;
  let rec = [], recOK = true, recWhy = '', notesAdded = 0;
  const notes = host ? await getNotes(host) : [];
  const SYS = AGENT_SYS + (notes.length ? `\n\nNOTES LEARNED EARLIER ABOUT ${host} (may be outdated; verify on the page):\n` + notes.map(n => '- ' + n).join('\n') : '');
  if (host && !/\b(sem receita|no recipe|reaprender|relearn)\b/i.test(goal)) {
    const pb = await findPlaybook(host, goal);
    if (pb) {
      ui.step('▸ ' + (pt ? `Receita guardada (${pb.steps.length} passos, usada ${pb.runs}×): a repetir sem modelo` : `Saved recipe (${pb.steps.length} steps, used ${pb.runs}×): replaying without the model`));
      try { await chrome.scripting.executeScript({ target: { tabId }, func: bannerFn, args: [true, t('working'), t('stop')] }); } catch {}
      let rr;
      try { rr = await replay(pb, tabId, signal, ui, tabs, pt); } finally { try { await chrome.scripting.executeScript({ target: { tabId: rr?.tabId || tabId }, func: bannerFn, args: [false] }); } catch {} }
      tabId = rr.tabId || tabId;
      if (rr.ok) {
        await markPlaybook(host, pb, true);
        let st = null; try { st = await snap(tabId); } catch {}
        const ctx = rr.collected.join('\n\n').slice(0, 24000);
        try {
          const r = await stepFn(c, [{ role: 'system', content: AGENT_SYS }, { role: 'user', content: 'User goal: ' + goal + '\n\nThe recorded steps were replayed. Collected page text:\n<page_text>\n' + ctx + '\n</page_text>\n\n' + (st ? formatState(st) : '') + '\n\nAnswer the goal from this data and call done. Do not act.' }], AGENT_TOOLS.filter(x => x.function.name === 'done'), tx => ui.live(tx), signal);
          const d = callsToActions(r.calls); ui.final(d.done || r.text || ctx || '✓');
        } catch (e) { if (signal.aborted) throw e; ui.final(ctx || '✓'); }
        return;
      }
      const dropped = await markPlaybook(host, pb, false);
      ui.step('▸ ' + (pt ? `A receita falhou no passo ${rr.at + 1} (${rr.why}); o agente continua daqui${dropped ? ' e a receita antiga foi apagada' : ''}` : `Recipe failed at step ${rr.at + 1} (${rr.why}); the agent continues from here${dropped ? ' and the old recipe was dropped' : ''}`));
      rec = rr.done.slice(); note = `The saved recipe failed at step ${rr.at + 1} (${rr.why}). The first ${rr.done.length} steps were already replayed; continue from the current page.`;
    }
  }
  const visited = new Set();
  let lastClickKey = "", lastClickState = "", repeatedClicks = 0;
  try {
    for (let step = 1; step <= 250; step++) {
      signal.throwIfAborted();
      try { await chrome.scripting.executeScript({ target: { tabId }, func: bannerFn, args: [true, t('working'), t('stop')] }); } catch {}
      let state; try { state = await snap(tabId); } catch { ui.error(t('agentNoRead')); return; }
      const msgs = [{ role: 'system', content: SYS }, { role: 'user', content: 'User goal: ' + goal + (hist.length ? '\n\nSteps so far:\n' + hist.slice(-8).join('\n') : '') + (note ? '\n\nLast result:\n' + note : '') + '\n\n' + formatState(state) }];
      let r;
      try { r = await stepFn(c, msgs, AGENT_TOOLS, tx => ui.live(tx), signal); retries = 0; }
      catch (e) {
        if (signal.aborted) throw e;
        if (!e.status || e.status >= 500 || e.status === 429 || e.code === 'serverStream' || e.code === 'emptyReply') {
          if (++retries > 6) { ui.error(t('agentBusy')); return; }
          ui.step('… ' + t('agentRetry') + ' (' + retries + '/6)'); await sleep(Math.min(25000, 3000 * 2 ** (retries - 1)) + Math.random() * 1500); step--; continue;
        }
        throw e;
      }
      const d = callsToActions(r.calls);
      if (d.done != null) {
        if (host && recOK && /(n[aã]o consegui|n[aã]o foi poss[ií]vel|n[aã]o encontrei|n[aã]o abriu|could not|couldn't|unable to|did not open|failed to|not found)/i.test(String(d.done).slice(0, 400))) { recOK = false; recWhy = pt ? 'a tarefa não terminou com sucesso' : 'the task did not finish successfully'; }
        if (host && recOK && rec.length >= 2 && rec.length <= 60) { await savePlaybook(host, goal, rec); ui.step('▸ ' + (pt ? `Receita guardada (${rec.length} passos): da próxima vez corre sem modelo` : `Recipe saved (${rec.length} steps): next time it runs without the model`)); }
        else if (host && !recOK && recWhy) ui.step('▸ ' + (pt ? 'Receita não guardada: ' : 'Recipe not saved: ') + recWhy);
        ui.final(d.done || '✓'); return;
      }
      if (!d.acts.length) { if (++nudges > 3) { ui.final(r.text || t('agentMax')); return; } note = 'You must call a tool (or done).'; continue; }
      nudges = 0;
      const results = [];
      for (const a of d.acts) {
        signal.throwIfAborted();
        if (a.a === 'click' || a.a === 'clickxy') {
          const target = state.els.find(e => e.id === a.id);
          const key = a.a === 'clickxy' ? `xy:${Math.round(a.x / 20)}:${Math.round(a.y / 20)}` : `element:${target?.tag}:${target?.label}`;
          const signature = JSON.stringify([state.url, state.text, state.els.map(e => [e.tag, e.label, e.expanded, e.checked])]);
          repeatedClicks = key === lastClickKey && signature === lastClickState ? repeatedClicks + 1 : 1;
          lastClickKey = key; lastClickState = signature;
          if (repeatedClicks >= 4) { ui.error('A automação parou: o mesmo alvo foi clicado repetidamente sem alteração visível. Os resultados podem estar incompletos.'); return; }
        } else if (!['look', 'rowicons', 'extract', 'wait', 'remember'].includes(a.a)) { lastClickKey = ''; repeatedClicks = 0; }
        ui.step('▸ ' + describe(a, state));
        let res, before = '';
        try { before = (await chrome.tabs.get(tabId)).url || ''; } catch {}
        if (a.a === 'remember') { if (host && notesAdded++ < 3) await addNote(host, a.note); res = { ok: true }; }
        else try { res = await exec(a, tabId, signal, tabs); } catch (e) { res = { ok: false, msg: String(e.message || e) }; }
        if (res.ok && recOK && a.a !== 'remember') {
          if (!RECORDABLE.includes(a.a)) { recOK = false; recWhy = pt ? `usou "${a.a}" (leitura visual/coordenadas não se repetem de forma fiável)` : `it used "${a.a}" (visual reads/coordinates are not replayable reliably)`; }
          else {
            const el = ['click', 'type', 'select'].includes(a.a) ? state.els.find(e => e.id === a.id) : null, act = { ...a }; delete act.id;
            if (['click', 'type', 'select'].includes(a.a) && !el) { recOK = false; recWhy = pt ? 'elemento sem referência' : 'element without reference'; }
            else if (el && (el.secret || (a.a === 'click' && el.label.length <= 60 && RISKY.test(el.label)))) { recOK = false; recWhy = pt ? `passo sensível (“${el.label}”): pede sempre confirmação, por isso não gravo` : `sensitive step (“${el.label}”): needs confirmation each time, not recorded`; }
            else if (el && a.a === 'click' && !el.testid && el.label.length > 45) { recOK = false; recWhy = pt ? 'clique numa linha de lista com dados que mudam (ex.: chat); não é repetível' : 'click on a list row with changing data (e.g. a chat); not repeatable'; }
            else rec.push(el ? { act, loc: locOf(el) } : { act });
          }
        }
        if (res.tabId) tabId = res.tabId;
        let now = ''; if (res.nav) { await waitLoad(tabId); try { now = (await chrome.tabs.get(tabId)).url || ''; } catch {} }
        if (a.a === 'click' && res.nav && now) {
          if (now !== before && goal.length < 200 && (visited.has(now) || /youtube\.com\/watch/.test(now) && /\b(open|play|watch|abr[ei]|ver|reprodu)/i.test(goal))) { ui.final(t('agentOpened') + ' ' + now); return; }
          visited.add(now);
        }
        results.push(`${describe(a, state)}: ` + (res.ok ? t('aResult') : t('aFail') + ': ' + (res.msg || '')) + (now ? ' [now at ' + now + ']' : '') + (res.data ? '\n<page_text>\n' + res.data + '\n</page_text>' : ''));
        if (!res.ok || res.nav) break;
      }
      note = results.join('\n');
      const last = results.map(x => x.split('\n')[0].replace(/\s*\[now at.*$/, '')), h = hist.slice(-3).map(x => x.replace(/^\d+\.\s*/, ''));
      { const rec = hist.slice(-10).map(x => x.replace(/^\d+\.\s*/, '')); const rep = last.find(l => !/^(Scroll|Rolar)/.test(l) && rec.filter(x => x === l).length >= 2);
        if (rep) note += '\nWARNING: you already did "' + rep.slice(0, 80) + '" several times recently and it did not move the task forward. Do NOT do it again. Use a different action (rowicons, clickxy with coordinates you already have, the next row, or scroll) or finish with done.';
        if (d.acts.some(x => x.a === 'look') && rec.filter(x => /^(Look at the page|Ver a página)/.test(x)).length >= 3) note += '\nYou have used look many times: act now on the answers you already have.'; }
      if (last.length && h.length === 3 && h.every(x => x === last[0])) note += '\nWARNING: you repeated the same action 4 times and nothing changed. Do something different or finish with done explaining what blocks you.';
      results.forEach(x => hist.push((hist.length + 1) + '. ' + x.split('\n')[0].slice(0, 200)));
      if (hist.slice(-6).filter(x => /^\d+\.\s*(Look at the page|Ver a página)/.test(x)).length >= 5) { ui.error('Agent stopped: it used "look" 5 times in a row without acting (loop). Try the Boarding Pass audit wording or another model.'); return; }
    }
    ui.error(t('agentMax'));
  } finally { try { await chrome.scripting.executeScript({ target: { tabId }, func: bannerFn, args: [false] }); } catch {} }
}

// Boarding Pass audit without the model: go through every Resolved guest and read the first two circles.
async function bpAudit(tabId, signal, ui) {
  const run = async (op, arg) => (await chrome.scripting.executeScript({ target: { tabId }, func: bpFn, args: [op, arg ?? null] }))[0].result;
  const realClick = async (key) => {
    if (!(await chrome.permissions.contains({ permissions: ['debugger'] }))) return false;
    const p = await run('rect', key); if (!p?.ok) return false;
    const dbg = { tabId }; let att = false;
    try { await chrome.debugger.attach(dbg, '1.3'); att = true;
      const m = (type, extra) => chrome.debugger.sendCommand(dbg, 'Input.dispatchMouseEvent', { type, x: p.x, y: p.y, button: 'left', ...extra });
      await m('mouseMoved', { buttons: 0 }); await m('mousePressed', { buttons: 1, clickCount: 1 }); await sleep(60); await m('mouseReleased', { buttons: 0, clickCount: 1 }); return true;
    } catch { return false; } finally { if (att) await chrome.debugger.detach(dbg).catch(() => {}); }
  };
  try { await chrome.scripting.executeScript({ target: { tabId }, func: bannerFn, args: [true, t('working'), t('stop')] }); } catch {}
  const seen = new Set(), bad = [], unk = [], good = []; let stuck = 0;
  const pt = t('aBack') === 'Voltar';
  const cn = (c) => pt ? ({ green: 'verde', grey: 'cinzento', blue: 'azul', unknown: 'cor desconhecida' }[c] || c) : c;
  try {
    ui.step('▸ ' + (pt ? 'Auditoria Boarding Pass (sem modelo, Enter details + Id upload): a ir ao topo da lista' : 'Boarding Pass audit (no model, Enter details + Id upload): going to the top of the list'));
    try { await chrome.scripting.executeScript({ target: { tabId }, func: () => { const b = [...document.querySelectorAll('button,[role=tab],a')].find((e) => /^\s*resolved\b/i.test(e.innerText || '')); if (b) b.click(); return !!b; } }); await sleep(1500); } catch {}
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
        if (!res?.ok) { unk.push(r.name + ' — ' + (res?.why === 'nobp' ? (pt ? 'sem Boarding Pass (sem reserva?)' : 'no Boarding Pass (no booking?)') : res?.why === 'closed' ? (pt ? 'o dropdown do Boarding Pass não abriu' : 'Boarding Pass dropdown did not open') : (pt ? 'a conversa não abriu' : 'chat did not open'))); continue; }
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
  } finally { try { await chrome.scripting.executeScript({ target: { tabId }, func: bannerFn, args: [false] }); } catch {} }
}
