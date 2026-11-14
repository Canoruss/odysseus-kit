#!/usr/bin/env python3
"""Gera i18n/en.json (dicionario PT -> EN) a partir dos textos portugueses do codigo, usando o DeepL.
Uso:  python3 -I scripts/build_i18n.py            (usa DEEPL_API_KEY de ~/.config/odysseus-kit/deepl.env)
      python3 -I scripts/build_i18n.py --dry      (so lista o que vai traduzir)
O ficheiro gerado e revisavel e editavel: corrige a mao as traducoes que nao te agradarem; um novo run so acrescenta o que falta."""
import glob, html, json, os, re, sys, urllib.error, urllib.parse, urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "i18n", "en.json")
PT = re.compile(r"[àáâãçéêíóôõúÀÁÂÃÇÉÊÍÓÔÕÚ]|\b(não|para|com|que|uma|um|os|as|ou|tens|teu|tua|dia|ainda|nome|guardar|apagar|criar|abrir|escolhe|valor|data|hora|erro|ver|sem|mais|já)\b", re.I)
WORDY = re.compile(r"[A-Za-zÀ-ú]{3}")


def lits(text):
    for a, b in re.findall(r'"((?:[^"\\\n]|\\.)*)"|\'((?:[^\'\\\n]|\\.)*)\'', text):
        yield a or b


def html_segments(text):
    """Segmentos de texto entre etiquetas HTML (mantendo {expr} como marcadores {0},{1}...)."""
    out = set()
    for s in lits(text):
        for part in re.split(r"<[^>]+>|\\n", s):
            part = re.sub(r"\s+", " ", part).strip()
            if len(part) > 2 and PT.search(part) and WORDY.search(part) and not part.startswith(("http", "/", "#", ".", ")", "}")) and '\\"' not in part and "{\\" not in part:
                out.add(part)
    return out


def raw_html_segments(text):
    """Texto entre '>' e '<' no codigo-fonte bruto (apanha HTML em strings de varias linhas e f-strings)."""
    out = set()
    for m in re.finditer(r">([^<>]{3,}?)(?=<)", text):
        part = re.sub(r"\s+", " ", m.group(1)).strip()
        rest = re.sub(r"\{[^{}]*\}", "", part)
        if len(part) < 3 or not WORDY.search(rest) or re.search(r"[{}=\\]|\)\s*;|\(\)|=>|^[^\w\u00c0-\u00ff\u2190-\u21ff]|https?:|\.(py|js|json)\b", rest):
            continue
        if re.search(r"\b(def|return|import|self|None|True|False|lambda|elif)\b", rest):
            continue
        out.add(part)
    for m in re.finditer(r"""(?:placeholder|title|alt|aria-label)=\\?["']([^"'<>]{3,}?)\\?["']""", text):
        part = re.sub(r"\s+", " ", m.group(1)).strip()
        if WORDY.search(re.sub(r"\{[^{}]*\}", "", part)) and not re.search(r"[();=\\]|https?:", part):
            out.add(part)
    return out


def java_literals(text):
    out = set()
    for m in re.finditer(r'Tr\.t\("((?:[^"\\\n]|\\.)*)"\)', text):      # tudo o que ja esta marcado com Tr.t(...)
        v = m.group(1).replace('\\"', '"').replace("\\n", "\n")
        if len(v.strip()) > 2 and WORDY.search(v):
            out.add(v)
    for s in lits(text):
        s = s.replace('\\"', '"').replace("\\n", "\n")
        if len(s.strip()) > 2 and PT.search(s) and WORDY.search(s):
            out.add(s)
    return out


def xml_strings(text):
    out = set()
    for m in re.finditer(r'android:(?:text|label|contentDescription|title|description|hint)="([^"@][^"]*)"|<string[^>]*>([^<]+)</string>', text):
        s = html.unescape(m.group(1) or m.group(2))
        if PT.search(s) and WORDY.search(s):
            out.add(s)
    return out


def collect():
    web, java = set(), set()
    for pat in ("tools/hub/*.py", "tools/hub/*.html", "tools/translate/*.py", "tools/canva/*.py", "tools/jobs/*.py", "web/ody-extras.js", "setup/wizard.py"):
        for f in glob.glob(os.path.join(ROOT, pat)):
            txt = open(f, encoding="utf-8").read()
            web |= html_segments(txt) | raw_html_segments(txt)
    for f in glob.glob(os.path.join(ROOT, "android/app/src/main/java/**/*.java"), recursive=True):
        java |= java_literals(open(f, encoding="utf-8").read())
    for f in glob.glob(os.path.join(ROOT, "android/app/src/main/res/**/*.xml"), recursive=True) + [os.path.join(ROOT, "android/app/src/main/AndroidManifest.xml")]:
        java |= xml_strings(open(f, encoding="utf-8").read())
    return web, java


def protect(s):
    """{expr}/%s -> <x0/>, <x1/> para o DeepL nao mexer."""
    n = [0]
    ph = re.compile(r"\{[^{}]*\}|%(?:\d\$)?[sdf]|%\.\d[f]")
    parts, last, out = [], 0, ""
    for m in ph.finditer(s):
        out += html.escape(s[last:m.start()], quote=False) + "<x%d/>" % n[0]; n[0] += 1; last = m.end()
    return out + html.escape(s[last:], quote=False)


def unprotect(t, original):
    toks = re.findall(r"\{[^{}]*\}|%(?:\d\$)?[sdf]|%\.\d[f]", original)
    for i, tok in enumerate(toks):
        t = t.replace("<x%d/>" % i, tok)
    return html.unescape(re.sub(r"<x\d+/>", "", t))


def deepl(texts, key):
    host = "api-free.deepl.com" if key.endswith(":fx") else "api.deepl.com"
    out = []
    for i in range(0, len(texts), 40):
        chunk = texts[i:i + 40]
        data = urllib.parse.urlencode([("text", protect(t)) for t in chunk] + [("source_lang", "PT"), ("target_lang", "EN-US"),
                                        ("tag_handling", "xml"), ("ignore_tags", ",".join("x%d" % k for k in range(12)))]).encode()
        req = urllib.request.Request(f"https://{host}/v2/translate", data=data, headers={"Authorization": "DeepL-Auth-Key " + key})
        try:
            r = json.load(urllib.request.urlopen(req, timeout=60))
        except urllib.error.HTTPError as e:
            sys.exit("DeepL recusou: %s %s" % (e.code, e.read()[:200]))
        out += [unprotect(x["text"], t) for x, t in zip(r["translations"], chunk)]
    return out


def write_android_assets(cur):
    """Copia o dicionario da app para os assets do Android (lido por Tr.java)."""
    d = os.path.join(ROOT, "android", "app", "src", "main", "assets")
    os.makedirs(d, exist_ok=True)
    json.dump({k: v for k, v in cur["app"].items() if v.strip() != k.strip()}, open(os.path.join(d, "i18n_en.json"), "w", encoding="utf-8"), ensure_ascii=False)


def main():
    web, java = collect()
    cur = {"web": {}, "app": {}}
    if os.path.exists(OUT):
        cur = json.load(open(OUT, encoding="utf-8"))
        cur.setdefault("web", {}); cur.setdefault("app", {})
    todo_w = sorted(s for s in web if s not in cur["web"])
    todo_a = sorted(s for s in java if s not in cur["app"])
    print(f"web: {len(web)} textos ({len(todo_w)} novos) | app: {len(java)} textos ({len(todo_a)} novos)")
    if "--dry" in sys.argv:
        return
    if not (todo_w or todo_a):
        write_android_assets(cur)
        return
    key = os.environ.get("DEEPL_API_KEY", "")
    if not key:
        try:
            for l in open(os.path.expanduser("~/.config/odysseus-kit/deepl.env")):
                if l.startswith("DEEPL_API_KEY="):
                    key = l.split("=", 1)[1].strip()
        except OSError:
            pass
    if not key:
        sys.exit("Falta a chave DeepL (assistente de configuracao, passo Traducao).")
    for bucket, todo in (("web", todo_w), ("app", todo_a)):
        for s, t in zip(todo, deepl(todo, key)):
            cur[bucket][s] = t
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(cur, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)
    print("escrito", OUT)
    write_android_assets(cur)


if __name__ == "__main__":
    main()
