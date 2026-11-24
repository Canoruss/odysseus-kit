import { downloadTranscript, historyEntries } from './history.js';
import { explain, lang, t } from './i18n.js';
import { button, el } from './view.js';

export function bindHistoryView(callbacks) {
  const $ = id => document.getElementById(id);
  const panel = $('historyPanel'), query = $('historyQuery'), list = $('historyList'), detail = $('historyDetail');
  const toggle = $('historyEnabled'), status = $('historyStatus');
  let entries = [], selectedId, open = false, busy = false;
  query.placeholder = t('historySearch');
  function drawList() {
    list.replaceChildren();
    const needle = query.value.trim().toLocaleLowerCase(lang());
    const matches = entries.filter(item => !needle || item.title.toLocaleLowerCase(lang()).includes(needle) || item.messages.some(m => m.text.toLocaleLowerCase(lang()).includes(needle)));
    if (!matches.length) list.append(el('p', 'history-hint', t(entries.length ? 'historyNoMatch' : 'historyEmpty')));
    const calendar = new Intl.DateTimeFormat(lang(), { dateStyle: 'medium', timeStyle: 'short' });
    for (const item of matches) {
      const row = button('', () => { selectedId = item.id; status.textContent = ''; draw(); }, 'history-entry');
      row.append(el('strong', '', item.title), el('small', '', calendar.format(item.updatedAt)));
      list.append(row);
    }
  }
  async function load() { entries = await historyEntries(); }
  async function perform(action) {
    if (busy) return;
    busy = true; panel.inert = true; status.textContent = ''; callbacks.changed();
    try { await action(); if (open) await load(); }
    catch (e) { status.textContent = explain(e); }
    finally { busy = false; panel.inert = false; callbacks.changed(); if (open) draw(); }
  }
  function draw() {
    const item = entries.find(x => x.id === selectedId);
    list.hidden = !!item; detail.hidden = !item; query.hidden = !!item;
    toggle.checked = callbacks.enabled(); toggle.disabled = busy;
    $('exportCurrent').disabled = busy || !callbacks.hasCurrent();
    if (!item) { drawList(); return; }
    detail.replaceChildren();
    const back = button(t('historyBack'), () => { selectedId = null; status.textContent = ''; draw(); query.focus(); });
    const form = el('form', 'history-title-row'), title = el('input');
    title.value = item.title; title.maxLength = 100; title.setAttribute('aria-label', t('historyTitle'));
    const save = el('button', '', t('renameChat')); save.type = 'submit';
    form.onsubmit = e => { e.preventDefault(); perform(() => callbacks.rename(item.id, title.value)); };
    form.append(title, save);
    const actions = el('div', 'history-actions');
    const resume = button(t('resumeChat'), () => perform(() => callbacks.resume(item.id)), 'primary');
    resume.disabled = !callbacks.compatible(item);
    const remove = button(t('deleteChat'), () => {
      const prompt = el('p', '', t('confirmDeleteChat'));
      const confirm = button(t('deleteConfirm'), () => perform(async () => { await callbacks.remove(item.id); selectedId = null; }));
      const cancel = button(t('cancel'), draw);
      actions.replaceChildren(prompt, confirm, cancel); confirm.focus();
    });
    actions.append(resume, button(t('exportMarkdown'), () => downloadTranscript(item.title, item.messages)), remove);
    detail.append(back, form, actions);
    if (resume.disabled) detail.append(el('p', 'history-hint', t('historyScope')));
    const transcript = el('div', 'history-transcript');
    transcript.append(...item.messages.map(callbacks.message));
    detail.append(transcript);
  }
  query.oninput = drawList;
  toggle.onchange = () => perform(() => callbacks.setEnabled(toggle.checked));
  $('exportCurrent').onclick = callbacks.exportCurrent;
  const change = async value => {
    open = value; panel.hidden = !open;
    $('historyToggle').setAttribute('aria-expanded', String(open));
    callbacks.changed();
    if (!open) return;
    selectedId = null; query.value = ''; status.textContent = '';
    list.replaceChildren(); list.hidden = false; detail.hidden = true; query.hidden = false;
    await perform(async () => { await callbacks.ready(); });
    if (open) query.focus();
  };
  return { get open() { return open; }, get busy() { return busy; }, change };
}
