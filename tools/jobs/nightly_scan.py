#!/usr/bin/env python3
"""Nightly scan (cron, e.g. 04:00). Deterministic checks first; an optional free Groq model only SUMMARISES the facts.
Checks: Odysseus login page, KIT services (systemd), Docker containers, disk/memory, and, if a tester account exists
(~/.config/odysseus-kit/tester.env with ODY_USER / ODY_PASSWORD), the KIT tool pages through that login.
A finding is only reported when the check output proves it (the model cannot invent failures).
Output: <jobs>/nightly/latest.json + history.jsonl. Optional alert: ~/.config/odysseus-kit/telegram.env (BOT_TOKEN, CHAT_ID).
Usage: nightly_scan.py [--no-ai] [--quiet]"""
import datetime, http.cookiejar, json, os, shutil, subprocess, sys, time, urllib.request
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from kitconfig import JOBS_STATE, get, secret_file
OUT = os.path.join(JOBS_STATE, "nightly"); os.makedirs(OUT, exist_ok=True)
ODY = get("odysseus_url", "http://127.0.0.1:7860").rstrip("/")
HUB = "http://127.0.0.1:%s" % get("hub_port", 8792)
NOAI = "--no-ai" in sys.argv
facts = []   # {"check", "ok", "detail"}


def fact(check, ok, detail=""):
    facts.append({"check": check, "ok": bool(ok), "detail": str(detail)[:300]})


def sh(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except Exception as e:
        return 1, "", repr(e)


def env(path):
    out = {}
    try:
        for l in open(path):
            l = l.strip()
            if l.startswith("export "): l = l[7:]
            if "=" in l and not l.startswith("#"):
                k, v = l.split("=", 1); out[k.strip()] = v.strip().strip("'\"")
    except OSError:
        pass
    return out


def check_system():
    du = shutil.disk_usage("/")
    fact("disk-free", du.free / du.total > 0.10, "%.0f%% free" % (100 * du.free / du.total))
    mem = {l.split(":")[0]: int(l.split()[1]) for l in open("/proc/meminfo") if ":" in l}
    fact("memory-available", mem["MemAvailable"] / mem["MemTotal"] > 0.08, "%.0f%% available" % (100 * mem["MemAvailable"] / mem["MemTotal"]))
    for svc in ("kit-hub", "kit-translate", "kit-canva", "kit-wizard"):
        rc, o, _ = sh(["systemctl", "is-active", svc])
        if o != "" and (rc == 0 or o != "unknown"):
            fact("service:" + svc, o == "active", o)
    rc, o, _ = sh(["docker", "ps", "-a", "--format", "{{.Names}}|{{.Status}}"], timeout=20)
    if rc == 0:
        for l in o.splitlines():
            n, _, st = l.partition("|")
            fact("container:" + n, st.startswith("Up") and "unhealthy" not in st, st)


def get_url(url, headers=None, timeout=20):
    t = time.time()
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, headers=headers or {}), timeout=timeout)
        return r.status, r.read(400000).decode("utf-8", "replace"), time.time() - t
    except urllib.error.HTTPError as e:
        return e.code, "", time.time() - t
    except Exception as e:
        return 0, repr(e), time.time() - t


def check_http():
    st, body, dt = get_url(ODY + "/login")
    fact("odysseus-login-page", st == 200, "HTTP %s in %.1fs" % (st, dt))
    e = env(secret_file("tester"))
    if not e.get("ODY_USER"):
        fact("tester-account", True, "skipped: no tester.env")
        return
    try:
        cj = http.cookiejar.CookieJar()
        op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        op.open(urllib.request.Request(ODY + "/api/auth/login", json.dumps({"username": e["ODY_USER"], "password": e["ODY_PASSWORD"]}).encode(), {"Content-Type": "application/json"}), timeout=30)
        cookie = "; ".join("%s=%s" % (c.name, c.value) for c in cj)
    except Exception as ex:
        fact("tester-login", False, repr(ex)); return
    fact("tester-login", True, "ok")
    for path in ("/", "/period", "/focus", "/games", "/m/gym"):
        st, body, dt = get_url(HUB + path, {"Cookie": cookie})
        bad = st >= 500 or st == 0 or "Traceback" in body
        fact("page:" + path, not bad, "HTTP %s in %.1fs%s" % (st, dt, " (error text in page)" if "Traceback" in body else ""))


def ai_summary(bad):
    key = env(secret_file("groq")).get("GROQ_API_KEY")
    if NOAI or not key or not bad:
        return None
    body = {"model": get("scan_model", "openai/gpt-oss-120b"), "temperature": 0.1, "max_tokens": 700,
            "messages": [{"role": "system", "content": "You summarise server check results. Use ONLY the facts given. For each failed check say in one line what it means and one likely fix. Never mention a problem that is not in the list. Answer in the user's language: " + get("language", "en")},
                         {"role": "user", "content": json.dumps(bad)}]}
    rq = urllib.request.Request("https://api.groq.com/openai/v1/chat/completions", json.dumps(body).encode(), {"Content-Type": "application/json", "Authorization": "Bearer " + key, "User-Agent": "kit-nightly/1.0"})
    for k in range(3):
        try: return json.load(urllib.request.urlopen(rq, timeout=90))["choices"][0]["message"]["content"].strip()
        except urllib.error.HTTPError as e:
            if e.code not in (429, 503): return None
            time.sleep(10 * (k + 1))
        except Exception:
            return None


def main():
    check_system(); check_http()
    bad = [f for f in facts if not f["ok"]]
    summary = ai_summary(bad)
    res = {"time": datetime.datetime.now().isoformat(timespec="seconds"), "ok": not bad, "checks": len(facts), "failed": bad, "summary": summary}
    json.dump(dict(res, facts=facts), open(os.path.join(OUT, "latest.json"), "w"), indent=1, ensure_ascii=False)
    open(os.path.join(OUT, "history.jsonl"), "a").write(json.dumps(res, ensure_ascii=False) + "\n")
    msg = "Nightly scan: %d checks, %s" % (len(facts), "all OK" if not bad else "%d FAILED\n" % len(bad) + "\n".join("- %s: %s" % (f["check"], f["detail"]) for f in bad) + (("\n\n" + summary) if summary else ""))
    if "--quiet" not in sys.argv: print(msg)
    t = env(secret_file("telegram"))
    if bad and t.get("BOT_TOKEN") and t.get("CHAT_ID"):
        try: urllib.request.urlopen(urllib.request.Request("https://api.telegram.org/bot%s/sendMessage" % t["BOT_TOKEN"], json.dumps({"chat_id": t["CHAT_ID"], "text": msg[:3800]}).encode(), {"Content-Type": "application/json"}), timeout=20)
        except Exception: pass


if __name__ == "__main__":
    main()
