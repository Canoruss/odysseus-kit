# Installation

Requirements: Linux with Python 3.11+, Odysseus running in Docker, and (for use outside your home network) a way to publish it over HTTPS, for example [Tailscale](https://tailscale.com). Optional: `poppler-utils` (`pdftotext`) to read PDFs in Study.

## Quick install on a fresh server (Ubuntu/Debian, e.g. Oracle Cloud Always Free)

```bash
git clone https://github.com/Canoruss/odysseus-kit && bash odysseus-kit/install/install.sh
```

One command installs Docker, Odysseus (official image, pinned), HTTPS (Caddy), and the KIT tools and wires everything together. Everything runs on your own machine and nothing is sent anywhere. At the end it prints the address and the generated admin password. Options: `--domain`, `--admin-user`, `--timezone` (see `--help`). Remove with `install/uninstall.sh` (`--purge` also deletes the data). On Oracle Cloud you must also open ports 80 and 443 in the VCN Security List. Step-by-step guide (Portuguese): [ORACLE.pt.md](ORACLE.pt.md). The manual steps below are for existing setups.

## 1. Configuration

There are two ways: the local browser wizard (below) or, once the installation is up and running, **inside Odysseus**: Tools → **Setup** (administrators only; opens automatically on first use). The wizard also runs behind the Hub at `/finance/setup/`, using the same authentication as Odysseus.

```bash
python3 -I setup/wizard.py
```

It opens `http://127.0.0.1:8790` and walks you through the steps. It creates:
- `~/.config/odysseus-kit/config.json` (active features, names, timezone);
- `~/.config/odysseus-kit/<name>.env` with the keys (mode 600);
- `~/.config/odysseus-kit/kit-config.js` (configuration for the front-end).

You can run the wizard again at any time. Saved values appear masked, and an empty field means "keep".

## 2. Start the tools

```bash
bash scripts/start.sh
```

| Service | Port (127.0.0.1) | Suggested public path |
|---|---|---|
| Hub (Finance, Gym, Study, News, Compose, Flights, Glucose, Cash) | 8792 | `/finance` |
| Translation | 8791 | `/translate` |
| Canva | 8793 | `/canva` |
| Configuration wizard | 8790 | `/finance/setup/` (via Hub; administrator only) |

Change the ports using `KIT_HUB_PORT`, `KIT_TRANSLATE_PORT`, and `KIT_CANVA_PORT`. To start on boot, use `systemd --user` or `cron` (`@reboot`).

## 3. Publish behind your proxy

With Tailscale:
```bash
sudo tailscale serve --set-path /finance   http://127.0.0.1:8792
sudo tailscale serve --set-path /translate http://127.0.0.1:8791
sudo tailscale serve --set-path /canva     http://127.0.0.1:8793
```

**Important:** the tools identify the user via the Odysseus session cookie, so they must be on the same domain as Odysseus. Do not expose them directly to the Internet.

## 4. Connect to Odysseus

The front-end is a script that is added to Odysseus's `index.html`:
1. Copy `web/ody-extras.js` to the static files folder you mount in the container (for example `/app/static/js/ody-extras.js`) and `~/.config/odysseus-kit/kit-config.js` to the same location.
2. In `index.html`, before the modules, add:
   ```html
   <script src="/static/js/kit-config.js"></script>
   <script src="/static/js/ody-extras.js"></script>
   ```
3. Restart the Odysseus container.

The tools appear in the **Tools** bar, and you can hide them in **Appearance**.

**Ryoku theme (optional):** copy `web/ryoku/` to `/app/static/ryoku/` and include `ryoku.css`. The art comes from ryoku.dev (GPL-3.0, "dithered from AI-generated marble").

## 5. Scheduled tasks (optional)

In `tools/jobs/`: installment and expense alerts, workout reminders, daily ClickUp list, and gallery synchronization. They require `~/.config/odysseus-kit/agent.env` with `ODYSSEUS_URL` and `ODYSSEUS_API_TOKEN` (agent token created in Odysseus settings). Example `cron`:
```
40 9 * * *  python3 -I ~/odysseus-kit/tools/jobs/installments.py
```


## Check that it works

After `bash scripts/start.sh`, each port should answer (`curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8792/login`). Expected on a fresh install, before the wizard:
- Hub, Translation and Wizard answer `200`; Canva answers `403` (it is not configured yet).
- The logs in `~/.local/share/odysseus-kit/logs/` show warnings such as "FINANCE_PASSWORD not set" and "Canva not configured". Run the wizard to clear them.

This flow was tested on a clean Ubuntu 24.04 container (Python 3.12, only `git`, `python3` and `curl` installed).

## Troubleshooting

- **Blank page when opening a tool:** the service is not running or the proxy is not pointing to the correct port (`ss -ltn | grep 879`).
- **403 everywhere:** the tool did not recognize the user. Check `owner` in the wizard (it must match the name in Odysseus).
- **Key rejected:** use the Test button in the wizard.
- **Scan for secrets before contributing:** `python3 scripts/scan.py`.
