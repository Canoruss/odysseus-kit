# Odysseus KIT

[English](README.md) · **Português**

Extras para o Odysseus (o teu chat de IA self-hosted): ferramentas dentro do chat, uma app Android e um assistente de configuração passo a passo. Tudo é opcional: cada pessoa liga só o que quer, e pode desligar o resto em **Appearance**.

> Estado: **pré-lançamento**. Foi extraído de uma instalação pessoal e ainda não foi testado por terceiros. Abre uma issue se algo falhar.

## O que inclui

| Ferramenta | O que faz | Precisa de |
|---|---|---|
| **Tradução** | pt/en/es/fr/de/…, voz, tradução por foto, sugestão de resposta a hóspedes | DeepL e/ou Groq |
| **Finanças** | movimentos, dívidas com avisos, metas, recibos por foto, despesas mensais | Groq (recibos) |
| **Gym + Treino+** | plano, séries, descanso, peso, fotos de progresso, técnica por IA, relatórios médicos | Groq/Gemini |
| **Estudo** | trabalhos, etapas, fontes com citação APA (exportar para Word), resumo de links/PDF com OCR para PDFs digitalizados, notas por cadeira, avisos de prazos e um separador **Planeador** de 14 dias | Groq |
| **Notícias** | feed por fontes e temas de cada pessoa + resumo do dia | Groq |
| **Compor** | rascunho de email/WhatsApp e botão para escolher a app de envio | Groq |
| **Voos** | guarda voos, abre no Flightradar24, atrasos com chave AirLabs | AirLabs (opcional) |
| **Glicose** | gráfico do LibreLinkUp e histórico. A calculadora de insulina vem **desligada** | LibreLinkUp |
| **Canva** | criar designs e exportar PNG | conta de developer Canva |
| **Caixa de ideias** | utilizadores enviam ideias/bugs, a IA organiza em tarefas | Groq |
| **Emails** | liga contas IMAP/SMTP (Gmail, Outlook, Yahoo, iCloud, outras) com os servidores já preenchidos e teste de ligação | palavras-passe de aplicação do fornecedor |
| **Setup** | o assistente passo a passo: chaves, serviços, ativar/saltar cada ferramenta (só administradores, abre na primeira vez) | — |
| **Abas das Tools** | ordenar e esconder as abas em *Settings → Appearance*; a ordem fica no servidor e vale para o browser e a app | — |
| **Idioma** | English / Português (Appearance e primeiro ecrã da app) | — |
| **Tema Ryoku** | tema extra para o Odysseus (arte GPL-3.0 do projeto ryoku.dev) | — |
| **App Android** | widgets, lembretes com ações, tradutor, calendário, bloqueio por impressão digital | Android Studio/SDK |

## Início rápido

```bash
git clone <este repositório> ~/odysseus-kit && cd ~/odysseus-kit
python3 -I setup/wizard.py        # abre http://127.0.0.1:8790 e guia-te passo a passo
bash scripts/start.sh             # arranca as ferramentas
```

O assistente explica cada serviço, diz onde obter as chaves, tem um botão **Testar**, e deixa **saltar** o que não queres. O que saltares fica desativado mas não se perde: podes voltar e ativar com as mesmas instruções.

Guia completo: [docs/INSTALL.pt.md](docs/INSTALL.pt.md). App Android: [docs/APK.pt.md](docs/APK.pt.md). Idiomas (English/Português): [docs/I18N.pt.md](docs/I18N.pt.md).

Dentro do Odysseus há também **Tools → Setup**, o mesmo assistente, que abre sozinho na primeira vez; e a app Android começa com um ecrã de idioma e servidor.

## Descarregar a app Android

Não precisas de compilar: a APK assinada está em **[Releases](../../releases/latest)** (`Odysseus-KIT-<versão>.apk`).

1. Descarrega-a no telemóvel e instala (ativa "instalar de fontes desconhecidas" quando o Android pedir).
2. Ao abrir, escolhe o idioma e escreve o endereço do teu Odysseus; carrega em **Testar ligação**.
3. Inicia sessão no Odysseus e segue o assistente em **Tools → Setup**.

Confirma sempre a impressão digital do certificado antes de instalar. A release indica o `SHA-256` do ficheiro e do certificado de assinatura, e podes verificá-los com `sha256sum` e `apksigner verify --print-certs`. A APK precisa do teu próprio servidor Odysseus: a app só mostra o que o teu servidor lhe servir.

## Segurança e privacidade

- As chaves ficam só em `~/.config/odysseus-kit/*.env` (modo 600), nunca no repositório.
- As ferramentas escutam apenas em `127.0.0.1` e devem ser publicadas atrás do teu proxy (Tailscale Serve, Caddy, nginx) **com a mesma autenticação do Odysseus**.
- As funcionalidades que usam IA enviam texto, áudio ou fotos para o fornecedor que escolheres (Groq, Gemini, DeepL…). Lê as políticas deles.
- `python3 scripts/scan.py` procura segredos e dados pessoais antes de publicares alterações.

## Aviso de saúde

Glicose, Gym e relatórios médicos são **ferramentas de apoio**, não aconselhamento médico. A calculadora de insulina não traz valores: só funciona se definires os do teu médico, e é por tua conta e risco. Ver [docs/GLUCOSE.pt.md](docs/GLUCOSE.pt.md).

## Licença

[AGPL-3.0](LICENSE), a mesma do Odysseus, de que este projeto é trabalho derivado. Se alterares e disponibilizares o serviço em rede, tens de partilhar o código. Atribuições em [NOTICE.md](NOTICE.pt.md).
