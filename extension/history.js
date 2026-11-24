import { Problem } from './api.js';
import { t } from './i18n.js';
import { snapshotThread } from './thread.js';

export const historyEnabledKey = 'saveConversationHistory';
const prefix = 'savedConversation:';
const keyFor = id => prefix + id;
const locked = fn => navigator.locks.request('odysseus-conversation-history', fn);

export function titleFor(messages) {
  return messages.find(m => m.role === 'user')?.text.replace(/\s+/g, ' ').trim().slice(0, 100) || t('untitledChat');
}

export async function historyEntries() {
  const entries = await chrome.storage.local.get(null);
  return Object.entries(entries).filter(([key, item]) => key.startsWith(prefix) && item && key === keyFor(item.id) && typeof item.title === 'string' && Number.isFinite(item.updatedAt) && Array.isArray(item.messages))
    .map(([, item]) => item).sort((a, b) => b.updatedAt - a.updatedAt);
}

export function setHistoryEnabled(value) {
  return locked(() => chrome.storage.local.set({ [historyEnabledKey]: value }));
}

export function saveArchived(id, record, creating) {
  return locked(async () => {
    const key = keyFor(id);
    const state = await chrome.storage.local.get([key, historyEnabledKey]);
    if (!state[historyEnabledKey]) return false;
    const existing = state[key];
    if (!existing && !creating) throw new Problem('historyMissing');
    await chrome.storage.local.set({ [key]: { ...record, id, title: existing?.title ?? titleFor(record.messages), updatedAt: Date.now() } });
    return true;
  });
}

function withArchived(id, action) {
  return locked(async () => {
    const key = keyFor(id), stored = (await chrome.storage.local.get(key))[key];
    if (!stored) throw new Problem('historyMissing');
    return action(stored, key);
  });
}

function inOtherWindow(id, currentKey, states) {
  return Object.entries(states).some(([key, record]) => key.startsWith('thread:') && key !== currentKey && record?.historyId === id);
}

export function renameArchived(id, title) {
  return withArchived(id, (item, key) => chrome.storage.local.set({ [key]: { ...item, title: title.trim().slice(0, 100) || titleFor(item.messages) } }));
}

export function deleteArchived(id, threadKey) {
  return withArchived(id, async (_, key) => {
    if (inOtherWindow(id, threadKey, await chrome.storage.session.get(null))) throw new Problem('historyInUse');
    await chrome.storage.local.remove(key);
  });
}

export function resumeArchived(id, threadKey, scope) {
  return withArchived(id, async item => {
    if (item.scope !== scope) throw new Problem('historyScope');
    const active = await chrome.storage.session.get(null);
    if (inOtherWindow(id, threadKey, active)) throw new Problem('historyInUse');
    const record = { ...item, draft: active[threadKey]?.historyId === id ? active[threadKey].draft : '', historyId: id, historySaved: true };
    await chrome.storage.session.set({ [threadKey]: record });
    return record;
  });
}

export function durableConversation(thread, scope) {
  const { draft, historyId, historySaved, ...record } = snapshotThread(thread, scope, 100000);
  return record;
}

export function transcriptMarkdown(title, messages) {
  const heading = String(title).replace(/\s+/g, ' ').trim();
  const turns = messages.map(m => {
    const speaker = m.role === 'user' ? t('you') : m.role === 'assistant' ? 'Odysseus' : t('guide');
    const kind = m.guide && m.role !== 'note' ? ` · ${t('guide')}` : '';
    const status = m.partial ? ` · ${t('partial')}` : '';
    const sources = m.sources?.length ? `\n\n${t('attachments')} · ${m.sources.join(' · ').replace(/[\r\n]+/g, ' ')}` : '';
    return `## ${speaker}${kind}${status}\n\n${m.text}${sources}`;
  });
  return [`# ${heading}`, ...turns].join('\n\n') + '\n';
}

export function downloadTranscript(title, messages) {
  const slug = title.normalize('NFKD').replace(/[^a-z0-9 -]/gi, '').trim().replace(/\s+/g, '-').slice(0, 70) || 'odysseus-chat';
  const url = URL.createObjectURL(new Blob([transcriptMarkdown(title, messages)], { type: 'text/markdown;charset=utf-8' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = slug + '.md';
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
