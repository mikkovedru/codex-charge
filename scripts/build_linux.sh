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
  --name recharge-ai-task-cli \
  scripts/entry_cli.py

echo "Building the combined recharge-ai-task dashboard and tray..."
"$PYTHON" -m PyInstaller --noconfirm scripts/gui_linux.spec

# Preserve the previous tray command without bundling another Python runtime.
# Write beside the binaries so moving the release folder keeps it working.
for launcher in gui tray; do
  # Replace old executables atomically, including when a previous build is running.
  install -m 755 "scripts/launch_${launcher}.sh" "dist/recharge-ai-task-${launcher}.new"
  mv -f "dist/recharge-ai-task-${launcher}.new" "dist/recharge-ai-task-${launcher}"
done

echo ""
echo "Output:"
echo "  dist/recharge-ai-task"
echo "  dist/recharge-ai-task-tray (compatibility launcher)"
echo "  dist/recharge-ai-task-cli"
echo "  dist/recharge-ai-task-gui (compatibility launcher)"
echo ""
echo "Linux desktop mode also requires: sudo apt install xdotool"
