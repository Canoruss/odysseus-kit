# App Android

A app é um invólucro [Capacitor](https://capacitorjs.com) à volta do teu Odysseus, com funções nativas: widgets (chat, tradução, notas, tarefa, despesas), lembretes com "Feito" e "Adiar", resumo da manhã, tradutor com câmara, calendário nos dois sentidos, bloqueio por impressão digital e leitura de SMS de consultas do SNS 24 (só Portugal, opcional).

Alternativa sem compilar: abre o endereço do Odysseus no Chrome e escolhe **Instalar aplicação** (PWA).

## APK pronta

A APK assinada de cada versão está nas **Releases** do repositório, com o `SHA-256` do ficheiro e do certificado. Só precisas de compilar se quiseres alterar a app.

## Primeiro ecrã da app

O endereço do servidor **já não fica dentro do APK**: ao abrir a app pela primeira vez aparece o ecrã de configuração (idioma e endereço do Odysseus, com teste de ligação). Depois do início de sessão abre-se o assistente Tools → Setup para as chaves e serviços. O endereço pode ser mudado repetindo o arranque (limpar dados da app).

## Compilar

Versão do código: **1.58** (versionCode 63). Requisitos: JDK 21, Android SDK (platform 35 e build-tools), Node 20+ e Rust com o Android NDK 27 (para a biblioteca de voz/política em `voice-core/`).

0a. `bash scripts/build-voice.sh` compila `voice-core/` e copia os `.so` para `android/app/src/main/jniLibs/`.

0. `cd android && npm install && npx cap sync android` (descarrega o Capacitor e gera `capacitor-cordova-android-plugins`; o `package.json` está em `android/`).
1. (Opcional, só para os textos de exemplo) os endereços `YOUR-SERVER...` nos ficheiros abaixo já não são usados no arranque; podes ignorá-los:
   - `android/app/src/main/assets/capacitor.config.json` (campo `server.url`);
   - `android/app/src/main/java/com/canorus/odysseus/Updater.java` (`BASE`) e `NoteSync.java` (`SITE`);
   - `android/www/error.html`.
   Procura `YOUR-SERVER.YOUR-TAILNET.ts.net` e substitui em todos.
2. Cria a tua chave de assinatura (guarda-a bem, sem ela não consegues atualizar a app):
   ```bash
   keytool -genkey -v -keystore ~/odysseus-kit.keystore -alias kit -keyalg RSA -keysize 2048 -validity 10000
   ```
   e cria `android/keystore.properties` (não vai para o Git) com `storeFile`, `storePassword`, `keyAlias`, `keyPassword`.
3. Compila: `cd android && ./gradlew assembleRelease`.
4. Instala o APK no telemóvel (ativa "instalar de fontes desconhecidas").

## Atualizações dentro da app

`android/tools/publish.sh` compila, assina e publica o APK numa pasta servida em `/odysseus-app/` (com `version.json`). A app verifica essa lista nas Definições. Serve a pasta com o mesmo proxy do passo 3 da instalação.

## Notas

- O identificador do pacote é `com.canorus.odysseus`. Se publicares a tua variante, muda-o.
- Permissões usadas: notificações, alarmes exatos, calendário, câmara, microfone, ler SMS (só para consultas SNS 24) e leitura de notificações. Podes removê-las do `AndroidManifest.xml` se não usares a função.
