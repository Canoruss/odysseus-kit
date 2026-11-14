# Instalação

Requisitos: Linux com Python 3.11+, o Odysseus a correr em Docker, e (para usar fora de casa) uma forma de o publicar com HTTPS, por exemplo [Tailscale](https://tailscale.com). Opcional: `poppler-utils` (`pdftotext`) para ler PDFs no Estudo.

## 1. Configuração

Há duas formas: o assistente no browser local (abaixo) ou, depois de a instalação estar de pé, **dentro do Odysseus**: Tools → **Setup** (só administradores; abre sozinho na primeira vez). O assistente também corre atrás do Hub em `/finance/setup/`, com a mesma autenticação do Odysseus.

```bash
python3 -I setup/wizard.py
```

Abre `http://127.0.0.1:8790` e percorre os passos. Cria:
- `~/.config/odysseus-kit/config.json` (funcionalidades ativas, nomes, fuso horário);
- `~/.config/odysseus-kit/<nome>.env` com as chaves (modo 600);
- `~/.config/odysseus-kit/kit-config.js` (configuração para o front-end).

Podes voltar a correr o assistente quando quiseres. Os valores guardados aparecem mascarados, e campo vazio significa "manter".

## 2. Arrancar as ferramentas

```bash
bash scripts/start.sh
```

| Serviço | Porta (127.0.0.1) | Caminho público sugerido |
|---|---|---|
| Hub (Finanças, Gym, Estudo, Notícias, Compor, Voos, Glicose, Caixa) | 8792 | `/finance` |
| Tradução | 8791 | `/translate` |
| Canva | 8793 | `/canva` |
| Assistente de configuração | 8790 | `/finance/setup/` (via Hub; só o administrador) |

Muda as portas com `KIT_HUB_PORT`, `KIT_TRANSLATE_PORT` e `KIT_CANVA_PORT`. Para arrancar no boot, usa `systemd --user` ou o `cron` (`@reboot`).

## 3. Publicar atrás do teu proxy

Com Tailscale:
```bash
sudo tailscale serve --set-path /finance   http://127.0.0.1:8792
sudo tailscale serve --set-path /translate http://127.0.0.1:8791
sudo tailscale serve --set-path /canva     http://127.0.0.1:8793
```

**Importante:** as ferramentas identificam o utilizador pelo cookie de sessão do Odysseus, por isso devem ficar no mesmo domínio que ele. Não as exponhas diretamente à Internet.

## 4. Ligar ao Odysseus

O front-end é um script que se acrescenta ao `index.html` do Odysseus:
1. Copia `web/ody-extras.js` para a pasta de ficheiros estáticos que montas no contentor (por exemplo `/app/static/js/ody-extras.js`) e `~/.config/odysseus-kit/kit-config.js` para o mesmo sítio.
2. No `index.html`, antes dos módulos, acrescenta:
   ```html
   <script src="/static/js/kit-config.js"></script>
   <script src="/static/js/ody-extras.js"></script>
   ```
3. Reinicia o contentor do Odysseus.

As ferramentas aparecem na barra **Tools**, e podes escondê-las em **Appearance**.

**Tema Ryoku (opcional):** copia `web/ryoku/` para `/app/static/ryoku/` e inclui `ryoku.css`. A arte vem de ryoku.dev (GPL-3.0, "dithered from AI-generated marble").

## 5. Tarefas agendadas (opcional)

Em `tools/jobs/`: avisos de prestações e despesas, lembretes de treino, lista diária do ClickUp e sincronização da galeria. Precisam de `~/.config/odysseus-kit/agent.env` com `ODYSSEUS_URL` e `ODYSSEUS_API_TOKEN` (token de agente criado nas definições do Odysseus). Exemplo de `cron`:
```
40 9 * * *  python3 -I ~/odysseus-kit/tools/jobs/installments.py
```

## Resolução de problemas

- **Página em branco ao abrir uma ferramenta:** o serviço não está a correr ou o proxy não aponta para a porta certa (`ss -ltn | grep 879`).
- **403 em tudo:** a ferramenta não reconheceu o utilizador. Confirma `owner` no assistente (tem de ser igual ao nome no Odysseus).
- **Chave recusada:** usa o botão Testar do assistente.
- **Procurar segredos antes de contribuir:** `python3 scripts/scan.py`.
