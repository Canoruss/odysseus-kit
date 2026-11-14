#!/usr/bin/env python3
"""Importa as imagens novas da pasta InstantUpload do Nextcloud para a galeria do Odysseus (so imagens, sem duplicados).
Corre como root (le os ficheiros do Nextcloud) e usa o login da conta owner."""
import sys as _s, os as _o
_s.path.insert(0, _o.path.join(_o.path.dirname(_o.path.abspath(__file__)), ".."))
from kitconfig import *
from kitconfig import secret_file
import os, sys, json, time, uuid, urllib.request, urllib.error, http.cookiejar
SRC = get("gallery_src", "")   # pasta com as fotos (ex.: dados do Nextcloud .../files/InstantUpload)
if not SRC: sys.exit("Define gallery_src em ~/.config/odysseus-kit/config.json (assistente de configuracao).")
HOME = os.path.expanduser("~")
STATE = os.path.join(JOBS_STATE, "gallery-state.json")
H = get("odysseus_url", "http://127.0.0.1:7860")
ALBUM = "Nextcloud InstantUpload"
EXT = {"jpg", "jpeg", "png", "webp", "gif"}
env = dict(l.strip().split("=", 1) for l in open(secret_file("owner")) if "=" in l)
cj = http.cookiejar.CookieJar(); op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
def call(path, data=None, headers=None, timeout=120):
    r = urllib.request.Request(H + path, data, headers or {})
    return json.load(op.open(r, timeout=timeout))
call("/api/auth/login", json.dumps({"username": env["ODY_USER"], "password": env["ODY_PASSWORD"]}).encode(), {"Content-Type": "application/json"})
al = call("/api/gallery/albums")
albums = al.get("albums", al) if isinstance(al, dict) else al
aid = next((a["id"] for a in albums if a.get("name") == ALBUM), None)
if not aid:
    aid = call("/api/gallery/albums", json.dumps({"name": ALBUM}).encode(), {"Content-Type": "application/json"})["id"]
try: st = json.load(open(STATE))
except Exception: st = {}
files = []
for root, _, fs in os.walk(SRC):
    for f in fs:
        if f.rsplit(".", 1)[-1].lower() in EXT:
            p = os.path.join(root, f); s = os.stat(p); files.append((s.st_mtime, p, s.st_size))
files.sort(reverse=True)
limit = int(sys.argv[1]) if len(sys.argv) > 1 else 10**9
n_ok = n_dup = n_skip = n_err = 0; t0 = time.time()
def save():
    tmp = STATE + ".tmp"; json.dump(st, open(tmp, "w")); os.replace(tmp, STATE); os.chown(STATE, 1000, 1000)
done_now = 0
for mt, p, sz in files:
    key = f"{p}|{int(mt)}|{sz}"
    if key in st: n_skip += 1; continue
    if done_now >= limit: break
    done_now += 1
    try:
        body = open(p, "rb").read()
        b = uuid.uuid4().hex
        data = (f'--{b}\r\nContent-Disposition: form-data; name="album_id"\r\n\r\n{aid}\r\n'
                f'--{b}\r\nContent-Disposition: form-data; name="file"; filename="{os.path.basename(p)}"\r\nContent-Type: application/octet-stream\r\n\r\n').encode() + body + f'\r\n--{b}--\r\n'.encode()
        r = call("/api/gallery/upload", data, {"Content-Type": "multipart/form-data; boundary=" + b}, timeout=300)
        if r.get("duplicate"): n_dup += 1
        else: n_ok += 1
        st[key] = 1
    except urllib.error.HTTPError as e:
        if e.code in (400, 413): st[key] = 0; n_err += 1   # tipo/tamanho recusado: nao repetir
        else: n_err += 1
    except Exception:
        n_err += 1
    if done_now % 100 == 0:
        save(); print(f"{done_now} processados: {n_ok} novos, {n_dup} duplicados, {n_err} erros, {int(time.time()-t0)} s", flush=True)
save()
print(f"FIM: {n_ok} novos, {n_dup} duplicados, {n_skip} ja feitos antes, {n_err} erros (de {len(files)} imagens)", flush=True)
