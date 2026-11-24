export const blankThread = () => ({ sid: null, messages: [], draft: '' });
const MAX_SAVED_CHARS = 160000;
// Store the most recent portion of the conversation for this window only.
export function snapshotThread(thread, scope, maxChars = MAX_SAVED_CHARS) {
  let left = maxChars;
  const messages = [];
  for (const m of thread.messages.slice(-60).reverse()) {
    if (left <= 0) break;
    const text = m.text.length > left ? m.text.slice(0, left) + ' …' : m.text;
    messages.unshift({ ...m, text }); left -= text.length;
  }
  return { scope, sid: thread.sid, ...(thread.historyId ? { historyId: thread.historyId, historySaved: !!thread.historySaved } : {}), draft: thread.draft.slice(0, 32000), messages };
}
export function restoreThread(saved, scope) {
  if (!saved || saved.scope !== scope || !Array.isArray(saved.messages)) return blankThread();
  return { sid: saved.sid ?? null, ...(saved.historyId ? { historyId: saved.historyId, historySaved: saved.historySaved !== false } : {}), draft: typeof saved.draft === 'string' ? saved.draft.slice(0, 32000) : '', messages: saved.messages.filter(m => ['user', 'assistant', 'note'].includes(m?.role) && typeof m.text === 'string').slice(-60) };
}
