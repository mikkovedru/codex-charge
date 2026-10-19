#!/usr/bin/env bash
# Build standalone Linux x86_64 executables.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-python3}"
"$PYTHON" -c 'import gi; gi.require_version("Gtk", "3.0"); gi.require_version("XApp", "1.0"); gi.require_version("Atspi", "2.0"); gi.require_foreign("cairo"); import pyatspi' || { echo "Install python3-gi python3-cairo python3-gi-cairo gir1.2-gtk-3.0 gir1.2-xapp-1.0 python3-pyatspi gir1.2-atspi-2.0 and use a system-site-packages virtualenv." >&2; exit 1; }

arch="$(uname -m)"
if [[ "$arch" != "x86_64" ]]; then
  echo "Release builds target x86_64 Linux only (got: $arch)" >&2
  exit 1
fi

LOCALES="$ROOT/recharge_ai_task/locales"
COMMON=(
  --noconfirm --onefile
  --specpath "$ROOT/build"
  --paths "$ROOT"
  --collect-data recharge_ai_task
  --add-data "$LOCALES:recharge_ai_task/locales"
)

echo "Building recharge-ai-task CLI..."
"$PYTHON" -m PyInstaller "${COMMON[@]}" --console \
  --name recharge-ai-task \
  scripts/entry_cli.py

echo "Building recharge-ai-task GUI launcher..."
"$PYTHON" -m PyInstaller "${COMMON[@]}" --console \
  --name recharge-ai-task-gui \
  scripts/entry_gui.py

echo "Building recharge-ai-task tray..."
"$PYTHON" -m PyInstaller --noconfirm scripts/tray_linux.spec

echo ""
echo "Output:"
echo "  dist/recharge-ai-task"
echo "  dist/recharge-ai-task-tray"
echo "  dist/recharge-ai-task-gui"
echo ""
echo "Linux desktop mode also requires: sudo apt install xdotool"
