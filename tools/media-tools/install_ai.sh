#!/usr/bin/env bash
# Odysseus KIT: media tools engine. Creates the venv (Pillow, numpy) and, with --ai, adds PyTorch (CPU, ~1 GB) for AI upscaling.
# Usage: install_ai.sh [--ai]        (without --ai only video and image optimisation are enabled)
set -euo pipefail
D="$HOME/.local/share/odysseus-kit/media-tools"
mkdir -p "$D/models" "$D/jobs"
if ! command -v ffmpeg >/dev/null; then
  if [ "$(id -u)" -eq 0 ]; then SUDO=""; else SUDO="sudo"; fi
  $SUDO apt-get install -y ffmpeg python3-venv >/dev/null
fi
[ -x "$D/venv/bin/python" ] || python3 -m venv "$D/venv"
"$D/venv/bin/pip" install -q --upgrade pip
"$D/venv/bin/pip" install -q pillow numpy
if [ "${1:-}" = "--ai" ]; then
  echo "Installing PyTorch (CPU)..."
  "$D/venv/bin/pip" install -q torch --index-url https://download.pytorch.org/whl/cpu
  echo "AI upscaling ready (models are downloaded on first use, ~65 MB each)."
else
  echo "Video and image optimisation ready. Run again with --ai to add AI upscaling."
fi
echo "Restart the hub to pick up the change: sudo systemctl restart kit-hub"
