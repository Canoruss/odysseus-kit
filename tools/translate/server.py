import sys as _s, os as _o
_s.path.insert(0, _o.path.join(_o.path.dirname(_o.path.abspath(__file__)), ".."))
from kitconfig import *
from kitconfig import secret_file
import os
#!/usr/bin/env python3
"""Odysseus translator backend (tailnet only, via `tailscale serve --set-path /translate`).
POST /translate/api  {"text": "...", "source": "auto|pt|en|...", "target": "pt|en|..."}
  -> {"translation": "...", "detected": "en", "engine": "gemini-3.6-flash"}
Portuguese is always European Portuguese (pt-PT). Gemini (free) first, Claude Haiku (bridge) as fallback.
"""
import json, os, time, urllib.request, urllib.error
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

KEY = ""
try:
    for line in open(secret_file("gemini")):
        if line.startswith("GEMINI_API_KEY="):
            KEY = line.split("=", 1)[1].strip()
except OSError:
    pass  # opcional: sem chave Gemini, usa os outros motores
GEMINI_MODELS = ["gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.5-flash-lite"]  # then Claude Haiku as last resort
BRIDGE = "http://127.0.0.1:8787/v1/chat/completions"
BKEY = ""
try:  # opcional: bridge OpenAI-compativel (ex.: Claude Code) em ~/.config/odysseus-kit/bridge.env
    for line in open(secret_file("bridge")):
        if line.startswith("BRIDGE_API_KEY="):
            BKEY = line.split("=", 1)[1].strip().strip('"\'')
except OSError:
    pass

NAMES = {"pt": "European Portuguese (Portugal)", "en": "English", "es": "Spanish", "fr": "French", "de": "German",
         "it": "Italian", "nl": "Dutch", "zh": "Chinese (Simplified)", "ja": "Japanese", "ko": "Korean", "ar": "Arabic",
         "ru": "Russian", "uk": "Ukrainian", "ro": "Romanian", "pl": "Polish", "tr": "Turkish", "hi": "Hindi",
         "sv": "Swedish", "el": "Greek", "ca": "Catalan", "cs": "Czech", "da": "Danish", "fi": "Finnish", "he": "Hebrew",
         "hu": "Hungarian", "id": "Indonesian", "no": "Norwegian", "th": "Thai", "vi": "Vietnamese", "bg": "Bulgarian",
         "hr": "Croatian", "sk": "Slovak", "sl": "Slovenian", "sr": "Serbian", "lt": "Lithuanian", "lv": "Latvian",
         "et": "Estonian", "fa": "Persian", "bn": "Bengali", "ur": "Urdu", "ms": "Malay", "tl": "Filipino",
         "sw": "Swahili", "af": "Afrikaans", "ga": "Irish", "eu": "Basque", "gl": "Galician"}

PT_RULE = ("When writing Portuguese, ALWAYS use European Portuguese as written in Portugal (pre-2009 vocabulary is fine, "
           "but follow the current Portugal norm): e.g. 'comboio' not 'trem', 'autocarro' not 'ônibus', 'telemóvel' not "
           "'celular', 'casa de banho' not 'banheiro', 'pequeno-almoço' not 'café da manhã', 'ecrã' not 'tela', "
           "'facto', 'receção', 'estou a fazer' (never 'estou fazendo'), clitic placement as in Portugal. Never Brazilian Portuguese.")


def prompt(text, src, tgt):
    s = "Detect the source language" if src in ("", "auto") else f"The source language is {NAMES.get(src, src)}"
    return (f"You are a professional translator. {s}. Translate the text into {NAMES.get(tgt, tgt)}. {PT_RULE} "
            "Keep the meaning, tone, formatting, line breaks, names and numbers. Do not add explanations. "
            "If the text is already in the target language, return it improved only if it is not European Portuguese; "
            'otherwise unchanged. Answer ONLY with JSON: {"detected": "<ISO 639-1 code of the source>", "translation": "<text>"}.'
            f"\n\nTEXT:\n{text}")


def post(url, body, headers, timeout):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def parse(raw):
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw[raw.find("{"):]
    j = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
    return j.get("translation", ""), (j.get("detected") or "").lower()[:2]


GROQ_KEY = ""
try:
    for line in open(secret_file("groq")):
        if line.startswith("GROQ_API_KEY="):
            GROQ_KEY = line.split("=", 1)[1].strip().strip('"\'')
except OSError:
    pass
DEEPL_KEY = ""
try:
    for line in open(secret_file("deepl")):
        if line.startswith("DEEPL_API_KEY="):
            DEEPL_KEY = line.split("=", 1)[1].strip().strip('"\'')
except OSError:
    pass


def deepl(text, src, tgt):
    host = "api-free.deepl.com" if DEEPL_KEY.endswith(":fx") else "api.deepl.com"
    body = {"text": [text], "target_lang": "PT-PT" if tgt == "pt" else tgt.upper().replace("EN", "EN-GB")}
    if src and src != "auto":
        body["source_lang"] = src.upper()
    d = post(f"https://{host}/v2/translate", body, {"Authorization": "DeepL-Auth-Key " + DEEPL_KEY}, 8)
    r = d["translations"][0]
    return {"translation": r["text"], "detected": r.get("detected_source_language", "").lower()[:2], "engine": "deepl"}


def translate(text, src, tgt):
    if DEEPL_KEY:
        try:
            return deepl(text, src, tgt)
        except Exception:
            pass
    p = prompt(text, src, tgt)
    for m in GEMINI_MODELS:
        try:
            d = post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent",
                     {"contents": [{"parts": [{"text": p}]}],
                      "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2}},
                     {"x-goog-api-key": KEY}, 15)
            out = "".join(x.get("text", "") for x in d["candidates"][0]["content"]["parts"])
            t, det = parse(out)
            if t:
                return {"translation": t, "detected": det, "engine": m}
        except Exception:
            continue
    d = post(BRIDGE, {"model": "claude-code-haiku", "messages": [{"role": "user", "content": p}]}, {"Authorization": "Bearer " + BKEY}, 120)
    t, det = parse(d["choices"][0]["message"]["content"])
    return {"translation": t, "detected": det, "engine": "claude-haiku"}


def ask_json(prompt_text, image_b64=None, fast=False):
    """Gemini (com imagem opcional) -> Claude Haiku; devolve o JSON da resposta."""
    parts = [{"text": prompt_text}]
    if image_b64:
        parts.append({"inline_data": {"mime_type": "image/jpeg", "data": image_b64}})
    if (fast or image_b64) and GROQ_KEY:
        for gm in (("qwen/qwen3.8-27b",) if image_b64 else ("qwen/qwen3.8-27b", "openai/gpt-oss-120b")):
            try:
                content = prompt_text if not image_b64 else [{"type": "text", "text": prompt_text},
                          {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + image_b64}}]
                body = {"model": gm, "messages": [{"role": "user", "content": content}], "temperature": 0.3,
                        "response_format": {"type": "json_object"}}
                if "gpt-oss" in gm:
                    body["reasoning_effort"] = "low"
                d = post("https://api.groq.com/openai/v1/chat/completions", body, {"Authorization": "Bearer " + GROQ_KEY, "User-Agent": "odysseus-translate/1.0"}, 15)
                out = d["choices"][0]["message"]["content"]
                return json.loads(out[out.find("{"): out.rfind("}") + 1]), "groq:" + gm.split("/")[-1]
            except Exception:
                continue
    if fast and not image_b64:
        # Gemini gratuito oscila (429/503, esperas de ~12 s); o Haiku pelo bridge responde sempre em ~2 s.
        try:
            d = post(BRIDGE, {"model": "claude-code-haiku", "messages": [{"role": "user", "content": prompt_text}]}, {"Authorization": "Bearer " + BKEY}, 25)
            out = d["choices"][0]["message"]["content"]
            return json.loads(out[out.find("{"): out.rfind("}") + 1]), "claude-haiku"
        except Exception:
            pass
    models = GEMINI_MODELS
    for m in models:
        try:
            gc = {"responseMimeType": "application/json", "temperature": 0.3}
            d = post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent",
                     {"contents": [{"parts": parts}], "generationConfig": gc},
                     {"x-goog-api-key": KEY}, 45)
            out = "".join(x.get("text", "") for x in d["candidates"][0]["content"]["parts"])
            return json.loads(out[out.find("{"): out.rfind("}") + 1]), m
        except Exception:
            continue
    msgs = [{"role": "user", "content": prompt_text}]
    if image_b64:
        msgs = [{"role": "user", "content": [{"type": "text", "text": prompt_text},
                {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + image_b64}}]}]
    d = post(BRIDGE, {"model": "claude-code-haiku", "messages": msgs}, {"Authorization": "Bearer " + BKEY}, 120)
    out = d["choices"][0]["message"]["content"]
    return json.loads(out[out.find("{"): out.rfind("}") + 1]), "claude-haiku"


def groq_whisper(wav_bytes, lang):
    """Whisper large-v3-turbo no Groq (gratis, ~0,3 s). Devolve o texto ou levanta excecao."""
    import uuid
    bd = uuid.uuid4().hex
    fields = {"model": "whisper-large-v3-turbo", "response_format": "json", "temperature": "0"}
    if lang and lang != "auto":
        fields["language"] = lang[:2]
    body = b"".join(f'--{bd}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode() for k, v in fields.items())
    body += f'--{bd}\r\nContent-Disposition: form-data; name="file"; filename="a.wav"\r\nContent-Type: audio/wav\r\n\r\n'.encode() + wav_bytes + f"\r\n--{bd}--\r\n".encode()
    req = urllib.request.Request("https://api.groq.com/openai/v1/audio/transcriptions", body,
                                 {"Authorization": "Bearer " + GROQ_KEY, "Content-Type": "multipart/form-data; boundary=" + bd,
                                  "User-Agent": "odysseus-translate/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return (json.loads(r.read()).get("text") or "").strip()


def stt(b64, mime, lang):
    """Transcreve áudio gravado no telemóvel/browser (webm/mp4/ogg) com Gemini; converte para wav com ffmpeg."""
    import subprocess, base64 as b64m
    raw = b64m.b64decode(b64)
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", "pipe:0", "-ac", "1", "-ar", "16000", "-f", "wav", "pipe:1"], input=raw, capture_output=True, timeout=30)
    if r.returncode != 0 or not r.stdout:
        raise RuntimeError("áudio inválido")
    if GROQ_KEY:
        try:
            return groq_whisper(r.stdout, lang)
        except Exception:
            pass  # cai para o Gemini
    wav = b64m.b64encode(r.stdout).decode()
    hint = f" O idioma falado é provavelmente '{lang}'." if lang and lang != "auto" else ""
    q = "Transcreve fielmente a fala deste áudio. Devolve só o texto falado, sem aspas nem comentários." + hint + " Se não houver fala, devolve texto vazio."
    last = None
    for m in ("gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-3.6-flash"):
        try:
            d = post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent",
                     {"contents": [{"parts": [{"text": q}, {"inline_data": {"mime_type": "audio/wav", "data": wav}}]}], "generationConfig": {"temperature": 0}},
                     {"x-goog-api-key": KEY}, 30)
            return "".join(x.get("text", "") for x in d["candidates"][0]["content"]["parts"]).strip()
        except Exception as e:
            last = e
    raise RuntimeError("transcrição indisponível: " + str(last)[:80])


def guest_reply(message, lang, note):
    gl = NAMES.get(lang, lang or "the guest's language")
    p = ("You help the manager of tourist apartments in Portugal answer a guest. Write a short, warm and professional reply "
         f"to the guest's message, in {gl} (detect it from the message if unclear). "
         + ("The manager wants to say: " + note + ". " if note else "")
         + "NEVER invent or confirm facts, prices, codes, times or amenities that are not given to you: for any question you were not told the answer to, say politely that you will confirm and get back to the guest. "
         + PT_RULE +
         ' Answer ONLY with JSON: {"lang": "<ISO 639-1 of the reply>", "reply": "<reply in the guest language>"}.'
         f"\n\nGUEST MESSAGE:\n{message}")
    j, eng = ask_json(p, fast=True)
    rl = (j.get("lang") or lang or "").lower()[:2]
    reply = j.get("reply", "")
    pt = reply
    if reply and rl != "pt":
        try:
            pt = translate(reply, rl or "auto", "pt")["translation"]  # DeepL: rápido e fiável
        except Exception:
            pt = ""
    return {"lang": rl, "reply": reply, "reply_pt": pt, "engine": eng}


def image_translate(b64, tgt):
    p = ("Read ALL the text visible in this photo (sign, menu, document, label). Then translate it into "
         f"{NAMES.get(tgt, tgt)}. {PT_RULE} Keep the structure (line breaks). "
         'Answer ONLY with JSON: {"detected": "<ISO 639-1 of the original text>", "original": "<the text as written>", "translation": "<translation>"}. '
         'If there is no readable text, use empty strings.')
    j, eng = ask_json(p, b64)
    return {"detected": (j.get("detected") or "").lower()[:2], "original": j.get("original", ""), "translation": j.get("translation", ""), "engine": eng}


# ---- voz neural (edge-tts, gratuito): devolve MP3 ----
import hashlib, subprocess, urllib.parse
_HERE = os.path.dirname(os.path.abspath(__file__))
EDGE = os.path.join(_HERE, "venv", "bin", "edge-tts")
TTS_DIR = os.path.join(_HERE, "tts-cache")
PREF = {"pt": "pt-PT-RaquelNeural", "en": "en-GB-SoniaNeural", "es": "es-ES-ElviraNeural", "fr": "fr-FR-DeniseNeural"}
LOCALE = {"zh": "zh-CN", "ar": "ar-SA", "de": "de-DE", "it": "it-IT", "nl": "nl-NL", "sv": "sv-SE", "ko": "ko-KR", "ja": "ja-JP",
          "el": "el-GR", "he": "he-IL", "fa": "fa-IR", "hi": "hi-IN", "uk": "uk-UA", "cs": "cs-CZ", "da": "da-DK", "no": "nb-NO",
          "tl": "fil-PH", "sw": "sw-KE", "bn": "bn-IN", "ur": "ur-PK", "ca": "ca-ES", "gl": "gl-ES", "eu": "eu-ES", "vi": "vi-VN"}
_voices = None

def voice_for(lang):
    global _voices
    lang = (lang or "pt").split("-")[0].lower()
    if lang in PREF:
        return PREF[lang]
    if _voices is None:
        out = subprocess.run([EDGE, "--list-voices"], capture_output=True, text=True, timeout=30).stdout
        _voices = [l.split()[0] for l in out.splitlines() if "Neural" in l]
    want = LOCALE.get(lang, lang) + "-"
    for pref in (want, lang + "-"):
        for v in _voices:
            if v.startswith(pref):
                return v
    return None

def tts(text, lang):
    text = " ".join((text or "").split())[:3000]
    v = voice_for(lang)
    if not text or not v:
        return None
    os.makedirs(TTS_DIR, exist_ok=True)
    f = os.path.join(TTS_DIR, hashlib.sha1((v + "|" + text).encode()).hexdigest() + ".mp3")
    if not os.path.exists(f) or os.path.getsize(f) == 0:
        tmp = f + ".%d.tmp" % os.getpid()
        ok = False
        for _try in range(3):
            try:
                r = subprocess.run([EDGE, "--voice", v, "--text=" + text, "--write-media", tmp], capture_output=True, timeout=20)
                ok = r.returncode == 0 and os.path.exists(tmp) and os.path.getsize(tmp) > 0
            except Exception:
                ok = False
            if ok: break
            time.sleep(0.4)
        if not ok:
            try: os.remove(tmp)
            except OSError: pass
            return None
        os.replace(tmp, f)
        files = sorted((os.path.join(TTS_DIR, x) for x in os.listdir(TTS_DIR)), key=os.path.getmtime)
        for old in files[:-200]:
            try: os.remove(old)
            except OSError: pass
    return open(f, "rb").read()


class H(BaseHTTPRequestHandler):
    def _audio(self, text, lang):
        try:
            b = tts(text, lang)
        except Exception:
            b = None
        if not b:
            return self._send(502, {"error": "Voz indisponível"})
        self.send_response(200)
        self.send_header("Content-Type", "audio/mpeg")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def log_message(self, *a):
        pass

    def _send(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        u = urllib.parse.urlsplit(self.path)
        if u.path.rstrip("/").endswith("/tts"):
            q = urllib.parse.parse_qs(u.query)
            return self._audio((q.get("text") or [""])[0], (q.get("lang") or ["pt"])[0])
        if self.path.rstrip("/").endswith("/languages"):
            return self._send(200, {"languages": [{"code": k, "name": v} for k, v in NAMES.items()]})
        self._send(200, {"ok": True})

    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length", 0))
            pth = self.path.split("?")[0].rstrip("/")
            if pth.endswith("/image"):
                if n > 6_000_000:
                    return self._send(413, {"error": "Imagem demasiado grande."})
                body = json.loads(self.rfile.read(n) or b"{}")
                t0 = time.time(); r = image_translate(body["image"], (body.get("target") or "pt").lower()); r["ms"] = int((time.time() - t0) * 1000)
                return self._send(200, r)
            if pth.endswith("/stt"):
                if n > 4_000_000:
                    return self._send(413, {"error": "Áudio demasiado longo."})
                body = json.loads(self.rfile.read(n) or b"{}")
                t0 = time.time(); txt = stt(body["audio"], body.get("mime") or "", (body.get("lang") or "").lower())
                return self._send(200, {"text": txt, "ms": int((time.time() - t0) * 1000)})
            if pth.endswith("/reply"):
                body = json.loads(self.rfile.read(min(n, 20000)) or b"{}")
                msg = (body.get("message") or "").strip()[:4000]
                if not msg:
                    return self._send(200, {"error": "Cola primeiro a mensagem do hóspede."})
                t0 = time.time(); r = guest_reply(msg, (body.get("lang") or "").lower(), (body.get("note") or "").strip()[:500]); r["ms"] = int((time.time() - t0) * 1000)
                return self._send(200, r)
            if n > 20000:
                return self._send(413, {"error": "Texto demasiado longo (máx. ~5000 palavras)."})
            body = json.loads(self.rfile.read(n) or b"{}")
            if self.path.split("?")[0].rstrip("/").endswith("/tts"):
                return self._audio(body.get("text") or "", body.get("lang") or "pt")
            text = (body.get("text") or "").strip()
            if not text:
                return self._send(200, {"translation": "", "detected": ""})
            t0 = time.time()
            r = translate(text, (body.get("source") or "auto").lower(), (body.get("target") or "pt").lower())
            r["ms"] = int((time.time() - t0) * 1000)
            tr = r.get("translation") or ""
            if tr and len(tr) < 600:
                import threading
                threading.Thread(target=lambda: tts(tr, (body.get("target") or "pt").lower()), daemon=True).start()
            self._send(200, r)
        except Exception as e:
            self._send(502, {"error": f"Tradução indisponível: {e}"})


ThreadingHTTPServer(("127.0.0.1", int(get("translate_port", 8791))), H).serve_forever()
