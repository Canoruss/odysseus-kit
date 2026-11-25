#!/usr/bin/env python3
"""Gera as ilustrações do tutorial (SVG, estilizadas; sem dados reais de ninguém)."""
import os
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "web", "img")
W, H = 640, 360
def esc(t): return t.replace("&", "&amp;").replace("<", "&lt;")
def frame(title, body, kind="browser"):
    top = f'''<rect x="0" y="0" width="{W}" height="{H}" rx="14" fill="#11151c"/>
<rect x="0" y="0" width="{W}" height="34" rx="14" fill="#1c222d"/><rect x="0" y="20" width="{W}" height="14" fill="#1c222d"/>
<circle cx="20" cy="17" r="5" fill="#ff5f57"/><circle cx="38" cy="17" r="5" fill="#febc2e"/><circle cx="56" cy="17" r="5" fill="#28c840"/>
<text x="{W/2}" y="22" text-anchor="middle" fill="#8b94a5" font-size="12">{esc(title)}</text>'''
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="Segoe UI,Inter,system-ui,sans-serif" font-size="14">{top}{body}</svg>'
def t(x, y, s, fill="#dfe5ef", size=14, w="400", anchor="start", mono=False):
    fam = ' font-family="Consolas,Menlo,monospace"' if mono else ""
    return f'<text x="{x}" y="{y}" fill="{fill}" font-size="{size}" font-weight="{w}" text-anchor="{anchor}"{fam}>{esc(s)}</text>'
def box(x, y, w, h, fill="#1c222d", r=8, stroke=None):
    s = f' stroke="{stroke}" stroke-width="1.5"' if stroke else ""
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}"{s}/>'
def hl(x, y, w, h): return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="none" stroke="#4da3ff" stroke-width="3" stroke-dasharray="7 4"/>'
def badge(x, y, n): return f'<circle cx="{x}" cy="{y}" r="13" fill="#4da3ff"/><text x="{x}" y="{y+5}" text-anchor="middle" fill="#071018" font-size="14" font-weight="700">{n}</text>'
def btn(x, y, w, label, fill="#2f6fed"): return box(x, y, w, 30, fill, 7) + t(x + w/2, y+20, label, "#fff", 13, "600", "middle")
def field(x, y, w, label, val): return t(x, y-6, label, "#8b94a5", 12) + box(x, y, w, 32, "#0b0e13", 7, "#2b3342") + t(x+10, y+21, val, "#dfe5ef", 13, mono=True)
imgs = {}

imgs["ip-tailscale"] = frame("login.tailscale.com / admin / machines", 
    box(20,52,600,36,"#171c25")+t(36,75,"Machines",  "#fff",15,"600")+t(540,75,"3 machines","#8b94a5",12)+
    box(20,98,600,60,"#171c25")+t(36,122,"o-meu-servidor","#fff",15,"600")+t(36,144,"100.101.102.103","#7ee787",13,mono=True)+t(260,144,"o-meu-servidor.tuarede.ts.net","#7ee787",13,mono=True)+box(560,112,50,22,"#1f6f3f",11)+t(585,128,"Connected","#c6f6d5",9,anchor="middle")+
    box(20,166,600,60,"#171c25")+t(36,190,"portatil","#fff",15,"600")+t(36,212,"100.101.102.104","#8b94a5",13,mono=True)+
    hl(26,126,230,26)+hl(250,126,300,26)+badge(268,112,1)+badge(560,174,2)+
    t(320,300,"1  Nome ou IP do servidor (Tailscale)  /  Server name or IP","#dfe5ef",13,anchor="middle")+
    t(320,322,"2  Copie um deles / Copy either one","#dfe5ef",13,anchor="middle"))

imgs["ip-local"] = frame("PowerShell  /  Terminal",
    box(20,50,600,290,"#0b0e13",8)+t(36,78,"PS C:\\> ipconfig","#7ee787",14,mono=True)+
    t(36,108,"Adaptador Ethernet / Wi-Fi:","#8b94a5",13,mono=True)+
    t(36,134,"   Endereço IPv4 . . . : 192.168.X.Y","#dfe5ef",14,mono=True)+hl(150,118,300,24)+badge(470,130,1)+
    t(36,176,"$ hostname -I          (Linux/Mac)","#7ee787",14,mono=True)+t(36,200,"192.168.X.Y 172.17.X.Y","#dfe5ef",14,mono=True)+hl(30,184,190,22)+badge(240,196,2)+
    t(36,260,"Na app / In the app:  http://192.168.X.Y:7860","#4da3ff",15,"600",mono=True)+
    t(36,290,"1  Windows   2  Linux / Mac  (o primeiro / the first)","#8b94a5",12))

imgs["ip-oracle"] = frame("cloud.oracle.com / Compute / Instances",
    box(20,50,600,40,"#171c25")+t(36,76,"odysseus-vm","#fff",16,"700")+box(150,60,60,20,"#1f6f3f",10)+t(180,74,"Running","#c6f6d5",11,anchor="middle")+
    box(20,100,600,200,"#171c25")+t(36,126,"Instance information","#8b94a5",12)+
    t(36,156,"Public IP address","#8b94a5",13)+t(36,180,"203.0.113.25","#fff",18,"600",mono=True)+hl(28,162,200,28)+badge(250,176,1)+
    t(330,156,"Shape","#8b94a5",13)+t(330,180,"VM.Standard.A1.Flex","#dfe5ef",14)+
    t(36,226,"Image","#8b94a5",13)+t(36,250,"Canonical Ubuntu 24.04","#dfe5ef",14)+
    t(320,330,"1  Endereço IP público / Public IP address  → http://203.0.113.25","#dfe5ef",13,anchor="middle"))

imgs["oracle-create"] = frame("Oracle Cloud · Create instance",
    box(20,50,600,290,"#171c25")+t(36,78,"Image and shape","#fff",15,"600")+
    t(36,108,"Image","#8b94a5",12)+box(36,114,260,30,"#0b0e13",7,"#2b3342")+t(46,134,"Canonical Ubuntu 24.04","#dfe5ef",13)+hl(32,110,268,38)+badge(316,129,1)+
    t(36,176,"Shape","#8b94a5",12)+box(36,182,260,30,"#0b0e13",7,"#2b3342")+t(46,202,"Ampere · VM.Standard.A1.Flex","#dfe5ef",13)+hl(32,178,268,38)+badge(316,197,2)+
    t(36,244,"OCPUs 2   ·   Memory 12 GB","#dfe5ef",13)+hl(32,226,230,26)+badge(280,239,3)+
    t(36,282,"SSH keys: Generate a key pair  → Download private key","#dfe5ef",13)+hl(32,264,420,26)+badge(470,277,4)+
    btn(36,302,110,"Create"))

imgs["oracle-ports"] = frame("Oracle Cloud · Security List · Add Ingress Rules",
    box(20,50,600,290,"#171c25")+t(36,80,"Add Ingress Rules","#fff",15,"600")+
    field(36,110,260,"Source CIDR","0.0.0.0/0")+hl(32,92,268,52)+badge(316,127,1)+
    field(36,170,120,"IP Protocol","TCP")+hl(32,152,128,52)+badge(176,187,2)+
    field(36,230,260,"Destination Port Range","80,443")+hl(32,212,268,52)+badge(316,247,3)+
    btn(36,290,170,"Add Ingress Rules"))

imgs["ssh-connect"] = frame("PowerShell  /  Terminal",
    box(20,50,600,290,"#0b0e13",8)+t(36,80,"PS C:\\Users\\eu> ssh -i oracle.key ubuntu@203.0.113.25","#7ee787",13,mono=True)+hl(30,62,560,26)+badge(604,76,1)+
    t(36,114,"Welcome to Ubuntu 24.04 LTS","#8b94a5",13,mono=True)+
    t(36,142,"ubuntu@odysseus-vm:~$ ","#7ee787",13,mono=True)+t(36,176,"1  Cole aqui o comando do passo seguinte / Paste the next step's command","#dfe5ef",13)+
    t(36,206,"   (clique direito = colar / right-click = paste)","#8b94a5",12))

imgs["paste-install"] = frame("Terminal",
    box(20,50,600,290,"#0b0e13",8)+t(36,80,"$ git clone https://github.com/Canoruss/odysseus-kit \\","#7ee787",12,mono=True)+
    t(36,100,"    && bash odysseus-kit/install/install.sh --keys-file ~/keys.json","#7ee787",12,mono=True)+hl(30,62,570,48)+badge(612,86,1)+
    t(36,140,"==> Downloading Odysseus 1.0.2 …","#8b94a5",12,mono=True)+t(36,160,"==> Applying your API keys","#8b94a5",12,mono=True)+
    t(36,184,"================ Done ================","#28c840",13,mono=True)+
    t(36,206,"Open:     https://203-0-113-25.sslip.io","#fff",13,mono=True)+t(36,226,"User:     admin","#fff",13,mono=True)+t(36,246,"Password: ••••••••••••••••••••","#fff",13,mono=True)+
    hl(30,194,420,62)+badge(470,226,2)+t(36,300,"1  Um comando só / One command   2  Guarde o endereço, utilizador e palavra-passe / Save these","#dfe5ef",12))

imgs["wsl-install"] = frame("PowerShell (Administrador / Administrator)",
    box(20,50,600,290,"#0b0e13",8)+t(36,80,"PS C:\\WINDOWS\\system32> wsl --install -d Ubuntu","#7ee787",14,mono=True)+hl(30,62,420,26)+badge(470,76,1)+
    t(36,114,"A instalar o Ubuntu… / Installing Ubuntu…","#8b94a5",13,mono=True)+
    t(36,140,"Reinicie o computador quando pedido / Restart when asked","#febc2e",13,mono=True)+badge(560,136,2)+
    t(36,200,"Depois abra o menu Iniciar → «Ubuntu»","#dfe5ef",14)+t(36,222,"Then open Start menu → “Ubuntu”, create a user and a password","#dfe5ef",14)+badge(36,262,3)+
    t(60,267,"Cole o comando do passo seguinte lá dentro / Paste the next command there","#dfe5ef",13))

imgs["keys-groq"] = frame("console.groq.com / keys",
    box(20,50,600,290,"#171c25")+t(36,80,"API Keys","#fff",16,"700")+btn(470,62,130,"Create API Key")+hl(464,58,142,38)+badge(450,78,1)+
    box(36,120,570,40,"#0b0e13",7,"#2b3342")+t(48,145,"minha-chave","#dfe5ef",13)+t(250,145,"gsk_••••••••••••••••••••••••","#8b94a5",13,mono=True)+
    hl(240,128,260,24)+badge(520,140,2)+t(36,210,"1  Crie a chave (gratuito, sem cartão) / Create the key (free, no card)","#dfe5ef",13)+
    t(36,234,"2  Copie-a e cole-a na app (começa por gsk_) / Copy it into the app (starts with gsk_)","#dfe5ef",13))

for k, v in imgs.items():
    open(os.path.join(OUT, k + ".svg"), "w", encoding="utf-8").write(v)
print(len(imgs), "imagens")
