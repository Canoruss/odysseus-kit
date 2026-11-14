#!/usr/bin/env bash
# Publish a new Odysseus app version for the in-app updater.
#   ~/odysseus-apk/tools/publish.sh "1.3" "O que mudou nesta versão"
# Bumps versionCode, builds + signs the release APK, puts it in ~/odysseus-apk-updates
# (served at https://YOUR-SERVER.YOUR-TAILNET.ts.net/odysseus-app/) and writes version.json.
# Installed apps see it the next time they open (or within 30 min while open).
set -euo pipefail
NAME="${1:?usage: publish.sh <versionName> [notes]}"
NOTES="${2:-}"
ROOT=~/odysseus-apk
OUT=~/odysseus-apk-updates
GRADLE="$ROOT/android/app/build.gradle"
export ANDROID_HOME=~/android-sdk JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64

CUR=$(grep -oP 'versionCode \K[0-9]+' "$GRADLE")
NEW=$((CUR + 1))
sed -i -E "s/versionCode [0-9]+/versionCode $NEW/; s/versionName \"[^\"]*\"/versionName \"$NAME\"/" "$GRADLE"
echo "versionCode $CUR -> $NEW, versionName $NAME"

cd "$ROOT" && npx cap sync android >/dev/null
cd "$ROOT/android" && ./gradlew --no-daemon -q assembleRelease 2>&1 | grep -v -E "^Note:|warning" || true
APK="$ROOT/android/app/build/outputs/apk/release/app-release.apk"
BT=$(ls -d ~/android-sdk/build-tools/* | tail -1)
BADGING=$("$BT/aapt" dump badging "$APK")
[[ "$BADGING" == *"versionCode='$NEW'"* ]] || { echo "build did not produce versionCode $NEW" >&2; exit 1; }
"$BT/apksigner" verify "$APK" 2>&1 | grep -v "^WARNING" || true

FILE="Odysseus-$NAME.apk"
cp "$APK" "$OUT/$FILE"
cp "$APK" ~/odysseus-apk-out/Odysseus.apk
SHA=$(sha256sum "$OUT/$FILE" | cut -d' ' -f1)
python3 - "$OUT" "$NEW" "$NAME" "$FILE" "$SHA" "$NOTES" <<'PY'
import json, os, sys
out, code, name, f, sha, notes = sys.argv[1:]
tmp = os.path.join(out, ".version.json.tmp")
json.dump({"versionCode": int(code), "versionName": name, "apk": f, "sha256": sha, "notes": notes},
          open(tmp, "w"), ensure_ascii=False, indent=2)
os.replace(tmp, os.path.join(out, "version.json"))
PY
# keep only the 3 newest APKs
ls -1t "$OUT"/Odysseus-*.apk | tail -n +4 | xargs -r rm -f
echo "Published $FILE (sha256 $SHA)"
curl -s https://YOUR-SERVER.YOUR-TAILNET.ts.net/odysseus-app/version.json
