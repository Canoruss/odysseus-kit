# Extensão para o browser

[English](EXTENSION.md) · **Português**

Assistente em painel lateral para Chrome, Edge e outros browsers Chromium que fala com o **teu próprio servidor Odysseus**. Pasta: [`extension/`](../extension). Versão 0.13.1. Sem compilação, sem dependências e sem servidores de terceiros.

## Instalar

1. Descarrega `odysseus-kit-extension-<versão>.zip` da [última release](../../../releases/latest) (ou usa a pasta `extension/` deste repositório) e extrai.
2. Abre `chrome://extensions` (ou `edge://extensions`), liga o **Modo de programador**, escolhe **Carregar sem pacote** e seleciona a pasta que tem o `manifest.json`.
3. Fixa o **Odysseus** na barra de ferramentas e clica no ícone numa página web normal.
4. Abre as **Definições** (roda dentada) e preenche:
   - **Endereço do servidor**, por exemplo `https://o-teu-servidor.a-tua-tailnet.ts.net` (inclui porto ou prefixo se o teu proxy usar);
   - um **token de API do Odysseus com o âmbito `chat`** (cria-o nas definições do teu Odysseus).
5. Carrega em **Testar ligação** e depois em **Guardar**. O browser pede permissão só para esse servidor.

Para atualizar, substitui o conteúdo da pasta pela nova release e clica em **Recarregar** no cartão da extensão. As definições mantêm-se. (A atualização automática precisa de um endpoint de atualização no teu servidor, que o KIT não inclui; sem ele a verificação não faz nada.)

## O que faz

| Função | Como usar |
|---|---|
| **Chat** | Escreve e carrega em Enter (Shift+Enter para nova linha). Esc ou Parar interrompe. Os blocos de código têm botão de copiar. |
| **Página e Seleção** | Anexa o texto da página ou a tua seleção. Expande o anexo para ver exatamente o que vai ser enviado. O menu do botão direito prepara rascunhos. |
| **Vários separadores** | Anexa até três separadores com **Comparar separadores**. Páginas longas usam *Excertos relevantes* (só as passagens que correspondem à pergunta) ou *Capturas completas* (até 20 000 carateres por página). |
| **Captura de ecrã e ficheiros** | Até 4 ficheiros, 10 MiB cada e 16 MiB no total. Os tipos aceites dependem do teu servidor Odysseus. |
| **Guia da página** | Descreve um objetivo; o assistente propõe **um passo de cada vez**. *Mostrar na página* destaca o alvo, *Aplicar este passo* faz um clique, preenchimento, escolha, scroll ou navegação, e *Obter próximo passo* partilha uma nova captura. Nada acontece sem a tua aprovação. |
| **Modo agente** | Descreve um objetivo (por exemplo *procura no YouTube um vídeo e abre o mais visto*). O agente abre separadores, pesquisa, clica e lê páginas sozinho até concluir ou atingir o limite de passos. **Parar** funciona a qualquer momento. Nunca escreve palavras-passe nem paga. Pede permissão para agir nas páginas à primeira vez. |
| **Histórico** | As conversas ficam guardadas neste browser (podes pausar): pesquisa, muda o nome, retoma, apaga ou exporta em Markdown. |
| **Tempos** | Por baixo de cada resposta vês quanto demorou a ligação, a preparação local e o primeiro texto. |
| **Idiomas** | Inglês e português de Portugal, conforme o idioma do browser. |

## Privacidade

- A extensão só fala com o servidor que indicares. Pede essa permissão de um único endereço, não de todos os sites.
- O texto da página só é enviado **quando o anexas** (ou executas um passo do Guia). O Guia da página ignora campos de palavra-passe, cartão e ficheiros.
- O token fica no armazenamento da extensão; **Desligar e esquecer token** remove-o e a permissão do endereço.
- A permissão opcional `debugger` (usada para alguns cliques no modo agente) só é pedida quando necessária, e podes recusá-la.

## Problemas comuns

| Problema | Solução |
|---|---|
| *Testar ligação* falha | Confirma o endereço (https, porto, prefixo) e que o token tem o âmbito `chat`. Abre o endereço num separador para ver se o servidor responde. |
| Lista de modelos vazia | O servidor pode não expor a lista. Escreve um modelo nas Definições ou deixa em branco para o predefinido. |
| O painel não abre | Clica no ícone numa página web normal (não em páginas `chrome://`). |
