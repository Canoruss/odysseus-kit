# Guia de utilização

[English](GUIDE.md) · **Português**

Como usar o KIT depois de instalado ([INSTALL](INSTALL.pt.md) ou [ORACLE](ORACLE.pt.md)). Tudo é opcional: esconde ou reordena abas em *Definições → Aparência*.

## 1. Primeiros passos

1. Abre o Odysseus e procura as abas das ferramentas (Tradução, Finanças, Gym, Glicose, Ciclo, Estudo, Notícias, Voos, …).
2. Administradores: corre o **assistente de configuração** e cola só as chaves das ferramentas que queres. Cada passo tem **Testar** e **Saltar**.
3. Cada pessoa que entra tem **dados separados**. Nada é partilhado entre contas.
4. Instala a [app Android](APK.pt.md) e a [extensão do browser](EXTENSION.pt.md) se quiseres.

## 2. Ferramentas do dia a dia

| Ferramenta | Como usar |
|---|---|
| **Tradução** | Escolhe os idiomas, escreve, fala ou fotografa o texto. O *modo conversa* alterna entre duas pessoas. Usa as *sugestões de resposta* para mensagens de hóspedes. |
| **Compor** | Descreve a mensagem, recebe um rascunho e abre-o no email ou WhatsApp com o botão. |
| **Prompts** | Descreve no teu idioma o que queres; copia o prompt em inglês. Aparece um aviso quando faltam detalhes. |
| **Notícias** | Escolhe fontes e temas, silencia palavras, ativa *só críticas* e lê o resumo diário neutro. |
| **Estudo** | Adiciona um trabalho, divide-o em passos, junta fontes (a APA é gerada), resume um link ou PDF e exporta as referências para Word. Os prazos criam lembretes. |
| **Emails / Faturas** | Liga uma conta com palavra-passe de aplicação. Em *Contas*, confirma ou ignora cada fatura detetada; confirmar cria uma dívida. Marca uma fatura como mensal para lembretes recorrentes. |
| **Voos** | Adiciona número e data do voo. Tens contagem decrescente, estado e, com chave AirLabs, avisos de atraso e porta. |
| **Finanças** | Regista despesas e receitas, fotografa talões, define metas e dívidas com avisos no dia de vencimento. |
| **Gym / Treino+** | Segue o plano, regista séries com esforço, usa o temporizador de descanso e acompanha peso e fotos. Recordes pessoais e sugestões de progressão são automáticos. |
| **Glicose** | Liga o LibreLinkUp para gráfico e histórico, ou regista à mão. A *análise* mostra tempo no alvo, GMI e perfil diário e pode ser impressa para o médico. A calculadora de insulina vem **desativada**. |
| **Ciclo** | Regista período, fluxo, sintomas e humor. Inclui previsões, cartão da fase, a **Pingo** (pinguim guia) e PIN opcional. |
| **Foco** | Uma tarefa de cada vez, com temporizadores e passos pequenos. |
| **Sonhos** | Escreve ou dita um sonho e pede uma interpretação. |
| **Jogos grátis** | Vê o que está grátis agora. Liga os avisos e **escolhe as lojas** (Epic, Steam, GOG, itch.io, Prime) que te interessam. |
| **Otimizar média** | Reduz vídeos (ffmpeg, H.264/HEVC/AV1) e imagens (WebP/JPEG) e, opcionalmente, amplia imagens com IA (Real-ESRGAN). Os trabalhos correm um de cada vez, em fila. A ampliação com IA é opcional: instala com `install.sh --media-ai` ou `tools/media-tools/install_ai.sh --ai` (cerca de 1 GB, lenta em CPU). |

## 3. Lembretes e horas de silêncio

Tarefas agendadas criam lembretes no Odysseus (prestações, dívidas, prazos, voos, ciclo, treinos, jogos grátis, faturas).

- Abre **Foco** ou **Ciclo** e usa a caixa 🌙 **Horas de silêncio**: define *das* e *às* e marca *Ativar*.
- Durante o silêncio, os lembretes não urgentes esperam pelo fim. **Os avisos de voo e o lembrete da pílula nunca são adiados.**
- As horas de silêncio são por conta e vêm desligadas.

## 4. Pesquisar em tudo

Usa a caixa 🔎 no canto superior direito de qualquer página das ferramentas, ou abre `/finance/search?q=...`. Pesquisa só nos **teus** dados (Foco, Sonhos, Estudo, Contas, Finanças e, para o administrador, a Caixa de ideias) e destaca os resultados.

## 5. Private Browser (opcional)

Um Chromium real que o assistente pode controlar, com capturas de ecrã. Os teus logins ficam num perfil local no teu servidor.

```bash
cd tools/pbrowse
npm install && npx playwright install chromium
bash run.sh &                       # só escuta em 127.0.0.1:8794
python3 pb open https://example.com
python3 pb click "More information"
python3 pb text                     # texto da página
python3 pb extract                  # tabela produto / preço
python3 pb close
```

- `pb --profile NOME ...` mantém logins separados por perfil. Compras e envios de formulários ficam bloqueados salvo com `--confirm`: só o uses quando quiseres mesmo.
- Variáveis opcionais: `PB_LOCALE`, `PB_TZ`, `SEARXNG_URL` (para `pb search`; sem ela abre o DuckDuckGo no browser).
- **Vista ao vivo:** o administrador abre `/finance/pblive` para ver o browser e assumir o controlo: clicar na imagem, escrever, fazer scroll, voltar ou abrir um URL.

## 6. Extensão e app Android

- [Guia da extensão](EXTENSION.pt.md): chat no painel lateral, anexos de páginas, comparação de separadores, Guia da página e modo agente.
- [App Android](APK.pt.md): widgets, lembretes com ações, tradutor, tarefa rápida por voz.

## 7. Boas práticas

- Corre `python3 scripts/scan.py` antes de publicar qualquer fork: procura chaves e dados pessoais.
- Guarda as chaves só em `~/.config/odysseus-kit/*.env` (nunca no repositório).
- As ferramentas de saúde são informativas. Lê o [aviso de saúde](../README.pt.md#aviso-de-saúde).

## Aba Estado

**Ferramentas → Estado** abre uma janela flutuante (arrasta-se pelo título, redimensiona-se pelo canto; não bloqueia o chat). Mostra o uso em tempo real dos modelos de IA (Claude, ChatGPT, Groq, DeepL, AirLabs) e, só para a conta do dono, disco/RAM/swap do servidor, contentores e registos recentes. Atualiza a cada 30 s. Pode ser escondida em Aspeto, como as outras ferramentas.
