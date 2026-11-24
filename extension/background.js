import { address, getCfg, hasPerm, pullCommands } from './api.js';
import { t } from './i18n.js';

const menus = { sum: 'menuSum', exp: 'menuExplain', tr: 'menuTranslate', ask: 'menuAsk' };
async function configure() {
  await chrome.storage.local.setAccessLevel({ accessLevel: 'TRUSTED_CONTEXTS' });
  await chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });
  await new Promise(resolve => chrome.contextMenus.removeAll(resolve));
  for (const [id, key] of Object.entries(menus)) chrome.contextMenus.create({ id, title: t(key), contexts: ['selection'], documentUrlPatterns: ['https://*/*', 'http://*/*'] });
}
chrome.runtime.onInstalled.addListener(configure);
chrome.runtime.onStartup.addListener(configure);
chrome.windows.onRemoved.addListener(windowId => { chrome.storage.session.remove(['thread:' + windowId, 'menu:' + windowId]); });
chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (!Object.hasOwn(menus, info.menuItemId) || !tab?.id || info.editable || !info.selectionText?.trim()) return;
  let page; try { page = new URL(info.frameUrl || info.pageUrl || tab.url); } catch { return; }
  if (!['http:', 'https:'].includes(page.protocol)) return;
  // Open synchronously during the menu gesture. Either a new or an existing panel can receive the draft.
  chrome.sidePanel.open({ windowId: tab.windowId }).catch(() => {});
  const draft = { id: crypto.randomUUID(), at: Date.now(), kind: info.menuItemId, title: (tab.title || '').slice(0, 200), url: (page.origin + page.pathname).slice(0, 2000), text: info.selectionText.slice(0, 20000), clipped: info.selectionText.length > 20000 };
  chrome.storage.session.set({ ['menu:' + tab.windowId]: draft });
});

// Commands queued on the server (e.g. "open this video") are opened in a new tab.
async function pollCommands() {
  try {
    const c = await getCfg();
    if (!c.url || !c.token || !await hasPerm(c)) return;
    for (const cmd of (await pullCommands(c)).slice(0, 5)) {
      if (cmd?.a !== 'open' || typeof cmd.url !== 'string' || cmd.url.length > 2000) continue;
      let u; try { u = new URL(cmd.url); } catch { continue; }
      if (!['http:', 'https:'].includes(u.protocol) || u.username || u.password) continue;
      await chrome.tabs.create({ url: u.href, active: true });
    }
  } catch {}
}
function schedulePoll() { chrome.alarms.create('cmd', { periodInMinutes: 0.5 }); }
chrome.alarms.onAlarm.addListener(a => { if (a.name === 'cmd') pollCommands(); });
chrome.runtime.onInstalled.addListener(schedulePoll);
chrome.runtime.onStartup.addListener(() => { schedulePoll(); pollCommands(); });
schedulePoll();
