# Servidor grátis no Oracle Cloud (sem saber de servidores)

Este guia leva-te de zero a um Odysseus com o KIT a funcionar **na tua própria conta** do Oracle Cloud, com um único comando. Não há servidor de ninguém envolvido: os teus dados ficam na tua máquina e o autor do KIT não os vê.

Tempo: cerca de 30 a 40 minutos, quase todos a esperar por descargas.

> Os ecrãs do Oracle mudam com frequência. Os nomes abaixo são os habituais; se algum for diferente, procura o equivalente.

## O que vais precisar
- Um email e um telemóvel (para verificar a conta).
- Um cartão bancário. O Oracle usa-o só para confirmar a identidade e, no plano «Always Free», não cobra enquanto ficares dentro dos limites gratuitos.
- A tua própria chave de uma IA (Claude, Groq, Gemini, etc.), que acrescentas no fim.

## 1. Criar a conta
1. Abre <https://www.oracle.com/cloud/free/> e escolhe **Start for free**.
2. Preenche os dados e escolhe a **região** (a «home region» não se pode mudar depois; escolhe uma perto de ti).
3. Confirma o cartão e espera pelo email a dizer que a conta está pronta.

## 2. Criar a máquina (VM)
1. No painel: **Compute → Instances → Create instance**.
2. **Image:** Canonical **Ubuntu 24.04**.
3. **Shape:** muda para **Ampere (ARM) → VM.Standard.A1.Flex**, com **2 OCPUs e 12 GB de RAM** (dentro do gratuito). Evita a máquina «Micro» de 1 GB: é pequena demais para o Odysseus.
   - Se disser *Out of capacity*, tenta outra hora ou outro domínio de disponibilidade. É normal acontecer.
4. **Networking:** deixa «Assign a public IPv4 address» ligado.
5. **SSH keys:** escolhe **Generate a key pair** e **descarrega a chave privada** (guarda-a bem; sem ela não entras na máquina).
6. **Boot volume:** 50 GB chegam.
7. **Create**. Quando ficar verde (*Running*), copia o **Public IP address**.

## 3. Abrir as portas 80 e 443
O script não consegue fazer isto por ti, porque é uma regra da rede do Oracle e não da máquina.
1. Na página da instância, clica na **Subnet** (em *Primary VNIC*) e depois na **Security List** (a «Default»).
2. **Add Ingress Rules**: *Source CIDR* `0.0.0.0/0`, *IP Protocol* TCP, *Destination Port Range* `80,443`.
3. Guarda.

## 4. Entrar na máquina
No Windows (PowerShell), Mac ou Linux, com a chave que descarregaste:
```bash
ssh -i caminho/da/chave.key ubuntu@IP_PUBLICO
```
Se o SSH se queixar das permissões da chave, no Mac/Linux usa `chmod 600 caminho/da/chave.key`.

## 5. Correr o instalador
Dentro da máquina:
```bash
git clone https://github.com/Canoruss/odysseus-kit
bash odysseus-kit/install/install.sh --admin-user o_teu_nome --timezone Europe/Lisbon
```
Troca `o_teu_nome` pelo nome que queres para o administrador (letras minúsculas, números, `-` ou `_`).

O script demora uns 10 a 20 minutos (descarrega cerca de 3 GB). No fim mostra:
- o **endereço** (por exemplo `https://12-34-56-78.sslip.io`);
- o **utilizador** e uma **palavra-passe** gerada ao acaso. Guarda-a e muda-a depois de entrar.

Se tiveres um domínio teu, usa `--domain o.teu.dominio` (tem de apontar para o IP da máquina).

## 6. Primeiros passos no Odysseus
1. Abre o endereço no browser e entra com o utilizador e a palavra-passe.
2. Acrescenta a tua chave de IA: **definições → Models**. A chave é tua e fica só nesta máquina.
3. Abre **Tools → Setup** para ligar ou desligar as funções do KIT e preencher as chaves opcionais.
4. Na app Android do Odysseus, define o endereço do servidor como o do passo 5.

## Manutenção
- **Atualizar o KIT:** `cd ~/odysseus-kit && git pull && bash install/install.sh` (mantém os dados e a palavra-passe).
- **Ver o estado:** `cd ~/odysseus-server && sudo docker compose ps`.
- **Ver erros do Odysseus:** `cd ~/odysseus-server && sudo docker compose logs --tail 100 odysseus`.
- **Cópia de segurança:** copia a pasta `~/odysseus-server/data` e `~/.config/odysseus-kit`.
- **Remover tudo:** `bash ~/odysseus-kit/install/uninstall.sh --purge` (apaga os dados; sem `--purge` ficam guardados).

## Problemas comuns
| Sintoma | Causa provável |
|---|---|
| O site não abre do exterior | Falta o passo 3 (regras de entrada 80 e 443). |
| Erro de certificado | O Let's Encrypt precisa que as portas 80 e 443 estejam abertas; espera 1 a 2 minutos e recarrega. |
| «Out of capacity» ao criar a VM | Falta de máquinas gratuitas ARM nessa região; tenta mais tarde. |
| O script diz «Not enough RAM» | Usaste a máquina Micro; cria uma Ampere A1 com pelo menos 2 GB. |
| As abas do KIT não aparecem | Recarrega a página (Ctrl+F5) ou fecha e volta a abrir a app. |

## Privacidade e segurança
- Tudo corre na tua conta Oracle. O instalador não envia dados a ninguém e não tem telemetria.
- O endereço fica público na internet, por isso usa uma palavra-passe forte (a gerada já é) e mantém a máquina atualizada (`sudo apt update && sudo apt upgrade`).
- O código do KIT é público: podes ler `install/install.sh` antes de o correr.
