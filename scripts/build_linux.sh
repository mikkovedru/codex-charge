#!/usr/bin/env bash
# Build standalone Linux x86_64 executables.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

arch="$(uname -m)"
if [[ "$arch" != "x86_64" ]]; then
  echo "Release builds target x86_64 Linux only (got: $arch)" >&2
  exit 1
fi

echo "Building codex-charge CLI..."
pyinstaller --noconfirm --onefile --console \
  --name codex-charge \
  codex_charge/cli.py

echo "Building codex-charge tray..."
pyinstaller --noconfirm --onefile --windowed \
  --name codex-charge-tray \
  --collect-all pystray \
  codex_charge/tray.py

echo ""
echo "Output:"
echo "  dist/codex-charge"
echo "  dist/codex-charge-tray"
echo ""
echo "Linux desktop mode also requires: sudo apt install xdotool"
