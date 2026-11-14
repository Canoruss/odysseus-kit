#!/usr/bin/env python3
"""Share a file with an Odysseus app user (served on the tailnet, shown in the app as "download?").
  share.py <user> <file> [--name "Nome.docx"] [--note "texto"]   publish a file
  share.py <user> <file> --link-only                             only return the link (for a PC browser): the app is NOT notified
  share.py --purge [days]                                         delete files older than N days (default 7)
Files live in ~/partilha/<user>/ ; the app reads ~/partilha/<user>/index.json
URL: https://YOUR-SERVER.YOUR-TAILNET.ts.net/odysseus-app/files/<user>/<stored-file>
"""
import json, os, re, secrets, shutil, sys, time, hashlib, mimetypes
ROOT = os.path.expanduser("~/partilha")
DAYS = 7

def load(d):
    try: return json.load(open(os.path.join(d, "index.json")))
    except Exception: return []

def save(d, items):
    tmp = os.path.join(d, ".index.json.tmp")
    json.dump(items, open(tmp, "w"), ensure_ascii=False, indent=1)
    os.replace(tmp, os.path.join(d, "index.json"))

def purge(days=DAYS):
    cutoff = time.time() - days * 86400
    for u in os.listdir(ROOT):
        d = os.path.join(ROOT, u)
        if not os.path.isdir(d): continue
        keep = []
        for it in load(d):
            if it["ts"] < cutoff:
                try: os.remove(os.path.join(d, it["file"]))
                except FileNotFoundError: pass
            else: keep.append(it)
        save(d, keep)
        listed = {it["file"] for it in keep}
        for f in os.listdir(d):  # link-only files are not in the index: expire them by age
            fp = os.path.join(d, f)
            if f.startswith(".") or f.startswith("index.") or f in listed or not os.path.isfile(fp): continue
            if os.path.getmtime(fp) < cutoff: os.remove(fp)

def share(user, path, name=None, note="", link_only=False):
    user = re.sub(r"[^a-z0-9_-]", "", user.lower())
    if not user: sys.exit("invalid user")
    d = os.path.join(ROOT, user); os.makedirs(d, exist_ok=True); os.chmod(d, 0o755)
    open(os.path.join(d, "index.html"), "a").close()  # no directory listing
    name = re.sub(r'[\\/:*?"<>|]', "_", name or os.path.basename(path))
    stored = secrets.token_hex(6) + "-" + re.sub(r"[^A-Za-z0-9._-]", "_", name)
    dst = os.path.join(d, stored); shutil.copyfile(path, dst); os.chmod(dst, 0o644)
    if link_only:
        purge(); print(f"https://YOUR-SERVER.YOUR-TAILNET.ts.net/odysseus-app/files/{user}/{stored}"); return
    sha = hashlib.sha256(open(dst, "rb").read()).hexdigest()
    items = load(d)
    items.append({"id": stored, "name": name, "file": stored, "size": os.path.getsize(dst), "sha256": sha,
                  "mime": mimetypes.guess_type(name)[0] or "application/octet-stream", "note": note, "ts": time.time()})
    save(d, items); purge()
    print(f"https://YOUR-SERVER.YOUR-TAILNET.ts.net/odysseus-app/files/{user}/{stored}")

a = sys.argv[1:]
if a and a[0] == "--purge": purge(float(a[1]) if len(a) > 1 else DAYS)
elif len(a) >= 2:
    name = note = None
    if "--name" in a: name = a[a.index("--name") + 1]
    if "--note" in a: note = a[a.index("--note") + 1]
    share(a[0], a[1], name, note or "", "--link-only" in a)
else: sys.exit(__doc__)
