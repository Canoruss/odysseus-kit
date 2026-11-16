# Free server on Oracle Cloud (no server experience needed)

This guide takes you from zero to a working Odysseus with the KIT, **in your own Oracle Cloud account**, with a single command. No one else's server is involved: your data stays on your machine and the KIT author cannot see it.

Time: about 30 to 40 minutes, most of it waiting for downloads.

> Oracle's screens change often. The names below are the usual ones; if one is different, look for the equivalent.

## What you need
- An email address and a phone (to verify the account).
- A bank card. Oracle uses it only to confirm your identity; on the "Always Free" plan it does not charge you as long as you stay within the free limits.
- Your own AI key (Claude, Groq, Gemini, etc.), which you add at the end.

## 1. Create the account
1. Open <https://www.oracle.com/cloud/free/> and choose **Start for free**.
2. Fill in your details and choose a **region** (the "home region" cannot be changed later; pick one close to you).
3. Confirm the card and wait for the email saying the account is ready.

## 2. Create the machine (VM)
1. In the console: **Compute → Instances → Create instance**.
2. **Image:** Canonical **Ubuntu 24.04**.
3. **Shape:** change it to **Ampere (ARM) → VM.Standard.A1.Flex**, with **2 OCPUs and 12 GB of RAM** (within the free allowance). Avoid the "Micro" machine with 1 GB: it is too small for Odysseus.
   - If it says *Out of capacity*, try again later or in another availability domain. This happens often.
4. **Networking:** leave "Assign a public IPv4 address" enabled.
5. **SSH keys:** choose **Generate a key pair** and **download the private key** (keep it safe; without it you cannot log in to the machine).
6. **Boot volume:** 50 GB is enough.
7. **Create**. When it turns green (*Running*), copy the **Public IP address**.

## 3. Open ports 80 and 443
The script cannot do this for you, because it is a rule of Oracle's network, not of the machine.
1. On the instance page, click the **Subnet** (under *Primary VNIC*) and then the **Security List** (the "Default" one).
2. **Add Ingress Rules**: *Source CIDR* `0.0.0.0/0`, *IP Protocol* TCP, *Destination Port Range* `80,443`.
3. Save.

## 4. Log in to the machine
On Windows (PowerShell), Mac or Linux, using the key you downloaded:
```bash
ssh -i path/to/key.key ubuntu@PUBLIC_IP
```
If SSH complains about the key's permissions, on Mac/Linux run `chmod 600 path/to/key.key`.

## 5. Run the installer
Inside the machine:
```bash
git clone https://github.com/Canoruss/odysseus-kit
bash odysseus-kit/install/install.sh --admin-user your_name --timezone Europe/Lisbon
```
Replace `your_name` with the administrator name you want (lowercase letters, digits, `-` or `_`) and `Europe/Lisbon` with your time zone.

The script takes about 10 to 20 minutes (it downloads about 3 GB). At the end it shows:
- the **address** (for example `https://12-34-56-78.sslip.io`);
- the **user name** and a randomly generated **password**. Save it and change it after logging in.

If you have your own domain, use `--domain your.domain` (it must point to the machine's IP).

## 6. First steps in Odysseus
1. Open the address in your browser and log in with the user name and password.
2. Add your AI key: **Settings → Models**. The key is yours and stays on this machine only.
3. Open **Tools → Setup** to turn KIT features on or off and fill in the optional keys.
4. In the Odysseus Android app, set the server address to the one from step 5.

## Maintenance
- **Update the KIT:** `cd ~/odysseus-kit && git pull && bash install/install.sh` (keeps your data and password).
- **Check the status:** `cd ~/odysseus-server && sudo docker compose ps`.
- **See Odysseus errors:** `cd ~/odysseus-server && sudo docker compose logs --tail 100 odysseus`.
- **Backup:** copy the `~/odysseus-server/data` folder and `~/.config/odysseus-kit`.
- **Remove everything:** `bash ~/odysseus-kit/install/uninstall.sh --purge` (deletes the data; without `--purge` the data is kept).

## Common problems
| Symptom | Likely cause |
|---|---|
| The site does not open from outside | Step 3 is missing (ingress rules for 80 and 443). |
| Certificate error | Let's Encrypt needs ports 80 and 443 open; wait 1 to 2 minutes and reload. |
| "Out of capacity" when creating the VM | No free ARM machines in that region right now; try later. |
| The script says "Not enough RAM" | You used the Micro machine; create an Ampere A1 with at least 2 GB. |
| The KIT tabs do not appear | Reload the page (Ctrl+F5) or close and reopen the app. |

## Privacy and security
- Everything runs in your Oracle account. The installer sends no data to anyone and has no telemetry.
- The address is public on the internet, so use a strong password (the generated one is) and keep the machine updated (`sudo apt update && sudo apt upgrade`).
- The KIT code is public: you can read `install/install.sh` before running it.
