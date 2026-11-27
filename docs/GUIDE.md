# Usage guide

**English** · [Português](GUIDE.pt.md)

How to use the KIT once it is installed ([INSTALL](INSTALL.md) or [ORACLE](ORACLE.md)). Everything is optional: hide or reorder tabs in *Settings → Appearance*.

## 1. First steps

1. Open Odysseus and look for the tool tabs (Translation, Finance, Gym, Glucose, Cycle, Study, News, Flights, …).
2. Admins: run the **Setup assistant** and paste only the keys for the tools you want. Every step has **Test** and **Skip**.
3. Each person who logs in gets **separate data**. Nothing is shared between accounts.
4. Install the [Android app](APK.md) and the [browser extension](EXTENSION.md) if you want them.

## 2. Everyday tools

| Tool | Do this |
|---|---|
| **Translation** | Pick the languages, type or speak, or photograph text. *Conversation mode* alternates between two people. Use *reply suggestions* for guest messages. |
| **Compose** | Describe the message, get a draft, and use the button to open it in your email or WhatsApp app. |
| **Prompts** | Describe in your language what you want; copy the English prompt. A warning appears when details are missing. |
| **News** | Choose sources and topics, mute words, enable *only critical*, read the neutral daily summary. |
| **Study** | Add an assignment, break it into steps, add sources (APA is generated), summarize a link or PDF, export references to Word. Deadlines create reminders. |
| **Emails / Invoices** | Connect an account with an app password. In *Bills*, confirm or ignore each detected invoice; confirming creates a debt. Mark an invoice as monthly for recurring reminders. |
| **Flights** | Add a flight number and date. You get a countdown, status and, with an AirLabs key, delay and gate alerts. |
| **Finance** | Log expenses and income, scan a receipt, set goals and debts with due-day alerts. |
| **Gym / Training+** | Follow the plan, log sets with effort, use the rest timer, track weight and photos. Personal records and progression suggestions are automatic. |
| **Glucose** | Connect LibreLinkUp for the chart and history, or log manually. *Analysis* shows time in range, GMI and daily profile and can be printed for your doctor. The insulin calculator ships **disabled**. |
| **Cycle** | Log period, flow, symptoms and mood. Predictions, the phase card, **Pingo** the penguin guide and an optional PIN are included. |
| **Focus** | One task at a time with timers and small steps. |
| **Dreams** | Write or dictate a dream, then ask for an interpretation. |
| **Free games** | See what is free now. Turn on alerts and **choose the stores** (Epic, Steam, GOG, itch.io, Prime) you care about. |
| **Optimise media** | Shrink videos (ffmpeg, H.264/HEVC/AV1) and images (WebP/JPEG), and optionally upscale images with AI (Real-ESRGAN). Jobs run one at a time in a queue. AI upscaling is optional: install with `install.sh --media-ai` or `tools/media-tools/install_ai.sh --ai` (about 1 GB, slow on CPU). |

## 3. Reminders and quiet hours

Scheduled jobs create Odysseus reminders (instalments, debts, deadlines, flights, cycle, workouts, free games, invoices).

- Open **Focus** or **Cycle** and use the 🌙 **Quiet hours** box: set *from* and *to* and tick *Enable*.
- During quiet hours, non-urgent reminders wait until the quiet period ends. **Flight alerts and the pill reminder are never delayed.**
- Quiet hours are per account and off by default.

## 4. Search everything

Use the 🔎 box at the top right of any tool page, or open `/finance/search?q=...`. It searches only **your own** data (Focus, Dreams, Study, Bills, Finance and, for the admin, the Idea Box) and highlights the matches.

## 5. Private Browser (optional)

A real Chromium that the assistant can drive, with screenshots. Your logins stay in a local profile on your server.

```bash
cd tools/pbrowse
npm install && npx playwright install chromium
bash run.sh &                       # listens on 127.0.0.1:8794 only
python3 pb open https://example.com
python3 pb click "More information"
python3 pb text                     # page text
python3 pb extract                  # product / price table
python3 pb close
```

- `pb --profile NAME ...` keeps separate logins per profile. Purchases and form submissions are blocked unless you add `--confirm`: only do that when you meant it.
- Optional environment: `PB_LOCALE`, `PB_TZ`, `SEARXNG_URL` (for `pb search`; otherwise DuckDuckGo opens in the browser).
- **Live view:** the admin can open `/finance/pblive` to watch the browser and take control: click on the image, type, scroll, go back or open a URL.

## 6. Browser extension and Android app

- [Extension guide](EXTENSION.md): side-panel chat, page attachments, tab comparison, Page guide and Agent mode.
- [Android app](APK.md): widgets, reminders with actions, translator, quick voice task.

## 7. Good habits

- Run `python3 scripts/scan.py` before publishing any fork: it looks for keys and personal data.
- Keep API keys only in `~/.config/odysseus-kit/*.env` (never in the repository).
- Medical tools are informational. Read the [health disclaimer](../README.md#health-disclaimer).

## Status tab

**Tools → Status** opens a floating window (drag it by the title, resize it from the corner; it does not block the chat). It shows live usage of your AI models (Claude, ChatGPT, Groq, DeepL, AirLabs) and, for the owner account only, server disk/RAM/swap, running containers and recent check logs. It refreshes every 30 s. Hide it under Appearance like any other tool.
