"""Ciclo: histórias curtas por fase e autoavaliações (Self Care). Nada é guardado; o resultado calcula-se no momento."""
import datetime, html
E = html.escape

# ---- Histórias: (título pt, título en, texto pt, texto en) por fase
STORIES = {
 "menstrual": [
  ("Descansar também é produtivo", "Resting is productive too",
   "Nos primeiros dias a energia costuma estar mais baixa. Não é preguiça: o corpo está a trabalhar. Hoje, troca uma tarefa pesada por algo leve e protege o teu sono. Uma bolsa de água quente na barriga ou nas costas ajuda com as cólicas.",
   "In the first days energy is often lower. It is not laziness, your body is working. Swap one heavy task for something light today and protect your sleep. A hot water bottle on your belly or back eases cramps."),
  ("Ferro e conforto", "Iron and comfort",
   "Com o fluxo perdes algum ferro. Lentilhas, grão, espinafres e carne magra ajudam, e a vitamina C (laranja, kiwi) melhora a absorção. Bebe água e come devagar, sem culpas.",
   "You lose some iron with your flow. Lentils, chickpeas, spinach and lean meat help, and vitamin C (orange, kiwi) improves absorption. Drink water and eat slowly, guilt-free."),
  ("Cólicas fortes não são 'normais' sempre", "Severe cramps are not always 'normal'",
   "Desconforto leve é comum. Dor que te impede de fazer o dia, fluxo que encharca a proteção todas as horas ou coágulos grandes merecem conversa com o médico. Regista os dias no Ciclo para levares dados à consulta.",
   "Mild discomfort is common. Pain that stops your day, flow soaking through every hour or large clots deserve a talk with your doctor. Log your days here so you bring data to the appointment.")],
 "folicular": [
  ("A energia está a voltar", "Your energy is coming back",
   "Depois do período, os estrogénios sobem e muita gente sente mais clareza, motivação e vontade de sair. É boa altura para começar projetos, treinos novos e conversas difíceis.",
   "After your period, estrogen rises and many people feel clearer, more motivated and sociable. A good time to start projects, new workouts and tough conversations."),
  ("Pele e cabelo", "Skin and hair",
   "Nesta fase a pele costuma estar mais equilibrada. Hidratação, protetor solar e sono regular fazem mais do que produtos complicados.",
   "Skin is often more balanced in this phase. Moisturiser, sunscreen and regular sleep do more than complicated products."),
  ("Treinar com mais intensidade", "Training harder",
   "O corpo recupera melhor agora. Se queres aumentar cargas ou tentar um treino novo, esta é uma boa janela. Aquece sempre e ouve os sinais.",
   "Your body recovers better now. If you want to add weight or try a new workout, this is a good window. Always warm up and listen to your body.")],
 "ovulatoria": [
  ("A janela fértil", "The fertile window",
   "A ovulação acontece cerca de 14 dias antes da menstruação seguinte. O corrimento fica claro e elástico, e pode haver uma dor leve de um lado. É quando a probabilidade de gravidez é mais alta.",
   "Ovulation happens about 14 days before your next period. Discharge turns clear and stretchy, and there may be mild one-sided pain. This is when pregnancy chance is highest."),
  ("Pico de energia e de confiança", "Peak energy and confidence",
   "Muita gente sente-se mais sociável e confiante. Aproveita para reuniões, apresentações e encontros. Se sentires a temperatura basal subir no dia seguinte, é sinal de que ovulou.",
   "Many people feel more social and confident. Use it for meetings, presentations and dates. A basal temperature rise the next day is a sign that ovulation happened."),
  ("Sinais para observar", "Signs to watch",
   "Corrimento tipo clara de ovo, libido mais alta, seios sensíveis e teste de ovulação positivo. Registar estes sinais torna as previsões mais certas.",
   "Egg-white discharge, higher libido, tender breasts and a positive ovulation test. Logging these signs makes predictions more accurate.")],
 "lutea": [
  ("Quando a TPM aparece", "When PMS shows up",
   "Na última semana a progesterona desce e podem surgir irritação, inchaço, vontade de doces e sono pior. É comum e passa quando o período chega. Menos sal, mais magnésio (frutos secos) e movimento suave ajudam.",
   "In the last week progesterone drops and irritability, bloating, cravings and poorer sleep may appear. It is common and passes when your period arrives. Less salt, more magnesium (nuts) and gentle movement help."),
  ("Sê gentil contigo", "Be kind to yourself",
   "Se as emoções estão mais intensas, lembra-te de que há uma razão hormonal. Reduz compromissos, diz que não sem culpa e reserva tempo para ti.",
   "If emotions feel more intense, remember there is a hormonal reason. Cut back commitments, say no without guilt and keep time for yourself."),
  ("Sono antes de tudo", "Sleep first",
   "A temperatura corporal sobe um pouco e o sono pode piorar. Quarto fresco, ecrãs desligados uma hora antes e chá sem cafeína ajudam a dormir melhor.",
   "Body temperature rises a little and sleep may suffer. A cool room, screens off an hour before bed and caffeine-free tea help you sleep better.")],
}
GENERIC = ("Conhece o teu ciclo", "Know your cycle",
           "O ciclo tem quatro fases: menstrual, folicular, ovulatória e lútea. Regista o primeiro dia do período e os sintomas, e a app aprende o teu padrão e ajusta as previsões.",
           "The cycle has four phases: menstrual, follicular, ovulatory and luteal. Log your first period day and symptoms, and the app learns your pattern and refines predictions.")
PH_NAME = {"menstrual": ("Menstrual", "Menstrual"), "folicular": ("Folicular", "Follicular"),
           "ovulatoria": ("Ovulatória", "Ovulatory"), "lutea": ("Lútea", "Luteal")}

# ---- Self Care: perguntas (pt, en), resposta 0..3 (nunca, às vezes, muitas vezes, sempre)
ANS = [("Nunca", "Never"), ("Às vezes", "Sometimes"), ("Muitas vezes", "Often"), ("Sempre", "Always")]
TESTS = {
 "sop": ("🌸", "Sinais de SOP", "PCOS signs", [
   ("Os meus ciclos são muito longos (mais de 35 dias) ou imprevisíveis", "My cycles are very long (over 35 days) or unpredictable"),
   ("Tenho pelos escuros no queixo, peito ou barriga", "I have dark hair on chin, chest or belly"),
   ("Tenho acne persistente", "I have persistent acne"),
   ("Tenho queda de cabelo no topo da cabeça", "I have thinning hair on top of my head"),
   ("Tenho dificuldade em controlar o peso", "I find it hard to manage my weight"),
   ("Tenho manchas escuras na pele (pescoço, axilas)", "I have dark patches on my skin (neck, armpits)")],
   (("Poucos sinais", "Few signs", "Poucos sinais relacionados com SOP. Continua a registar o ciclo."),
    ("Alguns sinais", "Some signs", "Há alguns sinais que podem ter várias causas. Se persistirem, fala com o teu médico."),
    ("Vários sinais", "Several signs", "Vários sinais em conjunto justificam uma consulta (ginecologia ou endocrinologia). Leva o histórico do Ciclo.")), ),
 "cansaco": ("🔋", "Cansaço", "Fatigue", [
   ("Acordo cansada mesmo depois de dormir", "I wake up tired even after sleeping"),
   ("Sinto falta de energia a meio do dia", "I lack energy mid-day"),
   ("Custa-me concentrar", "I find it hard to concentrate"),
   ("Sinto tonturas ou falta de ar com esforço leve", "I feel dizzy or breathless with light effort"),
   ("Tenho as mãos e os pés frios, ou palidez", "I have cold hands and feet, or paleness"),
   ("O cansaço piora durante o período", "My tiredness gets worse during my period")],
   (("Normal", "Normal", "Nível de cansaço dentro do esperado. Mantém sono e hidratação."),
    ("Moderado", "Moderate", "Cansaço moderado. Verifica sono, alimentação rica em ferro e stress. Se durar semanas, pede análises."),
    ("Elevado", "High", "Cansaço elevado, sobretudo com tonturas ou falta de ar. Marca uma consulta para ver ferro, tiroide e vitaminas.")), ),
 "tpm": ("🌙", "Humor e TPM", "Mood and PMS", [
   ("Fico irritada ou irritável na semana antes do período", "I get irritable in the week before my period"),
   ("Fico triste ou choro com facilidade", "I feel sad or cry easily"),
   ("Sinto ansiedade ou tensão", "I feel anxious or tense"),
   ("Tenho vontade intensa de doces ou comida", "I have strong cravings for sweets or food"),
   ("Sinto inchaço e seios sensíveis", "I feel bloated with tender breasts"),
   ("Os sintomas atrapalham o meu dia-a-dia", "The symptoms get in the way of my daily life")],
   (("Ligeira", "Mild", "Sintomas ligeiros. Movimento, sono e menos cafeína costumam bastar."),
    ("Moderada", "Moderate", "TPM moderada. Regista os sintomas no Ciclo, reduz sal e álcool, e mexe-te com regularidade."),
    ("Forte", "Strong", "Sintomas fortes que atrapalham o dia a dia. Fala com o médico: há tratamento eficaz, incluindo para a forma mais grave (PMDD).")), ),
 "sono": ("😴", "Sono", "Sleep", [
   ("Demoro mais de 30 minutos a adormecer", "It takes me over 30 minutes to fall asleep"),
   ("Acordo várias vezes durante a noite", "I wake up several times at night"),
   ("Durmo menos de 7 horas", "I sleep less than 7 hours"),
   ("Uso o telemóvel na cama até tarde", "I use my phone in bed late"),
   ("Bebo café ou bebidas energéticas à tarde", "I drink coffee or energy drinks in the afternoon"),
   ("Durmo pior na semana antes do período", "I sleep worse the week before my period")],
   (("Bom", "Good", "Os teus hábitos de sono estão bons."),
    ("A melhorar", "Could improve", "Há margem para melhorar: horário fixo, quarto fresco e escuro, e ecrãs desligados 1 hora antes."),
    ("Fraco", "Poor", "Sono fraco. Aplica a higiene do sono durante 2 semanas; se não melhorar, fala com o médico.")), ),
}
# limiares sobre a percentagem do máximo (6 perguntas x 3 = 18)
def _band(score, n):
    p = score * 100 // (n * 3)
    return 0 if p < 25 else (1 if p < 55 else 2)


def story_of_day(ph, today, lang):
    lst = STORIES.get(ph[0]) if ph and ph[0] else None
    if not lst:
        return GENERIC
    return lst[today.timetuple().tm_yday % len(lst)]


def _t(lang, pt, en):
    return en if lang == "en" else pt


def _story_card(s, lang, open_=False):
    return '<details%s><summary>%s</summary><p>%s</p></details>' % (
        " open" if open_ else "", E(_t(lang, s[0], s[1])), E(_t(lang, s[2], s[3])))


def nav(tab, lang):
    items = [("", "🏠", "Hoje", "Today"), ("stories", "📖", "Histórias", "Stories"), ("care", "💗", "Self Care", "Self Care"), ("ask", "🐧", "Pergunta ao Pingo", "Ask Pingo"), ("profile", "📝", "O meu perfil", "My profile")]
    return '<div class="row" style="margin:6px 0 10px">%s</div>' % "".join(
        '<a class="lnk" style="%s" href="/finance/period%s">%s %s</a>' % (
            "background:#2f8fbf;color:#fff" if tab == k else "", ("?tab=" + k) if k else "", ic, E(_t(lang, a, b)))
        for k, ic, a, b in items)


def stories(ph, today, lang):
    out = '<h3>%s</h3>' % _t(lang, "História de hoje", "Story of the day")
    out += '<div class="box">%s</div>' % _story_card(story_of_day(ph, today, lang), lang, True)
    cur = ph[0] if ph and ph[0] else None
    for key in ("menstrual", "folicular", "ovulatoria", "lutea"):
        nm = PH_NAME[key]
        out += '<div class="box"><b>%s%s</b>%s</div>' % (
            E(_t(lang, nm[0], nm[1])), (" · " + _t(lang, "a tua fase", "your phase")) if key == cur else "",
            "".join(_story_card(s, lang) for s in STORIES[key]))
    return out + '<p class="aviso">%s</p>' % _t(lang, "Conteúdo informativo, não substitui o médico.", "Informational only, not a substitute for your doctor.")


def care(q, lang):
    tid = q.get("t", "")
    if tid in TESTS:
        ic, npt, nen, qs, bands = TESTS[tid][0], TESTS[tid][1], TESTS[tid][2], TESTS[tid][3], TESTS[tid][4]
        vals = []
        for i in range(len(qs)):
            try:
                v = int(q.get("q%d" % i, ""))
                if 0 <= v <= 3:
                    vals.append(v)
            except ValueError:
                pass
        title = '%s %s' % (ic, E(_t(lang, npt, nen)))
        if len(vals) == len(qs):
            sc = sum(vals)
            b = bands[_band(sc, len(qs))]
            col = ("#3a7d44", "#b8860b", "#b23a48")[_band(sc, len(qs))]
            return ('<div class="box"><h3>%s</h3><p style="font-size:1.4em;margin:6px 0"><b style="color:%s">%s</b> · %d/%d</p><p>%s</p>'
                    '<p class="mut">%s</p><p><a class="lnk" href="/finance/period?tab=care">‹ %s</a> <a class="lnk" href="/finance/period?tab=care&t=%s">%s</a></p></div>' % (
                        title, col, E(_t(lang, b[0], b[1])), sc, len(qs) * 3, E(b[2] if lang != "en" else _en_adv(tid, _band(sc, len(qs)))),
                        _t(lang, "Isto não é um diagnóstico. Se tiveres dúvidas ou sintomas fortes, fala com o médico.", "This is not a diagnosis. If in doubt or symptoms are strong, talk to your doctor."),
                        _t(lang, "Voltar", "Back"), tid, _t(lang, "Repetir", "Retake")))
        rows = ""
        for i, (pt, en) in enumerate(qs):
            rows += '<div class="box"><b>%d. %s</b><div class="row">%s</div></div>' % (
                i + 1, E(_t(lang, pt, en)), "".join(
                    '<label style="margin:2px 8px 2px 0"><input type="radio" name="q%d" value="%d" required> %s</label>' % (i, v, E(_t(lang, a, b2)))
                    for v, (a, b2) in enumerate(ANS)))
        return ('<form method="get" action="/finance/period"><input type="hidden" name="tab" value="care"><input type="hidden" name="t" value="%s">'
                '<h3>%s</h3><p class="mut">%s</p>%s<button>%s</button></form>' % (
                    tid, title, _t(lang, "Responde pensando nos últimos 3 meses.", "Answer thinking of the last 3 months."), rows, _t(lang, "Ver resultado", "See result")))
    cards = "".join(
        '<a class="card" style="text-decoration:none;color:inherit" href="/finance/period?tab=care&t=%s"><span style="font-size:1.8em">%s</span><b>%s</b>'
        '<span class="mut">%s</span></a>' % (k, v[0], E(_t(lang, v[1], v[2])), _t(lang, "%d perguntas · 1 min", "%d questions · 1 min") % len(v[3]))
        for k, v in TESTS.items())
    tips = [("💧", "Bebe água ao longo do dia", "Drink water through the day"), ("🚶", "10 minutos de caminhada alivia cólicas e humor", "A 10-minute walk eases cramps and mood"),
            ("🧘", "Respira fundo 4-6 vezes quando estiveres tensa", "Take 4-6 deep breaths when tense"), ("🌙", "Deita-te à mesma hora esta semana", "Go to bed at the same time this week")]
    t = tips[datetime.date.today().toordinal() % len(tips)]
    return ('<h3>%s</h3><div class="box"><b>%s %s</b></div><div class="cards">%s</div><p class="aviso">%s</p>' % (
        _t(lang, "Autoavaliações", "Self-checks"), t[0], E(_t(lang, t[1], t[2])), cards,
        _t(lang, "As respostas não são guardadas. Não substituem o médico.", "Answers are not saved. They do not replace your doctor.")))


ADV_EN = {"sop": ("Few PCOS-related signs. Keep logging your cycle.", "Some signs that can have many causes. If they persist, talk to your doctor.",
                  "Several signs together justify a visit (gynecology or endocrinology). Bring your Cycle history."),
          "cansaco": ("Fatigue level as expected. Keep up sleep and hydration.", "Moderate fatigue. Check sleep, iron-rich food and stress. If it lasts weeks, ask for blood tests.",
                      "High fatigue, especially with dizziness or breathlessness. Book a visit to check iron, thyroid and vitamins."),
          "tpm": ("Mild symptoms. Movement, sleep and less caffeine usually suffice.", "Moderate PMS. Log symptoms in Cycle, cut salt and alcohol, and move regularly.",
                  "Strong symptoms that disrupt daily life. Talk to a doctor: effective treatment exists, including for the severe form (PMDD)."),
          "sono": ("Your sleep habits are good.", "Room to improve: fixed schedule, cool dark room, screens off 1 hour before.",
                   "Poor sleep. Apply sleep hygiene for 2 weeks; if no improvement, talk to a doctor.")}


def _en_adv(tid, b):
    return ADV_EN[tid][b]


# ---- Ask Clover: chat de IA sobre o ciclo (historico fica so no browser)
import json, re
def ask_system(info, ph, today, recent, lang, prof=""):
    key, day = ph
    fase = {"menstrual": "menstrual", "folicular": "follicular", "ovulatoria": "ovulatory", "lutea": "luteal"}.get(key, "unknown (no period logged yet)")
    ctx = "Current phase: %s%s. Typical cycle length: %s days; period length: %s days." % (
        fase, (", cycle day %s" % day) if day else "", info.get("cycle"), info.get("period"))
    if recent: ctx += " Recently logged symptoms: %s." % ", ".join(recent)
    if prof: ctx += " Health profile given by the user (self-reported, use it to personalise and to spot combinations worth a doctor visit): " + prof + "."
    return ("You are Pingo, a friendly penguin mascot and a warm, friendly and knowledgeable women's cycle-health companion inside a cycle tracker. "
            "Answer questions about the menstrual cycle, symptoms, PMS, PCOS, ovulation, fertility awareness, nutrition, sleep, exercise and mood. "
            "Be practical, kind and concise (under 150 words unless asked for detail); simple lists are fine, no markdown headings. "
            "You are NOT a doctor: never diagnose, never give medication doses, and never present this as contraception. "
            "For red flags (very heavy bleeding, severe pain, fainting, fever, pregnancy possibility with pain, bleeding after menopause, symptoms lasting months) "
            "clearly advise seeing a doctor. Politely decline topics unrelated to health and wellbeing. "
            "Reply in " + ("English" if lang == "en" else "European Portuguese") + ". User context (use it only when relevant): " + ctx)

def ask(system, history, question):
    import study
    msgs = [m for m in history if isinstance(m, dict) and m.get("r") in ("u", "a")][-8:]
    convo = "\n".join(("User: " if m["r"] == "u" else "Pingo: ") + str(m.get("t", ""))[:800] for m in msgs)
    q = (convo + "\n" if convo else "") + "User: " + question[:800] + "\nPingo:"
    out = study.ai(system, q)
    out = re.sub(r"<think>.*?</think>", "", out, flags=re.S).strip()
    return out[:2500]

def ask_page(lang, has_profile=False):
    import period_pg as PG
    pt = lang != "en"
    hello = "Olá! Sou o Pingo 🐧 Pergunta-me o que quiseres sobre o teu ciclo, sintomas, TPM, ovulação, alimentação ou sono." if pt else "Hi! I'm Pingo 🐧 Ask me anything about your cycle, symptoms, PMS, ovulation, nutrition or sleep."
    chips = (["Porque tenho cólicas?", "O que comer na fase lútea?", "Como sei que ovulei?", "Dicas para TPM"] if pt else
             ["Why do I get cramps?", "What to eat in the luteal phase?", "How do I know I ovulated?", "PMS tips"])
    if not has_profile:
        hello += " Preenche o separador 📝 O meu perfil para eu te conhecer melhor." if pt else " Fill in the 📝 My profile tab so I can get to know you."
    ph = "Escreve a tua pergunta…" if pt else "Type your question…"
    send = "Enviar" if pt else "Send"
    err = "Não consegui responder agora. Tenta outra vez." if pt else "I couldn't answer right now. Please try again."
    avis = "O Pingo não é médico e não faz diagnósticos. As respostas são informativas. A tua fase, sintomas recentes e o resumo do teu perfil são partilhados com a IA para personalizar; nada mais." if pt else "Pingo is not a doctor and does not diagnose. Answers are informational. Your phase, recent symptoms and profile summary are shared with the AI to personalise replies; nothing else."
    return ("""<style>#ck{display:flex;flex-direction:column;gap:8px;margin:8px 0;max-height:55vh;overflow:auto}
#ck div{padding:9px 12px;border-radius:14px;max-width:88%%;white-space:pre-wrap;line-height:1.4}
#ck .a{background:#2d2a45;align-self:flex-start}#ck .u{background:#2f8fbf;color:#fff;align-self:flex-end}
.cy .th-claro #ck .a,.th-claro #ck .a{background:#eee;color:#222}
#cf{display:flex;gap:6px}#cf input{flex:1;padding:10px;border-radius:10px;border:1px solid #555;background:transparent;color:inherit;font-size:16px}
#cf button{padding:10px 16px;border-radius:10px;border:0;background:#2f8fbf;color:#fff}</style>
<div class="pgask"><span id="pgm">%s</span><h3>%s</h3></div><div id="ck"><div class="a">%s</div></div>
<div class="row">%s</div>
<form id="cf"><input id="ci" maxlength="800" placeholder="%s" autocomplete="off"><button>%s</button></form>
<p class="aviso">%s</p>
<script>(function(){var T=%s,pgm=document.getElementById('pgm');function ps(k){if(pgm)pgm.innerHTML=T[k]}
var H=[],ck=document.getElementById('ck'),ci=document.getElementById('ci'),busy=0;
function add(c,t){var d=document.createElement('div');d.className=c;d.textContent=t;ck.appendChild(d);ck.scrollTop=ck.scrollHeight;return d}
async function go(q){q=(q||'').trim();if(!q||busy)return;busy=1;ci.value='';add('u',q);var w=add('a','…');ps('think');
try{var r=await fetch('/finance/period/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({q:q,h:H})});var j=await r.json();
if(j.a){w.textContent=j.a;ps('talk');setTimeout(function(){ps('hello')},4500);H.push({r:'u',t:q},{r:'a',t:j.a})}else{w.textContent=j.error||%s;ps('sad')}}catch(e){w.textContent=%s;ps('sad')}busy=0}
document.getElementById('cf').onsubmit=function(e){e.preventDefault();go(ci.value)};
document.querySelectorAll('.chip').forEach(function(b){b.onclick=function(){go(b.textContent)}})})()</script>""" % (
        PG.pg("hello", 150), E("Pergunta ao Pingo" if pt else "Ask Pingo"), E(hello) if True else "", "".join('<a class="lnk chip" href="javascript:void 0">%s</a>' % E(c) for c in chips), E(ph), E(send), E(avis), json.dumps({k: PG.pg(k, 150) for k in ('hello', 'think', 'talk', 'sad')}), json.dumps(err), json.dumps(err)))
