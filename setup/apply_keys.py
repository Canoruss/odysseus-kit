#!/usr/bin/env python3
"""Odysseus KIT: apply your own API keys automatically (used by install.sh --keys-file and the desktop app).
Keys file (JSON), made by the Odysseus desktop app or by hand:
  {"timezone": "Europe/Lisbon",
   "steps":  {"ai_groq": {"GROQ_API_KEY": "gsk_..."}, "translate": {"DEEPL_API_KEY": "..."}},
   "models": [{"name": "Groq", "base_url": "https://api.groq.com/openai/v1", "api_key": "gsk_..."}]}
 - "steps": same ids/fields as the setup wizard (setup/wizard.py); each listed step is switched on.
 - "models": OpenAI-compatible endpoints, added to Odysseus (shared, all users).
Keys never leave this machine except to the provider you chose. Nothing is printed."""
import argparse, http.cookiejar, json, os, sys, urllib.error, urllib.parse, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wizard  # noqa: E402  (no server starts on import)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keys", required=True)
    ap.add_argument("--url", default="http://127.0.0.1:7860")
    ap.add_argument("--user", required=True)
    ap.add_argument("--password", required=True)
    a = ap.parse_args()
    data = json.load(open(a.keys, encoding="utf-8"))
    failed = 0
    if data.get("timezone"):
        c = wizard.load(); c["timezone"] = str(data["timezone"]); wizard.save(c)
    for sid, vals in (data.get("steps") or {}).items():
        if sid in wizard.BYID and isinstance(vals, dict):
            wizard.apply(sid, {"enabled": True, "values": {k: v for k, v in vals.items() if isinstance(v, str)}})
            print("step", sid, "configured")
    models = [m for m in (data.get("models") or []) if m.get("base_url")]
    if models:
        jar = http.cookiejar.CookieJar()
        op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        req = urllib.request.Request(a.url + "/api/login", json.dumps({"username": a.user, "password": a.password}).encode(),
                                     {"Content-Type": "application/json"})
        try:
            op.open(req, timeout=20).read()
        except Exception as e:
            print("login failed:", getattr(e, "code", e)); return 1
        for m in models:
            body = urllib.parse.urlencode({"name": m.get("name", ""), "base_url": m["base_url"], "api_key": m.get("api_key", ""),
                                           "shared": "true", "skip_probe": "true"}).encode()
            try:
                op.open(urllib.request.Request(a.url + "/api/model-endpoints", body), timeout=60).read()
                print("model endpoint", m.get("name") or m["base_url"], "added")
            except urllib.error.HTTPError as e:
                print("model endpoint", m.get("name") or m["base_url"], "failed: HTTP", e.code); failed += 1
            except Exception as e:
                print("model endpoint failed:", type(e).__name__); failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
