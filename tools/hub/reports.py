"""Relatorios medicos no Gym: a IA le o documento (foto ou PDF), resume os pontos de atencao e sugere ajustes ao treino/alimentacao
para falar com o medico. Guarda so o resumo, nunca o ficheiro."""
import sys as _s, os as _o
_s.path.insert(0, _o.path.join(_o.path.dirname(_o.path.abspath(__file__)), ".."))
from kitconfig import *
from kitconfig import secret_file
import json, os, html, datetime, urllib.request

def _key():
    for l in open(secret_file("gemini")):
        if l.startswith("GEMINI_API_KEY="): return l.strip().split("=", 1)[1]
    raise RuntimeError("sem chave")

def analyze(mime, b64, goal_note=""):
    prompt = ("Lês um relatório ou análise médica (análises ao sangue, consulta, exame). Responde só com JSON em português de Portugal: "
              '{"tipo": "tipo de documento", "data": "AAAA-MM-DD ou null", "resumo": "2 a 4 frases simples", '
              '"fora_do_normal": [{"nome": "...", "valor": "...", "referencia": "...", "nota": "o que pode significar, simples"}], '
              '"possiveis_deficiencias": ["..."], '
              '"ajustes_treino_alimentacao": ["sugestões práticas e prudentes para treino e alimentação, a confirmar com o médico"], '
              '"perguntas_para_o_medico": ["..."]}. '
              "Não faças diagnósticos nem alteres medicação ou doses de insulina. Se o documento não for legível ou não for médico, devolve resumo a explicar isso e listas vazias. "
              + (("Contexto da pessoa: " + goal_note) if goal_note else ""))
    key = _key(); last = None
    for m in ("gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.5-flash-lite"):
        body = json.dumps({"contents": [{"parts": [{"text": prompt}, {"inline_data": {"mime_type": mime, "data": b64}}]}],
                           "generationConfig": {"responseMimeType": "application/json"}}).encode()
        rq = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent", body,
                                    {"Content-Type": "application/json", "x-goog-api-key": key})
        try:
            r = json.load(urllib.request.urlopen(rq, timeout=120))
            o = json.loads(r["candidates"][0]["content"]["parts"][0]["text"])
            if isinstance(o, list): o = o[0]
            clip = lambda v, n: [str(x)[:300] for x in (v or [])][:n] if isinstance(v, list) else []
            fora = []
            for x in (o.get("fora_do_normal") or [])[:25]:
                if isinstance(x, dict):
                    fora.append({k: str(x.get(k) or "")[:200] for k in ("nome", "valor", "referencia", "nota")})
            return {"tipo": str(o.get("tipo") or "")[:80], "data": str(o.get("data") or "")[:10], "resumo": str(o.get("resumo") or "")[:700],
                    "fora": fora, "defs": clip(o.get("possiveis_deficiencias"), 12), "ajustes": clip(o.get("ajustes_treino_alimentacao"), 12),
                    "perguntas": clip(o.get("perguntas_para_o_medico"), 12), "analisado": datetime.date.today().isoformat()}
        except Exception as e:
            last = e
    raise RuntimeError(last)

def put(store, rep):
    store.setdefault("reports", []).insert(0, rep); del store["reports"][20:]

def box(store, url):
    li = lambda xs: "".join(f"<li>{html.escape(x)}</li>" for x in xs) or "<li style='color:#8b93a5'>nenhum</li>"
    out = ""
    for i, r in enumerate(store.get("reports", [])[:5]):
        fora = "".join(f"<tr><td><b>{html.escape(x['nome'])}</b></td><td>{html.escape(x['valor'])}</td><td style='color:#8b93a5'>{html.escape(x['referencia'])}</td><td>{html.escape(x['nota'])}</td></tr>" for x in r["fora"]) or "<tr><td style='color:#8b93a5'>Sem valores fora do normal identificados.</td></tr>"
        out += (f"<details class='box' {'open' if i == 0 else ''}><summary>{html.escape(r['tipo'] or 'Relatório')} · {html.escape(r['data'] or r['analisado'])}</summary><div class='in'>"
                f"<p>{html.escape(r['resumo'])}</p><h3>Fora do normal</h3><table>{fora}</table><h3>Possíveis défices</h3><ul>{li(r['defs'])}</ul>"
                f"<h3>Ajustes a treino e alimentação (a confirmar com o médico)</h3><ul>{li(r['ajustes'])}</ul><h3>Perguntas para o médico</h3><ul>{li(r['perguntas'])}</ul>"
                f"<form method='post' action='{url}/del' style='margin-top:8px'><input type='hidden' name='i' value='{i}'><button>Apagar análise</button></form></div></details>")
    return (f"<div class='box'><h2>Relatórios médicos</h2><div style='color:#9aa3b2;font-size:13px;margin-bottom:8px'>Envia uma foto ou PDF da análise. A IA resume e sugere o que falar com o médico. "
            "Só guarda o resumo, não o ficheiro. Não substitui o médico e não altera medicação nem insulina.</div>"
            "<input type='file' id='rp' accept='image/*,application/pdf'> <button type='button' onclick='rsend()'>Analisar</button> <span id='rps' style='color:#9aa3b2'></span></div>"
            + out + "<script>async function rsend(){const f=document.getElementById('rp').files[0],s=document.getElementById('rps');if(!f){s.textContent='Escolhe um ficheiro.';return}"
            "if(f.size>8e6){s.textContent='Ficheiro demasiado grande (máx. 8 MB).';return}s.textContent='A ler o relatório… pode demorar 1 minuto.';"
            "const b=await new Promise(o=>{const r=new FileReader();r.onload=()=>o(String(r.result).split(',')[1]);r.readAsDataURL(f)});"
            f"try{{const r=await fetch('{url}',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{mime:f.type||'application/pdf',data:b}})}});"
            "const j=await r.json();if(!r.ok||j.error)throw new Error(j.error||r.status);location.reload()}catch(e){s.textContent='Erro: '+e.message}}</script>")
