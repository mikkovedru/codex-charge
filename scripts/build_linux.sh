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

LOCALES="$ROOT/codex_charge/locales"
COMMON=(
  --noconfirm --onefile
  --paths "$ROOT"
  --collect-submodules codex_charge
  --collect-data codex_charge
  --add-data "$LOCALES:codex_charge/locales"
)

echo "Building codex-charge CLI..."
pyinstaller "${COMMON[@]}" --console \
  --name codex-charge \
  scripts/entry_cli.py

echo "Building codex-charge tray..."
pyinstaller "${COMMON[@]}" --windowed \
  --name codex-charge-tray \
  --collect-all pystray \
  scripts/entry_tray.py

echo ""
echo "Output:"
echo "  dist/codex-charge"
echo "  dist/codex-charge-tray"
echo ""
echo "Linux desktop mode also requires: sudo apt install xdotool"
