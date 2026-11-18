"""Aba Ciclo - tema Pinguim: mascote (Pingo), questionario de perfil de saude e importacao de dados."""
import csv, html, io, json, re
E = html.escape

# (id, tipo, pt, en, [(valor, pt, en)])
Q = [
 ("age", "one", "Qual é a tua idade?", "How old are you?", [("<18", "Menos de 18", "Under 18"), ("18-24", "18-24", "18-24"), ("25-34", "25-34", "25-34"), ("35-44", "35-44", "35-44"), ("45-54", "45-54", "45-54"), ("55+", "55 ou mais", "55 or more")]),
 ("menarche", "one", "Com que idade teve a primeira menstruação?", "How old were you at your first period?", [("<11", "Antes dos 11", "Before 11"), ("11-13", "11-13", "11-13"), ("14-15", "14-15", "14-15"), ("16+", "16 ou mais", "16 or more"), ("not_yet", "Ainda não", "Not yet"), ("dk", "Não me lembro", "I don't remember")]),
 ("regular", "one", "O teu ciclo é regular?", "Is your cycle regular?", [("regular", "Regular (21-35 dias)", "Regular (21-35 days)"), ("irregular", "Irregular", "Irregular"), ("very", "Muito irregular ou ausente", "Very irregular or absent"), ("dk", "Não sei", "Not sure")]),
 ("flow", "one", "Como é o teu fluxo habitual?", "How heavy is your usual flow?", [("light", "Leve", "Light"), ("normal", "Normal", "Normal"), ("heavy", "Intenso (troco o penso/tampão de hora a hora)", "Heavy (soaking a pad/tampon every hour)"), ("dk", "Não sei", "Not sure")]),
 ("clots", "one", "Tens coágulos no período?", "Do you pass blood clots?", [("no", "Não", "No"), ("small", "Pequenos", "Small"), ("large", "Grandes (maiores que uma moeda)", "Large (bigger than a coin)")]),
 ("pain", "one", "Como é a dor menstrual?", "How is your period pain?", [("none", "Sem dor", "None"), ("mild", "Ligeira", "Mild"), ("moderate", "Moderada", "Moderate"), ("severe", "Forte (atrapalha o dia a dia)", "Severe (disrupts daily life)")]),
 ("pms", "one", "E os sintomas de TPM?", "And PMS symptoms?", [("none", "Nenhuns", "None"), ("mild", "Ligeiros", "Mild"), ("moderate", "Moderados", "Moderate"), ("severe", "Fortes", "Severe")]),
 ("status", "one", "Qual é a tua situação atual?", "What is your current situation?", [("none", "Nenhuma em especial", "Nothing in particular"), ("trying", "A tentar engravidar", "Trying to conceive"), ("pregnant", "Grávida", "Pregnant"), ("postpartum", "Pós-parto", "Postpartum"), ("breastfeeding", "A amamentar", "Breastfeeding"), ("perimenopause", "Perimenopausa", "Perimenopause"), ("menopause", "Menopausa", "Menopause")]),
 ("contra", "one", "Usas contracetivo?", "Do you use contraception?", [("none", "Não", "No"), ("pill", "Pílula", "The pill"), ("iud_h", "DIU hormonal", "Hormonal IUD"), ("iud_c", "DIU de cobre", "Copper IUD"), ("implant", "Implante", "Implant"), ("injection", "Injeção", "Injection"), ("patch_ring", "Adesivo ou anel", "Patch or ring"), ("condom", "Preservativo", "Condoms"), ("natural", "Métodos naturais", "Natural methods"), ("other", "Outro", "Other")]),
 ("cond", "many", "Tens algum destes diagnósticos? (podes escolher vários)", "Do you have any of these diagnoses? (pick any)", [("pcos", "SOP (ovário poliquístico)", "PCOS"), ("endo", "Endometriose", "Endometriosis"), ("fibroids", "Miomas", "Fibroids"), ("thyroid", "Problemas de tiroide", "Thyroid disorder"), ("anemia", "Anemia", "Anemia"), ("diabetes", "Diabetes", "Diabetes"), ("migraine", "Enxaquecas", "Migraines"), ("mental", "Ansiedade ou depressão", "Anxiety or depression"), ("ibs", "Intestino irritável", "IBS"), ("hbp", "Hipertensão", "High blood pressure"), ("eating", "Perturbação alimentar (atual ou passada)", "Eating disorder (current or past)")]),
 ("main", "many", "O que mais te incomoda?", "What bothers you most?", [("cramps", "Cólicas", "Cramps"), ("bleeding", "Fluxo intenso", "Heavy bleeding"), ("mood", "Alterações de humor", "Mood swings"), ("fatigue", "Cansaço", "Fatigue"), ("acne", "Acne", "Acne"), ("bloating", "Inchaço", "Bloating"), ("headache", "Dores de cabeça", "Headaches"), ("hair", "Queda de cabelo ou pelos a mais", "Hair loss or excess hair"), ("sleep", "Dormir mal", "Poor sleep"), ("libido", "Pouca libido", "Low sex drive")]),
 ("sleep", "one", "Quantas horas dormes por noite?", "How many hours do you sleep?", [("<5", "Menos de 5", "Under 5"), ("5-6", "5-6", "5-6"), ("7-8", "7-8", "7-8"), ("9+", "9 ou mais", "9 or more")]),
 ("exercise", "one", "Quantas vezes fazes exercício por semana?", "How often do you exercise per week?", [("0", "Nunca", "Never"), ("1-2", "1-2 vezes", "1-2 times"), ("3-4", "3-4 vezes", "3-4 times"), ("5+", "5 ou mais", "5 or more")]),
 ("diet", "one", "Como é a tua alimentação?", "What is your diet like?", [("omni", "De tudo", "Omnivore"), ("veg", "Vegetariana", "Vegetarian"), ("vegan", "Vegana", "Vegan"), ("restricted", "Com restrições (intolerâncias, dieta)", "Restricted (intolerances, dieting)")]),
 ("stress", "one", "Como está o teu nível de stress?", "How is your stress level?", [("low", "Baixo", "Low"), ("mid", "Médio", "Medium"), ("high", "Alto", "High")]),
 ("smoke", "one", "Fumas ou bebes álcool?", "Do you smoke or drink alcohol?", [("none", "Nem uma coisa nem outra", "Neither"), ("alcohol", "Álcool ocasional", "Occasional alcohol"), ("smoke", "Fumo", "I smoke")]),
 ("goals", "many", "O que queres do Pingo? (podes escolher vários)", "What do you want from Pingo? (pick any)", [("understand", "Perceber o meu ciclo", "Understand my cycle"), ("pain", "Reduzir a dor", "Reduce pain"), ("conceive", "Engravidar", "Conceive"), ("pcos", "Gerir o SOP", "Manage PCOS"), ("mood", "Humor e energia", "Mood and energy"), ("sleep", "Dormir melhor", "Sleep better"), ("food", "Alimentação", "Nutrition")]),
 ("style", "one", "Como preferes as respostas?", "How do you like answers?", [("short", "Curtas e diretas", "Short and direct"), ("detail", "Mais detalhadas", "More detailed")]),
]
TEXTS = [("meds", "Medicamentos ou suplementos que tomas (opcional)", "Medication or supplements you take (optional)"),
         ("other", "Alergias ou algo mais que o Pingo deva saber (opcional)", "Allergies or anything else Pingo should know (optional)")]
QID = {q[0]: q for q in Q}


def _t(lang, pt, en):
    return en if lang == "en" else pt


def clean_text(s):
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s.,;:()/%+\-ºª'áàâãéêíóôõúçÁÀÂÃÉÊÍÓÔÕÚÇ]", "", str(s or ""))).strip()[:120]


def parse_profile(f):
    out = {}
    for qid, typ, _p, _e, opts in Q:
        if typ == "one":
            v = f.get("q_" + qid, "")
            if v in [o[0] for o in opts]:
                out[qid] = v
        else:
            sel = [o[0] for i, o in enumerate(opts) if f.get("q_%s_%d" % (qid, i)) == "1"]
            if sel:
                out[qid] = sel
    for k, _p, _e in TEXTS:
        v = clean_text(f.get("t_" + k, ""))
        if v:
            out[k] = v
    return out


def pct(profile):
    n = sum(1 for q in Q if profile.get(q[0]))
    return n * 100 // len(Q)


def profile_text(profile):
    """Resumo em ingles para o prompt da IA (so rotulos conhecidos + texto limpo)."""
    parts = []
    for qid, typ, _p, en, opts in Q:
        v = profile.get(qid)
        if not v:
            continue
        lab = {o[0]: o[2] for o in opts}
        vals = ", ".join(lab.get(x, "") for x in (v if isinstance(v, list) else [v]) if x in lab)
        if vals:
            parts.append("%s %s" % (en.rstrip("?"), vals))
    for k, _p, en in TEXTS:
        if profile.get(k):
            parts.append("%s: %s" % (en.split(" (")[0], clean_text(profile[k])))
    return "; ".join(parts)


STATES = ("idle", "hello", "think", "talk", "happy", "sleep", "sad", "cramps", "period", "ovulation", "pill", "read", "selfcare", "quiz", "warning", "celebrate", "loading")


LAYERED = {'hello': (351, 368, (14.5, 57.1), (85.5, 56.0)), 'happy': (347, 358, (17.6, 46.0), (85.3, 39.2)), 'sad': (329, 361, (13.7, 58.1), (79.6, 58.1)), 'selfcare': (337, 364, (25.8, 66.4), (76.0, 54.3)), 'quiz': (334, 364, (15.9, 64.7), (77.8, 51.6)), 'read': (270, 360, (33.0, 61.5), (68.1, 62.4)), 'ovulation': (391, 361, (38.6, 68.0), (61.4, 68.8)), 'warning': (265, 364, (29.1, 60.5), (70.9, 59.7)), 'celebrate': (453, 397, (25.4, 43.3), (76.6, 43.2)), 'loading': (412, 353, (46.5, 48.2), (50, 50)), 'cramps': (269, 361, (41.6, 62.3), (59.1, 64.3)), 'period': (404, 361, (39.4, 63.2), (58.7, 63.1)), 'pill': (272, 361, (36.8, 62.4), (69.9, 62.0)), 'sleep': (379, 401, (13.5, 58.1), (76.0, 57.6)), 'talk': (383, 368, (17.5, 53.6), (80.4, 52.3)), 'think': (301, 371, (47.8, 47.4), (84.7, 54.0))}
# ordem de baixo para cima; (ficheiro, classe CSS)
LAYER_ORDER = {
    "talk": [("corpo", "b"), ("extra_boca_fechada", "mc"), ("extra_boca_aberta", "mo"), ("extra_notas", "nt"), ("asa_esq", "wl"), ("asa_dir", "wr"), ("olhos", "e")],
    "think": [("corpo", "b"), ("extra", "bl"), ("asa_esq", "wl"), ("asa_dir", "wr"), ("olhos", "e")],
    "sleep": [("corpo", "b"), ("extra", "zz"), ("asa_esq", "wl"), ("asa_dir", "wr"), ("olhos", "es")],
    "cramps": [("corpo", "b"), ("extra", "bt"), ("asa_esq", "wl"), ("asa_dir", "wr"), ("olhos", "e")],
    "pill": [("corpo", "b"), ("extra", "pl"), ("extra_copo", "cp"), ("asa_esq", "wl"), ("asa_dir", "wr"), ("olhos", "e")],
    "hello": [('corpo', 'b'), ('asa_esq', 'wl'), ('asa_dir', 'wr'), ('olhos', 'e')],
    "happy": [('corpo', 'b'), ('asa_esq', 'wl'), ('asa_dir', 'wr'), ('olhos', 'e')],
    "sad": [('corpo', 'b'), ('extra', 'tr'), ('asa_esq', 'wl'), ('asa_dir', 'wr'), ('olhos', 'e')],
    "selfcare": [('corpo', 'b'), ('extra_vapor', 'vp'), ('extra', 'ex'), ('asa_esq', 'wl'), ('asa_dir', 'wr'), ('extra_coracao', 'hr'), ('olhos', 'e')],
    "quiz": [('corpo', 'b'), ('extra', 'ex'), ('asa_esq', 'wl'), ('asa_dir', 'wr'), ('extra_lupa', 'lp'), ('olhos', 'e')],
    "read": [('corpo', 'b'), ('extra', 'ex'), ('asa_esq', 'wl'), ('asa_dir', 'wr'), ('olhos', 'e')],
    "ovulation": [('corpo', 'b'), ('extra_flor', 'ex'), ('extra', 'sp'), ('asa_esq', 'wl'), ('asa_dir', 'wr'), ('olhos', 'e')],
    "warning": [('corpo', 'b'), ('extra', 'wn'), ('asa_esq', 'wl'), ('asa_dir', 'wr'), ('olhos', 'e')],
    "celebrate": [('corpo', 'b'), ('extra', 'cf'), ('asa_esq', 'wl'), ('asa_dir', 'wr'), ('olhos', 'e')],
    "loading": [('extra_gelo', 'gl'), ('corpo', 'b'), ('extra', 'sl'), ('asa', 'wl'), ('olhos', 'e')],
    "period": [("extra_botija", "bt"), ("extra_almofada", "al"), ("corpo", "b"), ("extra", "dr"), ("asa_esq", "wl"), ("asa_dir", "wr"), ("olhos", "e")],
}


def _layered(state, size):
    W, H, pl, pr = LAYERED[state]
    imgs = "".join('<img class="l-%s" src="/finance/pingo/layers/%s_%s.png" alt="" draggable="false">' % (c, state, f) for f, c in LAYER_ORDER[state])
    return ('<span class="pg pgL pgL-%s" style="--ph:%dpx;--ar:%d/%d;--wl:%s%% %s%%;--wr:%s%% %s%%"><span class="pgls">%s</span>%s</span>'
            % (state, size, W, H, pl[0], pl[1], pr[0], pr[1], imgs, '<span class="pgspin"></span>' if state == "loading" else ""))


def pg(state, size=64):
    """Mascote Pingo: arte do Gemini (PNG) + animacao CSS por estado. size = altura em px."""
    if state not in STATES:
        state = "idle"
    if state in LAYERED:
        return _layered(state, size)
    bub = '<span class="pgbub"><i></i><i></i><i></i></span>' if state == "think" else ""
    if state == "idle":
        L = "/finance/pingo/layers/"
        return ('<span class="pg pg-idle pgl" style="--ph:%dpx"><span class="pgls">'
                '<img class="pl-b" src="%sbody.png" alt="" draggable="false">'
                '<img class="pl-wl" src="%swing_l.png" alt="" draggable="false">'
                '<img class="pl-wr" src="%swing_r.png" alt="" draggable="false">'
                '<img class="pl-e" src="%seyes.png" alt="" draggable="false"></span></span>') % (size, L, L, L, L)
    return '<span class="pg pg-%s" style="--ph:%dpx"><img src="/finance/pingo/%s.png" alt="" draggable="false">%s</span>' % (state, size, state, bub)


PG_CSS = """<style>
.pg{position:relative;display:inline-block;transform-origin:50% 100%;line-height:0;flex:none}
.pg img{display:block;height:var(--ph,72px);width:auto;filter:drop-shadow(0 6px 8px #0004);user-select:none;-webkit-user-drag:none}
.pgbub{position:absolute;right:-8%;top:0;width:22%;min-width:30px;aspect-ratio:7/5;border:3px solid #8e9cc9;border-radius:50%;background:#f3f6ff;display:flex;gap:3px;align-items:center;justify-content:center;animation:pgbu 4s ease-in-out infinite}
.pgbub i{width:5px;height:5px;border-radius:50%;background:#8e9cc9;display:block}
@keyframes pgbu{0%,100%{transform:translateY(0)}50%{transform:translateY(-4px)}}
.pgl{display:inline-block;height:var(--ph);aspect-ratio:339/368;animation:none!important}.pgls{position:relative;display:block;width:100%;height:100%;transform-origin:50% 100%;animation:pgbreath 2s ease-in-out infinite}
.pgl .pgls img{position:absolute;left:0;top:0;width:100%;height:100%;height:var(--ph);max-width:none}
.pgl .pl-wl{transform-origin:17.7% 51%;animation:plwl 2s ease-in-out infinite}.pl-wr{transform-origin:82.3% 51%;animation:plwr 2s ease-in-out infinite}
.pl-e{transform-origin:50% 27%;animation:plblink 4s infinite}
@keyframes plwl{0%,100%{transform:rotate(0)}50%{transform:rotate(-9deg)}}@keyframes plwr{0%,100%{transform:rotate(0)}50%{transform:rotate(9deg)}}
@keyframes plblink{0%,92%,100%{transform:scaleY(1)}95%{transform:scaleY(.08)}}
@media(prefers-reduced-motion:reduce){.pgls,.pl-wl,.pl-wr,.pl-e{animation:none!important}}
.pgL{display:inline-block;height:var(--ph);aspect-ratio:var(--ar);animation:none!important}.pgL .pgls{position:relative;display:block;width:100%;height:100%;transform-origin:50% 100%;animation:pgbreath 2.4s ease-in-out infinite}
.pgL .pgls img{position:absolute;left:0;top:0;width:100%;height:100%;max-width:none;filter:none}
.pgL{filter:drop-shadow(0 6px 8px #0004)}
.pgL .l-wl{transform-origin:var(--wl);animation:plwl 2.4s ease-in-out infinite}.pgL .l-wr{transform-origin:var(--wr);animation:plwr 2.4s ease-in-out infinite}
.pgL .l-e{transform-origin:50% 30%;animation:plblink 4s infinite}
.pgL .l-mc{animation:plmc 1.2s steps(1) infinite}.pgL .l-mo{animation:plmo 1.2s steps(1) infinite}
@keyframes plmc{0%,50%{opacity:1}50.01%,100%{opacity:0}}@keyframes plmo{0%,50%{opacity:0}50.01%,100%{opacity:1}}
.pgL .l-nt,.pgL .l-zz,.pgL .l-bl,.pgL .l-dr,.pgL .l-pl{animation:plfloat 3s ease-in-out infinite}
.pgL .l-zz{animation-duration:4s}.pgL .l-dr{animation:pldrip 2.4s ease-in infinite}
.pgL .l-bt{animation:plpulse 1.6s ease-in-out infinite;transform-origin:50% 60%}
.pgL-cramps .pgls{animation:plshake 2.4s ease-in-out infinite}
.pgL-sleep .pgls{animation:pgbreath 4s ease-in-out infinite}.pgL-sleep .l-wl,.pgL-sleep .l-wr{animation-duration:4s}
.pgL .l-vp{animation:plfloat 3s ease-in-out infinite}.pgL .l-hr{transform-origin:50% 50%;animation:plpulse 1.4s ease-in-out infinite}
.pgL .l-tr{animation:pldrip 2.8s ease-in infinite}.pgL .l-lp{animation:plfloat 2.6s ease-in-out infinite}
.pgL .l-sp{animation:pltwk 1.6s ease-in-out infinite}.pgL .l-wn{transform-origin:50% 90%;animation:plpulse .9s ease-in-out infinite}
.pgL .l-cf{animation:plconf 2.4s ease-in-out infinite}.pgL .l-sl{animation:plslide 1s ease-in-out infinite}
.pgL-celebrate .pgls,.pgL-happy .pgls{animation:plhop 1.2s ease-in-out infinite}
.pgspin{position:absolute;right:2%;top:4%;width:22%;aspect-ratio:1;border:max(3px,.035*var(--ph)) solid #8e9cc944;border-top-color:#8ec5ff;border-radius:50%;animation:plspin .9s linear infinite}@keyframes plspin{to{transform:rotate(360deg)}}@media(prefers-reduced-motion:reduce){.pgspin{animation:none}}
.pgL-loading .pgls{animation:plslide 2s ease-in-out infinite}.pgL-loading .l-wl{animation:plwl 1s ease-in-out infinite}
.pgL-hello .l-wr{animation:plwave .9s ease-in-out infinite}.pgL-sad .pgls{animation:pgbreath 4s ease-in-out infinite}
@keyframes pltwk{0%,100%{opacity:.35;transform:scale(.96)}50%{opacity:1;transform:scale(1.03)}}
@keyframes plconf{0%,100%{transform:translateY(-2%)}50%{transform:translateY(3%)}}
@keyframes plslide{0%,100%{transform:translateX(-2%)}50%{transform:translateX(2%)}}
@keyframes plhop{0%,100%{transform:translateY(0)}40%{transform:translateY(-6%)}}
@keyframes plwave{0%,100%{transform:rotate(0)}50%{transform:rotate(-14deg)}}
@keyframes plfloat{0%,100%{transform:translateY(0)}50%{transform:translateY(-4%)}}
@keyframes pldrip{0%{transform:translateY(-3%);opacity:.2}30%{opacity:1}100%{transform:translateY(8%);opacity:0}}
@keyframes plpulse{0%,100%{transform:scale(1)}50%{transform:scale(1.05)}}
@keyframes plshake{0%,100%{transform:translateX(0)}25%{transform:translateX(-1.2%)}75%{transform:translateX(1.2%)}}
@media(prefers-reduced-motion:reduce){.pgL *{animation:none!important}.pgL .l-mo{opacity:0}}
.pg-idle{animation:pgbreath 2s ease-in-out infinite}.pg-sleep{animation:pgslow 4s ease-in-out infinite}
.pg-sad{animation:pgdroop 4s ease-in-out infinite}.pg-hello{animation:pgwave 2s ease-in-out infinite}
.pg-think{animation:pgthink 4s ease-in-out infinite}.pg-talk{animation:pgtalk 1.33s ease-in-out infinite}
.pg-happy{animation:pghop 1.33s cubic-bezier(.3,0,.4,1) infinite}.pg-cramps{animation:pgtrem 4s linear infinite}
.pg-period,.pg-selfcare{animation:pgsway 4s ease-in-out infinite}.pg-ovulation{animation:pgglow 2s ease-in-out infinite}
.pg-pill{animation:pgnod 4s ease-in-out infinite}.pg-read{animation:pgread 4s ease-in-out infinite}
.pg-quiz{animation:pgtilt 4s ease-in-out infinite}.pg-warning{animation:pgalert 4s ease-in-out infinite}
.pg-celebrate{animation:pgparty 2s ease-in-out infinite}.pg-loading{animation:pgrock 2s ease-in-out infinite}
@keyframes pgbreath{0%,100%{transform:scale(1,1)}50%{transform:scale(1.015,1.03)}}
@keyframes pgslow{0%,100%{transform:scale(1,1) rotate(-.8deg)}50%{transform:scale(1.025,1.045) rotate(.8deg)}}
@keyframes pgdroop{0%,100%{transform:scale(1,1) translateY(0)}50%{transform:scale(1.01,.965) translateY(2px)}}
@keyframes pgwave{0%,100%{transform:rotate(0)}25%{transform:rotate(-2.5deg)}75%{transform:rotate(2.5deg)}}
@keyframes pgthink{0%,100%{transform:rotate(0)}30%,60%{transform:rotate(-3deg)}}
@keyframes pgtalk{0%,100%{transform:translateY(0) rotate(0)}25%{transform:translateY(-3px) rotate(1.5deg)}75%{transform:translateY(-1px) rotate(-1.5deg)}}
@keyframes pghop{0%,100%{transform:translateY(0) scale(1.03,.96)}45%{transform:translateY(-12px) scale(.98,1.03)}}
@keyframes pgtrem{0%,100%{transform:translate(0,0)}10%{transform:translate(-1.2px,.5px)}20%{transform:translate(1.2px,-.5px)}30%{transform:translate(-1px,0)}40%{transform:translate(1px,.5px)}50%{transform:translate(0,0)}}
@keyframes pgsway{0%,100%{transform:rotate(-1.5deg) scale(1,1)}50%{transform:rotate(1.5deg) scale(1.01,1.02)}}
@keyframes pgglow{0%,100%{transform:translateY(0);filter:brightness(1)}50%{transform:translateY(-8px);filter:brightness(1.1) saturate(1.1)}}
@keyframes pgnod{0%,35%,100%{transform:rotate(0)}15%{transform:rotate(-4deg) translateY(-3px)}25%{transform:rotate(3deg) translateY(1px)}}
@keyframes pgread{0%,100%{transform:rotate(0)}20%,45%{transform:rotate(1.5deg) translateY(1px)}60%{transform:rotate(3deg) translateY(2px)}80%{transform:rotate(1.5deg) translateY(1px)}}
@keyframes pgtilt{0%,100%{transform:rotate(0) translateY(0)}25%{transform:rotate(-4deg) translateY(-4px)}50%{transform:rotate(0) translateY(0)}75%{transform:rotate(4deg) translateY(-4px)}}
@keyframes pgalert{0%,100%{transform:translateX(0) scale(1)}10%{transform:translateX(-4px) scale(1.03)}20%{transform:translateX(4px) scale(1.03)}30%{transform:translateX(-4px) scale(1.03)}40%{transform:translateX(0) scale(1.02)}55%{transform:translateX(0) scale(1)}}
@keyframes pgparty{0%,100%{transform:translateY(0) rotate(0)}25%{transform:translateY(-10px) rotate(-4deg)}50%{transform:translateY(0) rotate(0)}75%{transform:translateY(-10px) rotate(4deg)}}
@keyframes pgrock{0%,100%{transform:rotate(-3deg)}50%{transform:rotate(3deg)}}
@media (prefers-reduced-motion:reduce){.pg,.pgbub{animation:none!important}}
/* ---- layout maior e mais legivel ---- */
.cy{max-width:none;margin:0;min-height:100vh;padding:14px clamp(14px,4vw,56px) 40px;box-sizing:border-box;background:radial-gradient(1200px 500px at 50% -10%,#24406a33,transparent),#141821}
body:has(.cy){max-width:none!important;padding:0!important;margin:0!important}
body:has(.cy)>h1:first-child{display:none}
.cybar{display:flex;justify-content:space-between;align-items:center;font-size:16px;margin-bottom:6px}
.cybar a{color:#9fc3ff;text-decoration:none;padding:8px 14px;border-radius:20px;background:#ffffff12}
.cy h2{font-size:30px;margin:6px 0 12px}
@media(min-width:900px){.cy>*{max-width:1100px;margin-left:auto;margin-right:auto}}
.pgbox{display:flex;align-items:center;gap:18px;background:linear-gradient(135deg,#123a5e 0%,#2a7fb5 60%,#6cc3ea 100%);border-radius:22px;padding:16px 20px;margin:12px 0;color:#fff;box-shadow:0 8px 24px #0004;position:relative;overflow:hidden}
.pgbox:after{content:"";position:absolute;right:-30px;top:-30px;width:140px;height:140px;border-radius:50%;background:#ffffff14}
.pgbox p{margin:0;font-size:19px;line-height:1.45;font-weight:500;text-shadow:0 1px 2px #0003;position:relative;z-index:1}
.pgbox .pgm{flex:none}
.pgbox>div{position:relative;z-index:1}
.cy.pal-gelo .hero{background:linear-gradient(135deg,#0f3a5f,#4fb3e0)!important}
.pgq{display:none}.pgq.on{display:block}.pgq h3{font-size:22px;line-height:1.3;margin:14px 0 10px}
.pgbar{height:12px;background:#2a2e36;border-radius:8px;overflow:hidden;margin:10px 0}
.pgbar i{display:block;height:100%;background:linear-gradient(90deg,#4fb3e0,#9be1ff);border-radius:8px;transition:width .3s}
.pgopt{display:block;padding:15px 16px;margin:9px 0;border:2px solid #455;border-radius:16px;cursor:pointer;font-size:18px;line-height:1.3;background:#ffffff08}
.pgopt:has(input:checked){border-color:#4fb3e0;background:#4fb3e033}.pgopt input{margin-right:12px;transform:scale(1.35)}
.pgq input[type=text]{font-size:18px!important;padding:14px!important;border-radius:14px;border:2px solid #455;background:transparent;color:inherit}
.pgnav{display:flex;gap:10px;margin-top:16px}.pgnav button{flex:1;padding:16px;border-radius:16px;border:0;background:#2f8fbf;color:#fff;font-size:19px;font-weight:600}
.cy #ck{font-size:18px;line-height:1.5;max-height:55vh}
.cy #ck .a,.cy #ck .u{font-size:18px;padding:12px 15px;border-radius:18px}
#cf input{font-size:18px;padding:14px;border-radius:14px}#cf button{font-size:18px;padding:14px 20px;border-radius:14px}
.cy .chip{font-size:16px;padding:10px 14px}
.pgask{display:flex;align-items:flex-end;gap:14px;margin:6px 0 10px}.pgask h3{font-size:24px;margin:0}
</style>"""


def mascot_bar(state, pt, en, lang, extra=""):
    return '<div class="pgbox"><span class="pgm">%s</span><div><p>%s</p>%s</div></div>' % (pg(state, 130), E(_t(lang, pt, en)), extra)


def profile_page(profile, lang, msg=""):
    L = lambda a, b: _t(lang, a, b)
    qs = []
    for i, (qid, typ, p, e, opts) in enumerate(Q):
        cur = profile.get(qid)
        o = ""
        for j, (v, pt, en) in enumerate(opts):
            if typ == "one":
                o += '<label class="pgopt"><input type="radio" name="q_%s" value="%s"%s>%s</label>' % (qid, E(v), " checked" if cur == v else "", E(L(pt, en)))
            else:
                o += '<label class="pgopt"><input type="checkbox" name="q_%s_%d" value="1"%s>%s</label>' % (qid, j, " checked" if cur and v in cur else "", E(L(pt, en)))
        qs.append('<div class="pgq on" data-i="%d"><h3>%s</h3>%s</div>' % (i, E(L(p, e)), o))
    for k, p, e in TEXTS:
        qs.append('<div class="pgq on" data-i="%d"><h3>%s</h3><input type="text" name="t_%s" maxlength="120" value="%s" style="width:100%%;padding:10px;font-size:16px"></div>' % (len(qs), E(L(p, e)), k, E(profile.get(k, ""))))
    n = len(qs)
    done = pct(profile)
    top = mascot_bar("hello", "Olá! Sou o Pingo 🐧 Responde ao que quiseres: quanto mais souber, mais personalizadas ficam as minhas respostas. Podes saltar perguntas e mudar tudo mais tarde.",
                     "Hi! I'm Pingo 🐧 Answer whatever you like: the more I know, the more personal my answers. You can skip questions and change anything later.", lang)
    js = """<script>(function(){var Q=__Q__;var qs=[].slice.call(document.querySelectorAll('.pgq')),i=0,b=document.getElementById('pgb'),nx=document.getElementById('pgn'),pv=document.getElementById('pgp'),sv=document.getElementById('pgs'),c=document.getElementById('pgc');
function show(){qs.forEach(function(q,k){q.className='pgq'+(k==i?' on':'')});b.style.width=((i+1)*100/qs.length)+'%';c.textContent=(i+1)+' / '+qs.length;pv.style.visibility=i?'visible':'hidden';nx.style.display=i<qs.length-1?'':'none';sv.style.display=i<qs.length-1?'none':'';var m=document.querySelector('.pgbox .pgm');if(m)m.innerHTML=Q[i==0?'hello':(i==qs.length-1?'happy':'quiz')]}
nx.onclick=function(){if(i<qs.length-1){i++;show()}};pv.onclick=function(){if(i>0){i--;show()}};show()})()</script>"""
    return (PG_CSS + top + ('<p class="green">%s</p>' % E(msg) if msg else "")
            + '<div class="mut">%s %d%%</div>' % (E(L("Perfil preenchido:", "Profile completed:")), done)
            + '<form method="post" action="/finance/period/profile" class="box"><div class="pgbar"><i id="pgb"></i></div><div class="mut" id="pgc"></div>'
            + "".join(qs)
            + '<div class="pgnav"><button type="button" id="pgp">%s</button><button type="button" id="pgn">%s</button><button id="pgs">%s</button></div></form>' % (E(L("Anterior", "Back")), E(L("Seguinte", "Next")), E(L("Guardar 🐧", "Save 🐧")))
            + '<form method="post" action="/finance/period/profile" class="box"><input type="hidden" name="clear" value="1"><button style="background:#7a3030">%s</button></form>' % E(L("Apagar o meu perfil de saúde", "Delete my health profile"))
            + '<p class="aviso">%s</p>' % E(L("Estas respostas ficam só na tua conta. Quando perguntas algo ao Pingo, um resumo delas é enviado ao motor de IA para personalizar a resposta, e mais nada. Não substitui o médico.",
                                              "These answers stay in your account. When you ask Pingo something, a summary is sent to the AI engine to personalise the reply, and nothing else. It does not replace a doctor."))
            + js.replace('__Q__', json.dumps({k: pg(k, 120) for k in ('hello', 'quiz', 'happy')})))


# ---- importacao (Clover, outras apps, CSV/JSON)
FLOWMAP = {"spotting": "manchas", "manchas": "manchas", "light": "leve", "leve": "leve", "medium": "média", "média": "média", "media": "média", "normal": "média",
           "moderate": "média", "heavy": "intensa", "intensa": "intensa", "very heavy": "intensa"}
ALIAS = {"date": "date", "data": "date", "day": "date", "dia": "date",
         "flow": "flow", "fluxo": "flow", "bleeding": "flow", "period": "flow", "menstruation": "flow", "menstruacao": "flow",
         "symptoms": "sym", "sintomas": "sym", "symptom": "sym",
         "mood": "moods", "moods": "moods", "humor": "moods", "humores": "moods",
         "discharge": "disch", "corrimento": "disch", "pill": "pill", "pilula": "pill", "pílula": "pill", "contraceptive": "pill",
         "sex": "sx", "sexo": "sx", "relacoes": "sx", "intimacy": "sx",
         "temperature": "temp", "temperatura": "temp", "bbt": "temp", "weight": "weight", "peso": "weight",
         "ovulation_test": "ov", "teste_ovulacao": "ov", "pregnancy_test": "preg", "teste_gravidez": "preg",
         "note": "note", "notes": "note", "nota": "note", "notas": "note",
         "period_start": "start", "start": "start", "start_date": "start", "inicio": "start", "início": "start",
         "period_end": "end", "end": "end", "end_date": "end", "fim": "end"}
TRUE = {"1", "true", "yes", "sim", "y", "x", "s"}
RES = {"positive": "pos", "positivo": "pos", "pos": "pos", "+": "pos", "negative": "neg", "negativo": "neg", "neg": "neg", "-": "neg", "uncertain": "unc", "incerto": "unc", "unc": "unc"}


def _lists():
    import period as P, period_ui as U
    rev = {v.lower(): k for k, v in U.LABEL_EN.items()}
    def mk(lst):
        m = {x.lower(): x for x in lst}
        m.update({k: v for k, v in rev.items() if v in lst})
        return m
    return {"sym": mk(P.SYMPTOMS), "moods": mk(P.MOODS[1:]), "disch": mk(P.DISCH), "pill": mk(P.PILL), "sx": mk(P.SEXO)}


def _items(v):
    if isinstance(v, list):
        return [str(x).strip() for x in v]
    return [x.strip() for x in re.split(r"[;|,]", str(v or "")) if x.strip()]


def _num(v, lo, hi):
    try:
        x = float(str(v).replace(",", "."))
        return round(x, 2) if lo <= x <= hi else None
    except Exception:
        return None


def _day(rec, maps):
    e, extra = {}, []
    for k, v in rec.items():
        a = ALIAS.get(re.sub(r"[\s\-]+", "_", str(k).strip().lower()))
        if a is None or v in (None, "", [], {}):
            continue
        if a == "flow":
            s = str(v).strip().lower()
            e["flow"] = FLOWMAP.get(s) or ("média" if s in TRUE else "")
        elif a in ("sym", "moods", "disch", "pill", "sx"):
            got = []
            for it in _items(v):
                c = maps[a].get(it.lower())
                if c:
                    got.append(c)
                else:
                    extra.append(it[:40])
            if got:
                e[a] = got
        elif a == "temp":
            x = _num(v, 34, 42)
            if x:
                e["temp"] = x
        elif a == "weight":
            x = _num(v, 25, 300)
            if x:
                e["weight"] = x
        elif a in ("ov", "preg"):
            r = RES.get(str(v).strip().lower())
            if r:
                e[a] = r
        elif a == "note":
            e["note"] = str(v).strip()[:300]
    if e.get("moods"):
        e["mood"] = e["moods"][0]
    if e.get("sx"):
        e["sex"] = "prot" if "Sexo com proteção" in e["sx"] and "Sexo sem proteção" not in e["sx"] else "sim"
    if extra:
        e["note"] = (e.get("note", "") + (" · " if e.get("note") else "") + "Import: " + ", ".join(extra))[:300]
    e.setdefault("flow", "")
    e.setdefault("sym", [])
    return e


def parse_import(text):
    """Devolve {iso_date: day}. Aceita o nosso JSON/CSV e formatos genericos (lista de registos, intervalos de periodo)."""
    import datetime
    maps = _lists()
    text = (text or "").strip().lstrip("﻿")
    recs = []
    if text[:1] in "[{":
        j = json.loads(text)
        if isinstance(j, dict) and isinstance(j.get("days"), dict):
            recs = [dict(v, date=k) for k, v in j["days"].items() if isinstance(v, dict)]
        else:
            for k in ("days", "entries", "records", "data", "logs", "cycles", "periods"):
                if isinstance(j, dict) and isinstance(j.get(k), list):
                    j = j[k]
                    break
            if isinstance(j, dict):
                j = [dict(v, date=k) if isinstance(v, dict) else {"date": k} for k, v in j.items()]
            recs = [r for r in j if isinstance(r, dict)]
    else:
        sample = text[:2000]
        try:
            dia = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except Exception:
            dia = csv.excel
        recs = list(csv.DictReader(io.StringIO(text), dialect=dia))
    out = {}
    def iso(s):
        s = str(s or "").strip()[:10]
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y", "%Y/%m/%d", "%d.%m.%Y"):
            try:
                return datetime.datetime.strptime(s, fmt).date()
            except Exception:
                pass
    for r in recs[:20000]:
        nr = {re.sub(r"[\s\-]+", "_", str(k).strip().lower()): v for k, v in r.items()}
        st = nr.get("period_start") or nr.get("start") or nr.get("start_date") or nr.get("inicio") or nr.get("início")
        en = nr.get("period_end") or nr.get("end") or nr.get("end_date") or nr.get("fim")
        if st and iso(st):
            a = iso(st)
            b = iso(en) or a + datetime.timedelta(days=4)
            if 0 <= (b - a).days <= 15:
                for i in range((b - a).days + 1):
                    out.setdefault((a + datetime.timedelta(days=i)).isoformat(), {"flow": "média", "sym": []})
            continue
        dt = iso(nr.get("date") or nr.get("data") or nr.get("day") or nr.get("dia"))
        if not dt or dt > datetime.date.today():
            continue
        e = _day(r, maps)
        if e["flow"] or any(v for k, v in e.items() if k != "flow"):
            out[dt.isoformat()] = e
    return out


def merge(d, new, takes_pill):
    add = upd = 0
    for k, e in new.items():
        if not takes_pill:
            e.pop("pill", None)
        cur = d["days"].get(k)
        if cur is None:
            d["days"][k] = e
            add += 1
        else:
            ch = False
            for kk, vv in e.items():
                if vv and not cur.get(kk):
                    cur[kk] = vv
                    ch = True
            upd += ch
    return add, upd
