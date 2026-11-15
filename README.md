# Odysseus KIT

**English** · [Português](README.pt.md)

Extras for Odysseus (your self-hosted AI chat): in-chat tools, an Android app, and a step-by-step setup assistant. Everything is optional: each person enables only what they want, and can disable the rest in **Appearance**.

> Status: **pre-release**. It was extracted from a personal installation and has not yet been tested by third parties. Open an issue if something fails.

## What's included

| Tool | What it does | Requires |
|---|---|---|
| **Translation** | pt/en/es/fr/de/…, voice, photo translation, response suggestions for guests | DeepL and/or Groq |
| **Finance** | transactions, debts with alerts, goals, photo receipts, monthly expenses | Groq (receipts) |
| **Gym + Training+** | plan, sets, rest, weight, progress photos, AI technique analysis, medical reports | Groq/Gemini |
| **Study** | assignments, steps, sources with APA citation, link/PDF summary, notes by subject | Groq |
| **News** | feed by sources and topics for each person + daily summary | Groq |
| **Compose** | email/WhatsApp draft and button to choose the sending app | Groq |
| **Prompts** | describe what you want in your language and get a ready-to-paste English prompt (chat, image, code, video, music, agent), with a warning when important details are missing | Groq (Claude Haiku as fallback) |
| **Usage bar** | slim bar above your name showing Claude session/weekly limits, Groq, DeepL and AirLabs usage | none (reads each service's own usage data) |
| **Choice buttons** | when the assistant needs a decision it ends the reply with `[[opcoes: Yes \| No]]` and the chat shows tap-able buttons | none |
| **Flights** | saves flights, opens in Flightradar24, delays with AirLabs key | AirLabs (optional) |
| **Glucose** | LibreLinkUp chart and history. The insulin calculator comes **disabled** | LibreLinkUp |
| **Canva** | create designs and export PNG | Canva developer account |
| **Idea Box** | users submit ideas/bugs, AI organizes them into tasks | Groq |
| **Emails** | connect IMAP/SMTP accounts (Gmail, Outlook, Yahoo, iCloud, custom) with the right servers pre-filled and a connection test | app passwords from your provider |
| **Setup** | the step-by-step wizard: keys, services, enable/skip each tool (admins only, opens on first use) | — |
| **Tool tabs** | reorder and hide the tabs under *Settings → Appearance*; the order is saved on the server and shared by browser and app | — |
| **Language** | English / Português switch (Appearance and the app's first screen) | — |
| **Ryoku Theme** | extra theme for Odysseus (GPL-3.0 art from the ryoku.dev project) | — |
| **Android App** | widgets, reminders with actions, translator, calendar, fingerprint lock | Android Studio/SDK |

## Quick start

```bash
git clone <this repository> ~/odysseus-kit && cd ~/odysseus-kit
python3 -I setup/wizard.py        # opens http://127.0.0.1:8790 and guides you step by step
bash scripts/start.sh             # starts the tools
```

The assistant explains each service, tells you where to get the keys, has a **Test** button, and lets you **skip** what you don't want. What you skip remains disabled but is not lost: you can come back and enable it with the same instructions.

Full guide: [docs/INSTALL.md](docs/INSTALL.md). Android app: [docs/APK.md](docs/APK.md). Languages (English/Portuguese): [docs/I18N.md](docs/I18N.md).

Inside Odysseus there is also **Tools → Setup**, the same assistant, which opens automatically the first time; and the Android app starts with a language and server screen.

## Download the Android app

You don't need to compile: the signed APK is in **[Releases](../../releases/latest)** (`Odysseus-KIT-<version>.apk`).

1. Download it to your phone and install it (enable "install from unknown sources" when Android asks).
2. When opening, choose the language and enter your Odysseus address; click **Test connection**.
3. Log in to Odysseus and follow the assistant in **Tools → Setup**.

Always verify the certificate fingerprint before installing. The release indicates the `SHA-256` of the file and the signing certificate, and you can verify them with `sha256sum` and `apksigner verify --print-certs`. The APK requires your own Odysseus server: the app only shows what your server serves it.

## Security and privacy

- Keys are stored only in `~/.config/odysseus-kit/*.env` (mode 600), never in the repository.
- Tools listen only on `127.0.0.1` and should be published behind your proxy (Tailscale Serve, Caddy, nginx) **with the same authentication as Odysseus**.
- Features that use AI send text, audio, or photos to the provider you choose (Groq, Gemini, DeepL…). Read their policies.
- `python3 scripts/scan.py` searches for secrets and personal data before you publish changes.

## Health disclaimer

Glucose, Gym, and medical reports are **support tools**, not medical advice. The insulin calculator does not include values: it only works if you set your doctor's values, and it is at your own risk. See [docs/GLUCOSE.md](docs/GLUCOSE.md).

## License

[AGPL-3.0](LICENSE), the same as Odysseus, of which this project is a derivative work. If you modify and provide the service over a network, you must share the code. Attributions in [NOTICE.md](NOTICE.md).
