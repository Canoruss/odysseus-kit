"""Otimizar média (aba no Odysseus): ampliar imagem com IA, otimizar vídeo e otimizar imagem.
Motor: tools/media-tools/worker.py (Real-ESRGAN para ampliar, ffmpeg para vídeo, Pillow para imagem).
Cada pedido vira um trabalho em media-jobs/<conta>/<id>/ (job.json + entrada + saída + log). Dados por conta.
Os trabalhos correm em fila (flock), um de cada vez, para não sobrecarregar o servidor."""
import os, re, json, uuid, time, html, shutil, subprocess, urllib.parse, glob
import sys as _s
_s.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from kitconfig import HUB

HERE = HUB
MT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "media-tools")      # worker.py
DATA_DIR = os.path.expanduser("~/.local/share/odysseus-kit/media-tools")                # venv + models
PY = os.path.join(DATA_DIR, "venv", "bin", "python")
if not os.path.exists(PY): PY = "/usr/bin/python3"
WORKER = os.path.join(MT, "worker.py")
JOBS = os.path.join(DATA_DIR, "jobs")
HAS_AI = bool(glob.glob(os.path.join(DATA_DIR, "venv", "lib", "python*", "site-packages", "torch")))
LOCK = "/tmp/mediatools.lock"
BASE_PATH = "/mediatools"
MAX_BYTES = {"upscale": 400_000_000, "image": 400_000_000, "video": 3_000_000_000}
CHUNK = 1 << 20
ID_RE = re.compile(r"^[0-9a-f]{32}$")

# Parametros aceites (lista branca): nome -> (valores aceites ou tipo, predefinido)
SPEC = {
    "upscale": {
        "model": ({"photo", "fast"}, "photo"),
        "scale": ({"2", "4"}, "2"),
        "strength": ("int", 0, 100, 75),
        "grain": ("float", 0.0, 6.0, 1.5),
        "fmt": ({"png", "jpg"}, "png"),
    },
    "video": {
        "codec": ({"h264", "hevc", "av1"}, "h264"),
        "quality": ({"alta", "equilibrada", "pequena"}, "equilibrada"),
        "height": ({"original", "2160", "1440", "1080", "720", "480"}, "original"),
        "audio": ({"copy", "aac"}, "copy"),
    },
    "image": {
        "format": ({"webp", "jpg", "png"}, "webp"),
        "quality": ({"alta", "equilibrada", "pequena"}, "equilibrada"),
        "max_side": ({"0", "3840", "2560", "1920", "1280", "1080"}, "0"),
        "keep_meta": ({"0", "1"}, "0"),
    },
}


def T(lang, pt, en):
    return en if lang == "en" else pt


def _user_dir(u):
    return os.path.join(JOBS, re.sub(r"[^a-z0-9_-]", "", str(u).lower()) or "anon")


def _job_dir(u, jid):
    if not ID_RE.match(jid or ""):
        return None
    d = os.path.join(_user_dir(u), jid)
    return d if os.path.isdir(d) else None


def _read_job(d):
    try:
        with open(os.path.join(d, "job.json")) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _params(kind, q):
    """Valida os parametros do pedido com a lista branca de SPEC; valores invalidos caem no predefinido."""
    out = {}
    for k, rule in SPEC[kind].items():
        raw = (q.get(k) or [""])[0][:12]
        if isinstance(rule[0], set):
            out[k] = raw if raw in rule[0] else rule[1]
        elif rule[0] == "int":
            try: out[k] = min(rule[2], max(rule[1], int(float(raw))))
            except ValueError: out[k] = rule[3]
        else:  # float
            try: out[k] = min(rule[2], max(rule[1], float(raw.replace(",", "."))))
            except ValueError: out[k] = rule[3]
    if kind == "upscale":
        out["scale"] = int(out["scale"])
    if kind == "image":
        out["max_side"] = int(out["max_side"])
    return out


def _ext_for(kind, params):
    if kind == "upscale": return params["fmt"]
    if kind == "video": return "mp4"
    return params["format"]


def _safe_ext(name):
    ext = os.path.splitext(name or "")[1].lower()
    return ext if re.fullmatch(r"\.[a-z0-9]{1,6}", ext or "") else ".bin"


def _stem(name):
    s = re.sub(r"[^\w.-]+", "_", os.path.splitext(name or "media")[0]).strip("._")
    return (s or "media")[:80]


def _spawn(jobdir):
    log = open(os.path.join(jobdir, "log.txt"), "ab")
    subprocess.Popen(["flock", LOCK, PY, WORKER, jobdir], stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                     start_new_session=True, close_fds=True, cwd=DATA_DIR if os.path.isdir(DATA_DIR) else None)


def _raw(h, code, ctype, body, headers=None):
    h.send_response(code)
    h.send_header("Content-Type", ctype)
    h.send_header("Content-Length", str(len(body)))
    h.send_header("Cache-Control", "no-store")
    h.send_header("X-Content-Type-Options", "nosniff")
    for k, v in (headers or {}).items(): h.send_header(k, v)
    h.end_headers()
    h.wfile.write(body)


def _json(h, code, obj):
    _raw(h, code, "application/json; charset=utf-8", json.dumps(obj, ensure_ascii=False).encode())


# ---------------------------------------------------------------- pedidos
def upload(h, u, q):
    """POST /mediatools/upload?kind=...&params — corpo = ficheiro bruto (stream para disco)."""
    kind = (q.get("kind") or [""])[0]
    if kind not in SPEC:
        return _json(h, 400, {"error": "tipo inválido"})
    if kind == "upscale" and not HAS_AI:
        return _json(h, 503, {"error": "ampliar com IA não está instalado (ver docs/GUIDE: install_ai.sh) / AI upscale is not installed"})
    try:
        n = int(h.headers.get("Content-Length", 0) or 0)
    except ValueError:
        n = 0
    if n <= 0:
        return _json(h, 400, {"error": "ficheiro vazio"})
    if n > MAX_BYTES[kind]:
        h.rfile.read(min(n, CHUNK))  # consome um pouco; o cliente ve a resposta
        return _json(h, 413, {"error": "ficheiro demasiado grande para este tipo"})
    name = urllib.parse.unquote((h.headers.get("X-Filename") or "media")[:200])
    params = _params(kind, q)
    jid = uuid.uuid4().hex
    d = os.path.join(_user_dir(u), jid)
    os.makedirs(d, exist_ok=True)
    inp = os.path.join(d, "in" + _safe_ext(name))
    out = os.path.join(d, "out." + _ext_for(kind, params))
    left = n
    try:
        with open(inp, "wb") as f:
            while left > 0:
                chunk = h.rfile.read(min(CHUNK, left))
                if not chunk: raise IOError("ligação interrompida")
                f.write(chunk); left -= len(chunk)
    except (OSError, IOError) as e:
        shutil.rmtree(d, ignore_errors=True)
        return _json(h, 400, {"error": "upload falhou: " + str(e)[:120]})
    job = {"id": jid, "kind": kind, "params": params, "input": inp, "output": out, "name": name[:200],
           "state": "queued", "progress": 0, "message": "Na fila", "created": time.time()}
    with open(os.path.join(d, "job.json.tmp"), "w") as f: json.dump(job, f, ensure_ascii=False)
    os.replace(os.path.join(d, "job.json.tmp"), os.path.join(d, "job.json"))
    _spawn(d)
    return _json(h, 200, {"ok": True, "id": jid})


def _public(job):
    keep = {"id", "kind", "name", "state", "progress", "message", "result", "output_size", "created", "params"}
    return {k: job.get(k) for k in keep if k in job}


def list_jobs(u):
    d = _user_dir(u)
    items = []
    if os.path.isdir(d):
        for jid in os.listdir(d):
            j = _read_job(os.path.join(d, jid))
            if j and ID_RE.match(jid): items.append(j)
    items.sort(key=lambda j: j.get("created", 0), reverse=True)
    return items[:25]


def list_html(u, lang):
    items = list_jobs(u)
    if not items:
        return '<p class="mt-muted">' + T(lang, "Ainda não há trabalhos.", "No jobs yet.") + "</p>"
    kinds = {"upscale": T(lang, "Ampliar", "Upscale"), "video": T(lang, "Vídeo", "Video"), "image": T(lang, "Imagem", "Image")}
    rows = []
    for j in items:
        st = j.get("state", "queued")
        label = {"queued": T(lang, "Na fila", "Queued"), "running": T(lang, "A processar", "Processing"),
                 "done": T(lang, "Pronto", "Done"), "error": T(lang, "Erro", "Error")}.get(st, st)
        pct = int(j.get("progress") or 0)
        res = j.get("result") or {}
        info = ""
        if res.get("width"): info = f'{res.get("width")}×{res.get("height")} px'
        if j.get("output_size"): info += f' · {j["output_size"] / 1048576:.1f} MB'
        jid = html.escape(j["id"])
        actions = ""
        if st == "done":
            actions += f'<a class="mt-btn" href="{BASE_PATH}/job/{jid}/file">{T(lang, "Descarregar", "Download")}</a>'
        actions += f' <button class="mt-del" data-id="{jid}">{T(lang, "Apagar", "Delete")}</button>'
        bar = f'<div class="mt-bar"><span style="width:{pct}%"></span></div>' if st in ("queued", "running") else ""
        msg = html.escape(str(j.get("message") or ""))
        rows.append(
            f'<div class="mt-job mt-{html.escape(st)}"><div class="mt-jt"><b>{html.escape(j.get("name") or "")}</b>'
            f' <span class="mt-tag">{kinds.get(j.get("kind"), "")}</span> <span class="mt-st">{label}</span></div>'
            f'{bar}<div class="mt-meta">{msg} {html.escape(info)}</div><div class="mt-act">{actions}</div></div>')
    return "".join(rows)


def job_json(h, u, jid):
    d = _job_dir(u, jid)
    j = _read_job(d) if d else None
    if not j: return _json(h, 404, {"error": "não existe"})
    return _json(h, 200, _public(j))


def job_file(h, u, jid):
    d = _job_dir(u, jid)
    j = _read_job(d) if d else None
    if not j or j.get("state") != "done" or not os.path.isfile(j.get("output", "")):
        return _json(h, 404, {"error": "sem ficheiro"})
    out = j["output"]
    ext = os.path.splitext(out)[1]
    fname = f'{_stem(j.get("name"))}-{j.get("kind")}{ext}'
    size = os.path.getsize(out)
    ctype = {".mp4": "video/mp4", ".png": "image/png", ".jpg": "image/jpeg", ".webp": "image/webp"}.get(ext, "application/octet-stream")
    h.send_response(200)
    h.send_header("Content-Type", ctype)
    h.send_header("Content-Length", str(size))
    h.send_header("Content-Disposition", "attachment; filename*=UTF-8''" + urllib.parse.quote(fname))
    h.send_header("Cache-Control", "no-store")
    h.end_headers()
    with open(out, "rb") as f:
        shutil.copyfileobj(f, h.wfile, CHUNK)


def job_delete(h, u, jid):
    d = _job_dir(u, jid)
    if not d: return _json(h, 404, {"error": "não existe"})
    j = _read_job(d) or {}
    if j.get("state") == "running":
        return _json(h, 409, {"error": "ainda a processar"})
    shutil.rmtree(d, ignore_errors=True)
    return _json(h, 200, {"ok": True})


# ---------------------------------------------------------------- pagina
CSS = """<style>
.mt-wrap{max-width:980px;margin:0 auto}
.mt-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px}
.mt-card{background:#262a31;border-radius:12px;padding:14px}
.mt-card h2{font-size:17px;margin:0 0 6px}
.mt-card p.mt-hint{font-size:12.5px;color:#aab;margin:0 0 10px;line-height:1.4}
.mt-card label{display:block;font-size:12.5px;color:#ccd;margin:8px 0 2px}
.mt-card select,.mt-card input[type=file]{width:100%;box-sizing:border-box}
.mt-card input[type=range]{width:100%;padding:0}
.mt-card button{margin-top:10px;width:100%}
.mt-muted{color:#889;font-size:13px}
.mt-jobs{margin-top:18px}
.mt-job{background:#262a31;border-radius:10px;padding:10px 12px;margin:8px 0}
.mt-jt{font-size:14px}.mt-tag{font-size:11px;background:#33405a;padding:2px 7px;border-radius:8px;margin-left:4px}
.mt-st{font-size:12px;color:#9ab;margin-left:6px}
.mt-done .mt-st{color:#70d080}.mt-error .mt-st{color:#f07070}
.mt-meta{font-size:12px;color:#99a;margin-top:4px}
.mt-act{margin-top:6px}
.mt-bar{height:6px;background:#333;border-radius:4px;overflow:hidden;margin-top:6px}
.mt-bar span{display:block;height:100%;background:#4a7bd0;transition:width .4s}
.mt-btn{display:inline-block;background:#4a7bd0;color:#fff;padding:6px 12px;border-radius:6px;text-decoration:none;font-size:13px;margin-right:6px}
.mt-del{background:#3a3f48;font-size:13px;padding:6px 12px;margin:0}
.mt-up{font-size:12px;color:#9ab;margin-top:6px;display:none}
</style>"""


def render(u, lang):
    t = lambda pt, en: T(lang, pt, en)
    sel = lambda name, opts: "".join(f'<option value="{v}"{" selected" if s else ""}>{html.escape(l)}</option>' for v, l, s in opts)
    card_up = lambda kind, title, hint, accept, fields: (
        f'<form class="mt-card" data-kind="{kind}"><h2>{title}</h2><p class="mt-hint">{hint}</p>'
        f'<label>{t("Ficheiro", "File")}</label><input type="file" name="file" accept="{accept}" required>'
        f'{fields}<button type="submit">{t("Enviar e processar", "Upload and process")}</button>'
        f'<div class="mt-up"></div></form>')
    up_fields = (
        f'<label>{t("Modelo", "Model")}</label><select name="model">'
        + sel("", [("photo", t("Fotos: mais detalhe", "Photos: more detail"), True),
                   ("fast", t("Rápido: pele mais suave", "Fast: softer skin"), False)]) + "</select>"
        + f'<label>{t("Ampliação", "Scale")}</label><select name="scale">'
        + sel("", [("2", "2×", True), ("4", "4×", False)]) + "</select>"
        + f'<label>{t("Intensidade da IA", "AI strength")}: <span id="mt-s-out">75</span>%</label>'
        + '<input type="range" name="strength" min="0" max="100" value="75" oninput="document.getElementById(\'mt-s-out\').textContent=this.value">'
        + f'<label>{t("Grão de filme", "Film grain")}: <span id="mt-g-out">1.5</span>%</label>'
        + '<input type="range" name="grain" min="0" max="6" step="0.5" value="1.5" oninput="document.getElementById(\'mt-g-out\').textContent=this.value">'
        + f'<label>{t("Formato de saída", "Output format")}</label><select name="fmt">'
        + sel("", [("png", t("PNG (sem perdas)", "PNG (lossless)"), True), ("jpg", "JPG (q95)", False)]) + "</select>")
    vid_fields = (
        f'<label>{t("Resolução máxima", "Max resolution")}</label><select name="height">'
        + sel("", [("original", t("Original (não aumenta)", "Original (never upscales)"), True), ("2160", "2160p (4K)", False),
                   ("1440", "1440p", False), ("1080", "1080p", False), ("720", "720p", False), ("480", "480p", False)]) + "</select>"
        f'<label>{t("Codec", "Codec")}</label><select name="codec">'
        + sel("", [("h264", t("H.264 (compatível com tudo)", "H.264 (works everywhere)"), True),
                   ("hevc", t("H.265 / HEVC (menor)", "H.265 / HEVC (smaller)"), False),
                   ("av1", t("AV1 (menor, mais lento)", "AV1 (smallest, slowest)"), False)]) + "</select>"
        f'<label>{t("Qualidade", "Quality")}</label><select name="quality">'
        + sel("", [("alta", t("Alta (quase sem perda)", "High (near lossless)"), False),
                   ("equilibrada", t("Equilibrada", "Balanced"), True),
                   ("pequena", t("Pequena (para enviar)", "Small (for sharing)"), False)]) + "</select>"
        f'<label>{t("Áudio", "Audio")}</label><select name="audio">'
        + sel("", [("copy", t("Copiar se possível", "Copy when possible"), True),
                   ("aac", t("Converter para AAC 192k", "Convert to AAC 192k"), False)]) + "</select>")
    img_fields = (
        f'<label>{t("Formato", "Format")}</label><select name="format">'
        + sel("", [("webp", t("WebP (o mais leve)", "WebP (smallest)"), True), ("jpg", "JPG", False),
                   ("png", t("PNG (sem perdas)", "PNG (lossless)"), False)]) + "</select>"
        f'<label>{t("Qualidade", "Quality")}</label><select name="quality">'
        + sel("", [("alta", t("Alta", "High"), False), ("equilibrada", t("Equilibrada", "Balanced"), True),
                   ("pequena", t("Pequena", "Small"), False)]) + "</select>"
        f'<label>{t("Lado maior máximo", "Longest side max")}</label><select name="max_side">'
        + sel("", [("0", t("Original", "Original"), True), ("3840", "3840 px", False), ("2560", "2560 px", False),
                   ("1920", "1920 px", False), ("1280", "1280 px", False), ("1080", "1080 px", False)]) + "</select>"
        f'<label>{t("Manter metadados (EXIF)", "Keep metadata (EXIF)")}</label><select name="keep_meta">'
        + sel("", [("0", t("Não", "No"), True), ("1", t("Sim", "Yes"), False)]) + "</select>")
    cards = (
        card_up("upscale", t("Ampliar imagem (IA)", "Upscale image (AI)"),
                t("Real-ESRGAN com mistura com a ampliação natural (Lanczos) para não ficar com aspeto de IA. "
                  "Entrada até 3000 px no lado maior. Em CPU demora de minutos a dezenas de minutos.",
                  "Real-ESRGAN blended with a natural Lanczos enlargement so it does not look AI-made. "
                  "Input up to 3000 px on the longest side. On CPU it takes minutes to tens of minutes."),
                "image/*", up_fields if HAS_AI else
                f'<p class="mt-muted">{t("A ampliação com IA não está instalada neste servidor. Corre tools/media-tools/install_ai.sh (cerca de 1 GB).", "AI upscaling is not installed on this server. Run tools/media-tools/install_ai.sh (about 1 GB).")}</p>')
        + card_up("video", t("Otimizar vídeo", "Optimise video"),
                  t("Redimensiona e comprime com ffmpeg. Nunca aumenta a resolução. Para guardar sem perda visível usa Alta; "
                    "Equilibrada é o ponto de partida; Pequena para enviar pelo telemóvel.",
                    "Resizes and compresses with ffmpeg. Never increases resolution. Use High to keep it visually lossless; "
                    "Balanced is the starting point; Small for phone sharing."),
                  "video/*", vid_fields)
        + card_up("image", t("Otimizar imagem", "Optimise image"),
                  t("Converte e comprime. WebP ou JPG com qualidade Equilibrada costumam ser indistinguíveis do original.",
                    "Converts and compresses. WebP or JPG at Balanced quality is usually indistinguishable from the original."),
                  "image/*", img_fields))
    body = f"""{CSS}<div class="mt-wrap"><h1 style="font-size:22px;margin:6px 0 12px">{t("Otimizar média", "Optimise media")}</h1>
<div class="mt-grid">{cards}</div>
<div class="mt-jobs"><h2 style="font-size:17px">{t("Trabalhos", "Jobs")}</h2><div id="mt-list">{list_html(u, lang)}</div></div></div>
<script>
(function(){{
  var BASE = location.pathname.replace(/\\/mediatools\\/?$/, '') + '/mediatools';
  var S = {{sending: {json.dumps(t("A enviar… ", "Uploading… "))}, err: {json.dumps(t("Erro: ", "Error: "))}, del: {json.dumps(t("Apagar este trabalho?", "Delete this job?"))}}};
  function refresh(){{ fetch(BASE + '/list', {{credentials:'same-origin'}}).then(function(r){{return r.text();}}).then(function(t){{ document.getElementById('mt-list').innerHTML = t; }}).catch(function(){{}}); }}
  document.querySelectorAll('form.mt-card').forEach(function(f){{
    f.addEventListener('submit', function(ev){{
      ev.preventDefault();
      var file = f.querySelector('input[type=file]').files[0]; if (!file) return;
      var qs = new URLSearchParams(); qs.set('kind', f.dataset.kind);
      Array.prototype.forEach.call(f.querySelectorAll('select,input[type=range]'), function(el){{ qs.set(el.name, el.value); }});
      var note = f.querySelector('.mt-up'); note.style.display = 'block'; note.textContent = S.sending + '0%';
      var x = new XMLHttpRequest(); x.open('POST', BASE + '/upload?' + qs.toString());
      x.setRequestHeader('X-Filename', encodeURIComponent(file.name));
      x.upload.onprogress = function(e){{ if (e.lengthComputable) note.textContent = S.sending + Math.round(e.loaded / e.total * 100) + '%'; }};
      x.onload = function(){{ var ok = x.status === 200; var j = {{}}; try {{ j = JSON.parse(x.responseText); }} catch(e) {{}}
        if (ok) {{ note.style.display = 'none'; f.querySelector('input[type=file]').value = ''; refresh(); }}
        else {{ note.textContent = S.err + (j.error || x.status); }} }};
      x.onerror = function(){{ note.textContent = S.err + 'network'; }};
      x.send(file);
    }});
  }});
  document.getElementById('mt-list').addEventListener('click', function(ev){{
    var b = ev.target.closest('.mt-del'); if (!b) return;
    if (!confirm(S.del)) return;
    fetch(BASE + '/job/' + b.dataset.id + '/del', {{method:'POST', credentials:'same-origin'}}).then(refresh);
  }});
  setInterval(function(){{ if (document.getElementById('mt-list').querySelector('.mt-queued,.mt-running')) refresh(); }}, 3000);
}})();
</script>"""
    return body


# ---------------------------------------------------------------- rotas
SKIN = None   # definido pelo server.py (ryoku_skin)


def route_get(h, u, lang, page_fn):   # page_fn = server.page(body, title)
    path = h.path.split("?")[0].rstrip("/")
    if path == BASE_PATH:   # texto ja gerado no idioma certo: sem passar pelo tradutor do servidor (JS incluido)
        _pg = page_fn(render(u, lang), T(lang, "Otimizar média", "Optimise media"))
        if "kittheme=ryoku" in (h.headers.get("Cookie") or "") and SKIN: _pg = SKIN(_pg)   # tema Ryoku (o _raw nao passa pelo h.send)
        return _raw(h, 200, "text/html; charset=utf-8", _pg.encode())
    if path == BASE_PATH + "/list":
        return _raw(h, 200, "text/html; charset=utf-8", list_html(u, lang).encode())
    m = re.fullmatch(BASE_PATH + r"/job/([0-9a-f]{32})(/file)?", path)
    if m:
        return job_file(h, u, m.group(1)) if m.group(2) else job_json(h, u, m.group(1))
    return _json(h, 404, {"error": "não existe"})


def route_post(h, u, lang):
    path = h.path.split("?")[0].rstrip("/")
    q = urllib_parse_qs(h.path)
    if path == BASE_PATH + "/upload":
        return upload(h, u, q)
    m = re.fullmatch(BASE_PATH + r"/job/([0-9a-f]{32})/del", path)
    if m:
        return job_delete(h, u, m.group(1))
    return _json(h, 404, {"error": "não existe"})


def urllib_parse_qs(p):
    return urllib.parse.parse_qs(urllib.parse.urlparse(p).query)
