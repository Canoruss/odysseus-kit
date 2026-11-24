# Browser extension

**English** · [Português](EXTENSION.pt.md)

A side-panel assistant for Chrome, Edge and other Chromium browsers that talks to **your own Odysseus server**. Folder: [`extension/`](../extension). Version 0.12.20. No build step, no runtime dependencies, no third-party servers.

## Install

1. Download `odysseus-kit-extension-<version>.zip` from the [latest release](../../../releases/latest) (or use the `extension/` folder of this repository) and extract it.
2. Open `chrome://extensions` (or `edge://extensions`), turn on **Developer mode**, choose **Load unpacked** and select the folder that contains `manifest.json`.
3. Pin **Odysseus** to the toolbar and click its icon on a normal web page.
4. Open **Settings** (gear icon) and enter:
   - **Server address**, for example `https://your-server.your-tailnet.ts.net` (include a port or path prefix if your proxy uses one);
   - an **Odysseus API token with the `chat` scope** (create it in your Odysseus settings).
5. Press **Test connection**, then **Save settings**. The browser asks for permission to reach only that server.

To update, replace the folder contents with the new release and click **Reload** on the extension card. Saved settings are kept. (The built-in self-update needs an update endpoint on your server, which the KIT does not ship; without it the update check does nothing.)

## What it does

| Feature | How to use it |
|---|---|
| **Chat** | Type and press Enter (Shift+Enter for a new line). Esc or Stop interrupts. Code blocks have copy buttons. |
| **Page and Selection** | Attach the current page text or your selection. Expand the attachment to see exactly what will be sent. The right-click menu prepares drafts. |
| **Several tabs** | Attach up to three tabs with **Compare tabs**. Long pages use *Relevant excerpts* (only passages that match your question) or *Full captures* (up to 20,000 characters per page). |
| **Screenshot and files** | Up to 4 files, 10 MiB each and 16 MiB in total. Supported types depend on your Odysseus server. |
| **Page guide** | Describe a goal; the assistant proposes **one step at a time**. *Show on page* highlights the target, *Apply this step* performs one click, fill, choice, scroll or navigation, and *Get next step* shares a fresh snapshot. Nothing happens without your approval. |
| **Agent mode** | Describe a goal (for example *search YouTube for a video and open the most viewed*). The agent opens tabs, searches, clicks and reads pages by itself until the goal is done or it reaches its step limit. **Stop** works at any time. It never types passwords or pays. It asks for permission to act on web pages the first time. |
| **History** | Chats are saved on this browser (you can pause saving): search them, rename, resume, delete or export as Markdown. |
| **Timing** | Under each reply, see how long connection, local preparation and the first streamed text took. |
| **Languages** | English and European Portuguese, following the browser language. |

## Privacy

- The extension only talks to the server you enter. It asks for that single host permission, not for all sites.
- Page text is sent **only when you attach it** (or run a Page guide step). The Page guide ignores password, card and file fields.
- The token is stored in the browser's extension storage; **Disconnect and forget token** removes it and the host permission.
- The optional `debugger` permission (used to perform some clicks in Agent mode) is only requested when needed, and you can refuse it.

## Troubleshooting

| Problem | Fix |
|---|---|
| *Test connection* fails | Check the address (https, port, prefix) and that the token has the `chat` scope. Open the address in a tab to confirm the server answers. |
| Empty model list | Your server may not expose model discovery. Type a model name in Settings or leave it blank for the server default. |
| Panel does not open | Click the toolbar icon on a normal web page (not `chrome://` pages). |
