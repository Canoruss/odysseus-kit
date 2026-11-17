"""Groq (gratis, rapido): leitura de imagens com qwen3.8-27b. Devolve texto JSON ou levanta excecao."""
import sys as _s, os as _o
_s.path.insert(0, _o.path.join(_o.path.dirname(_o.path.abspath(__file__)), ".."))
from kitconfig import *
from kitconfig import secret_file
import json, os, urllib.request

def _key():
    for l in open(secret_file("groq")):
        if l.startswith("GROQ_API_KEY="): return l.strip().split("=", 1)[1]
    raise RuntimeError("sem chave groq")

def vision_json(prompt, b64, mime="image/jpeg", timeout=25):
    body = {"model": "qwen/qwen3.8-27b", "temperature": 0, "response_format": {"type": "json_object"},
            "messages": [{"role": "user", "content": [{"type": "text", "text": prompt},
                         {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}]}]}
    rq = urllib.request.Request("https://api.groq.com/openai/v1/chat/completions", json.dumps(body).encode(),
                                {"Content-Type": "application/json", "Authorization": "Bearer " + _key(), "User-Agent": "finance-tool/1.0"})
    return json.load(urllib.request.urlopen(rq, timeout=timeout))["choices"][0]["message"]["content"]


def vision_multi(prompt, images, mime="image/jpeg", json_out=False, timeout=60):
    """Varias imagens (lista de base64) -> texto. Levanta excecao se falhar."""
    body = {"model": "qwen/qwen3.8-27b", "temperature": 0.2,
            "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}] +
                         [{"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b}"}} for b in images]}]}
    if json_out: body["response_format"] = {"type": "json_object"}
    rq = urllib.request.Request("https://api.groq.com/openai/v1/chat/completions", json.dumps(body).encode(),
                                {"Content-Type": "application/json", "Authorization": "Bearer " + _key(), "User-Agent": "finance-tool/1.0"})
    t = json.load(urllib.request.urlopen(rq, timeout=timeout))["choices"][0]["message"]["content"]
    if not t or not t.strip(): raise RuntimeError("resposta vazia")
    return t
