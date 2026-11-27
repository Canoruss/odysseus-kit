# Odysseus 0.13.1

A Chrome and Edge side-panel assistant for a private Odysseus server. It opens in Chat and offers a Page guide for reviewed browser actions. The interface follows the browser language and includes English and European Portuguese. The extension runs directly from this folder, with no build step or runtime dependencies.

## Install and connect

1. Extract the ZIP. Open `chrome://extensions` in Chrome or `edge://extensions` in Edge, turn on **Developer mode**, choose **Load unpacked**, and select the `odysseus-extension` folder containing `manifest.json`.
2. Pin Odysseus, open a regular web page and click its toolbar icon. In the panel, open **Settings** with the gear button.
3. Enter the server base address and an Odysseus API token with the `chat` scope. Include a reverse-proxy prefix or port if needed. **Test connection** reads the server’s model list. **Save settings** stores the configuration. A server without model discovery can still serve chat.
4. Choose a model in the panel, enter a custom model and endpoint in Settings, or leave the fields blank for the server default. Send a short message to verify a complete round trip.

For an existing unpacked installation, put the new `odysseus-extension` contents in the same directory used by the browser and click **Reload** on its extension card. This retains the installation identity and saved configuration. If the earlier release had access to all sites, saving Settings again grants the chosen server access. The old shared conversation ID and unattended-agent preference are discarded during an upgrade.

## Page context and request timing

For longer attached pages and comparison tabs, **Page context** offers **Relevant excerpts** and **Full captures**. Relevant excerpts ranks passages in the browser against the current question, keeps the original words in source order and marks omitted sections with `[…]`. Each source is evaluated separately. Short pages, broad requests, weak matches, and text you selected yourself use the entire capture. The attachment preview shows the text that will be sent. Full captures includes up to the original 20,000-character limit per page.

Open **Timing** below a reply to see connection checks, local context preparation, any session creation or uploads, and the time from the request to the first streamed text. It also shows the rest of the stream, time to first text since Send, and total turnaround. If a guide route responds without streamed text, its duration appears separately. Timings are measured in the browser and stay in the conversation. They do not split server queue, model processing or network time. An interrupted reply with visible text keeps partial timings.

In two synthetic three-tab comparisons, using relevant excerpts reduced the chat message from about 61 kB to 6–7 kB while keeping all three known facts in each case. A general overview sent the original captures. The measurement covers request size and evidence retained in the prompt. Inference time and answer quality depend on your server and model.

## Transport improvements

- Attachments upload two at a time using the existing per-file API. They appear in the prompt in their original order. When one request fails, a retry reuses any file already acknowledged for that session. A loopback benchmark with four 64 KiB files and a fixed 120 ms server delay per upload measured a median of 491 ms in 0.8.0 and 248 ms in 0.8.1 across seven runs per version.
- The model picker can reuse the server’s list for five minutes within the current browser session. Opening another panel or switching models during that period avoids fetching the list again. **Test connection** still checks the server live.
- The side panel appends new text as it arrives, then formats Markdown when the stream finishes. 

## Using the side panel

| Control | What it does |
| --- | --- |
| Chat | Streams answers, formats code and lists, and provides copy buttons. Enter sends and Shift+Enter adds a line. Stop or Escape interrupts the current request. |
| Page and Selection | Attach a text excerpt from the current tab. Expand the attachment to inspect its source and contents. The starter prompts and right-click menu also prepare editable drafts. |
| Screenshot and Files | Preview the captured image or inspect a file’s name and size. Sending uploads the files to the chat session. Four files including screenshots, 10 MiB per file and 16 MiB combined. Supported file formats depend on your server. |
| Page guide | Sending a goal shares the current page excerpt and eligible control labels. **Show on page** locates a proposed target. **Apply this step** approves one click, plain-text fill, choice, scroll or navigation. **Get next step** explicitly shares a fresh snapshot. |
| New chat | Clears this window’s local conversation, draft, attachments and pending suggestion. Existing server-side records follow your server’s retention settings. |
| Disconnect and forget token | Removes the saved token and persistent host grants. Re-enter a token to reconnect. |

A browser window can reopen its most recent conversation and text draft during the same browser session. The session transcript keeps up to 60 messages and roughly 160,000 characters. Changing the server, token or chat model starts a fresh conversation. Page-guide turns are labeled in the transcript and use a separate request context from ordinary chat.

## Conversation history and Markdown export

1. Open **History** in the side panel. Turn on **Save chats on this browser** to save the current conversation and future turns in this browser profile. Turning it off pauses saving and preserves earlier entries.
2. Search by title or message text. Open a saved chat to read it, change its title, export it as Markdown, or delete the local copy. **Export current chat** works even with saving disabled.
3. To continue a saved chat, choose **Resume chat** while using the same server connection and chat model. The original server session must still exist. Resume is available in one browser window at a time. Send or clear any staged draft and attachments before switching to a different saved chat.

Saved history keeps up to the most recent 60 messages and about 100,000 characters per conversation. It includes displayed messages and source names. Files, screenshot bytes, staged excerpts, and unsent drafts are excluded. Deleting a saved chat affects the local copy. Server records follow the server’s retention settings.

## Compare up to three tabs

1. On the first page, click **Compare tabs** in the composer.
2. Switch tabs and click **Compare tabs** again to add another excerpt. If access is needed, click the Odysseus toolbar icon on that tab and reopen the side panel if it closes. Comparison excerpts survive reopening the panel in the same browser window until they are removed, sent, or the browser session ends.
3. Expand the sources to review the text and URLs. After the second tab, an empty composer is filled with an editable prompt. Ask your own question or send the suggested prompt. The server receives the three numbered sources with your message through the existing chat route.

Re-capturing the same tab updates its excerpt. Comparison uses the same access limits and text filters as the **Page** button. All other staged attachments and pending action approvals live in the open panel.

## What changed after the 0.7.2 review

| Finding in the uploaded source | Change in 0.8.0 |
| --- | --- |
| The optional updater retained a writable directory handle and installed code supplied by the server without verifying a package signature. | Settings can display the version advertised by the server. Updating the executable files requires installing a trusted package. The upgrade discards the old directory handle. |
| The agent could fall back to an input’s current value for its label. Page captures also relied on an unfiltered text dump. | Text extraction skips native form fields, editable regions and hidden subtrees. Guide snapshots use labels and eligible choice lists. Page and link metadata omit query strings and fragments. Screenshots contain the visible pixels, including any sensitive information on screen. |
| The agent requested persistent access to every HTTP and HTTPS site. An unattended task could run for up to 200 iterations. A pending approval could also be left unresolved by Stop. | Page guide uses the user-invoked tab, one proposed action per request and a fresh approval for each action. Approval is bound to the tab, document, location and current target. Sensitive fields and built-in form submission controls are excluded. |
| Stop did not cover session creation or document upload. A global session ID could be reused across windows. The stream parser dropped some valid line endings and final events. | Cancellation covers session creation, upload and streamed replies. Sessions are scoped to the browser window and configuration. The stream reader handles split Unicode, SSE line endings, final events and interrupted replies. |

## Server interface

All routes are relative to the configured base address. API requests use `Authorization: Bearer <token>`. The transport omits browser cookies and refuses redirects. Use the final HTTPS address of the application. HTTP on loopback works directly. Other HTTP addresses require an explicit opt-in for that origin because the token and conversation travel unencrypted.

| Method and route | Contract |
| --- | --- |
| `GET /api/models` | Reads `items[]` with `id` or `endpoint_id`, `models[]` and optional `models_display[]`. Optional for chat. |
| `POST /api/session` | Multipart `name`, optional `endpoint_id` and `model`. Returns `id`. |
| `POST /api/upload` | Multipart `files` and `session_id`. Returns `files[].id`. Required when sending file or screenshot attachments. |
| `POST /api/chat_stream` | Multipart `session`, `message` and optional JSON-encoded `attachments`. Accepts SSE text deltas and authoritative `final_response` events. Finish a delta-only stream with `[DONE]`. |
| `POST /agent/step` | Optional JSON route with `messages` and `tools`. Streams text or `tool_calls`. This native route chooses its model on the server. HTTP 404, 405 or 501 switches the guide to a separate chat session with the selected chat model. |
| `GET /agent/version` | Optional, requested by **Check for an update**. Reads only the `version` from the response. |

The token is saved in extension-local storage restricted to trusted extension contexts. The client adds no analytics, CDN assets or third-party model endpoint. Your server controls any onward model calls and retention. A completed browser action or an upload already received by the server can survive client cancellation.

## Verification and browser behavior

From the parent folder containing `verification` and `odysseus-extension`, run the regression suite with Node.js 24 or later.

```sh
node --test
```

The tests exercise an actual loopback HTTP fixture for multipart requests, streaming, error handling and cancellation. Simulated Chrome and DOM interfaces exercise panel events, draft recovery, attachment handling, privacy filters and per-action approval. A full interactive Chrome or Edge run and the private production server were unavailable during this review.

Page tools operate on the top-level HTTP or HTTPS document. If access expires after navigating to another site, invoke the toolbar icon on the new page. Browser settings pages and embedded frames have different access rules. A browser screenshot may include embedded content. For a quick deployment check, open an ordinary article, attach a passage, send a question, reopen the panel, and review one Page guide suggestion.

Chrome documents temporary tab grants and browser-session storage. [Temporary tab access](https://developer.chrome.com/docs/extensions/develop/concepts/activeTab) · [Extension storage](https://developer.chrome.com/docs/extensions/reference/api/storage)
