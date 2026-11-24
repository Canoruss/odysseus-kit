import { Problem } from './api.js';
import { pageCommand } from './agent.js';

export function bindTabs(windowId) {
  let changes = 0;
  chrome.tabs.onActivated.addListener(info => { if (info.windowId === windowId) changes++; });
  async function active() {
    const [tab] = await chrome.tabs.query({ active: true, windowId });
    if (tab?.id == null) throw new Problem('noPage');
    return tab.id;
  }
  async function inject(tabId, op, arg = {}, documentId) {
    let result;
    try {
      [result] = await chrome.scripting.executeScript({ target: documentId ? { tabId, documentIds: [documentId] } : { tabId }, world: 'ISOLATED', func: pageCommand, args: [op, arg] });
    } catch { throw new Problem(documentId ? 'stale' : 'noPage'); }
    if (!result?.result) throw new Problem(documentId ? 'stale' : 'noPage');
    if (result.result.error) throw new Problem(result.result.error);
    return result;
  }
  async function capture(op, expectedTab) {
    const generation = changes, tabId = await active();
    if (expectedTab != null && tabId !== expectedTab) throw new Problem('guideTab');
    const { result, documentId } = await inject(tabId, op);
    if (await active() !== tabId || changes !== generation) throw new Problem('tabChanged');
    return { ...result, tabId, documentId };
  }
  async function captureImage(expectedTab, quality) {
    const generation = changes, before = await capture('meta', expectedTab);
    let src;
    try { src = await chrome.tabs.captureVisibleTab(windowId, { format: 'jpeg', quality }); }
    catch { throw new Problem('noShot'); }
    const after = await capture('meta');
    if (before.tabId !== after.tabId || before.documentId !== after.documentId || before.currentHref !== after.currentHref || changes !== generation) throw new Problem('tabChanged');
    if (!src.startsWith('data:image/jpeg;base64,')) throw new Problem('noShot');
    return { src, before };
  }
  async function screenshot() {
    const { src, before } = await captureImage(undefined, 78);
    const raw = atob(src.slice(src.indexOf(',') + 1));
    const bytes = Uint8Array.from(raw, c => c.charCodeAt(0));
    return { title: before.title, url: before.url, file: new File([bytes], 'screenshot.jpg', { type: 'image/jpeg' }) };
  }
  async function review(frame, action, op, signal) {
    if (await active() !== frame.tabId) throw new Problem('guideTab');
    signal?.throwIfAborted();
    return (await inject(frame.tabId, op, { token: frame.token, action }, frame.documentId)).result;
  }
  return { capture, captureImage, screenshot, review };
}
