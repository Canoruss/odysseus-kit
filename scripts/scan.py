#!/usr/bin/env python3
"""Verificacao antes de publicar: procura segredos e dados pessoais.
Uso: python3 scripts/scan.py [pasta]   (sai com codigo 1 se encontrar algo)
 - Padroes de chaves conhecidas (embutidos).
 - Lista privada de termos pessoais em ~/.config/odysseus-kit/scan-private.txt (um por linha, NAO vai para o repositorio)."""
import os, re, sys
ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), ".."))
PATTERNS = {
    "Google API key": r"AIza[0-9A-Za-z_\-]{30,}", "Groq key": r"gsk_[A-Za-z0-9]{20,}", "Tailscale key": r"tskey-[A-Za-z0-9\-]{10,}",
    "GitHub token": r"(github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9]{30,})", "OpenAI/Anthropic key": r"sk-(ant-)?[A-Za-z0-9\-_]{25,}",
    "Slack token": r"xox[abprs]-[A-Za-z0-9\-]{10,}", "Telegram bot token": r"\b\d{8,10}:[A-Za-z0-9_\-]{35}\b",
    "Private key": r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "Canva secret": r"cnvca[A-Za-z0-9\-_]{20,}",
    "Password assignment": r"(?i)(password|passwd|secret|api[_-]?key|token)\s*[:=]\s*['\"][^'\"\s]{8,}['\"]",
    "Email address": r"\b[A-Za-z0-9._%+\-]+@(?!example\.|YOUR|your)[A-Za-z0-9.\-]+\.[a-z]{2,}\b",
    "Tailnet host": r"[a-z0-9\-]+\.tail[0-9a-f]{4,}\.ts\.net", "Home path": r"/home/[a-z][a-z0-9_\-]*/",
    "Private IP": r"\b(192\.168|10\.\d{1,3}|172\.(1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}\b",
}
ALLOW = {"Email address": ("noreply@", "git@github.com")}
SKIP_DIRS = {".git", "node_modules", "build", ".gradle", "__pycache__"}
SKIP_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico", ".ttf", ".woff", ".woff2", ".mp3", ".apk", ".jar", ".zip", ".pyc")
priv = []
try:
    priv = [l.strip() for l in open(os.path.expanduser("~/.config/odysseus-kit/scan-private.txt"), encoding="utf-8") if l.strip() and not l.startswith("#")]
except OSError:
    print("(aviso: sem lista privada em ~/.config/odysseus-kit/scan-private.txt; so uso os padroes embutidos)")
hits = 0
for dp, dn, fn in os.walk(ROOT):
    dn[:] = [d for d in dn if d not in SKIP_DIRS]
    for f in fn:
        p = os.path.join(dp, f)
        rel = os.path.relpath(p, ROOT)
        if f.endswith(SKIP_EXT) or f == "LICENSE" or rel == os.path.join("scripts", "scan.py"):
            continue
        try:
            txt = open(p, encoding="utf-8").read()
        except Exception:
            continue
        for i, line in enumerate(txt.splitlines(), 1):
            for name, rx in PATTERNS.items():
                for m in re.finditer(rx, line):
                    if any(a in m.group(0) for a in ALLOW.get(name, ())):
                        continue
                    print(f"{rel}:{i}: [{name}] {line.strip()[:110]}")
                    hits += 1
            for term in priv:
                if term.lower() in line.lower():
                    print(f"{rel}:{i}: [termo privado] {line.strip()[:110]}")
                    hits += 1
print(f"\n{hits} problema(s) encontrado(s)." if hits else "\nLimpo: nada encontrado.")
sys.exit(1 if hits else 0)
