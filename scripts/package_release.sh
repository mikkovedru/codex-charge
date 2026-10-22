#!/usr/bin/env bash
# Package Linux release tar.gz from dist/ artifacts.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

CLI="$ROOT/dist/recharge-ai-task-cli"
TRAY="$ROOT/dist/recharge-ai-task-tray" # Small compatibility launcher, not a third binary.
GUI="$ROOT/dist/recharge-ai-task"
LEGACY_GUI="$ROOT/dist/recharge-ai-task-gui"
OUT="$ROOT/dist/recharge-ai-task-linux-x86_64.tar.gz"

[[ -f "$CLI" ]] || { echo "Missing $CLI — run scripts/build_linux.sh first" >&2; exit 1; }
[[ -f "$TRAY" ]] || { echo "Missing $TRAY — run scripts/build_linux.sh first" >&2; exit 1; }

[[ -f "$GUI" ]] || { echo "Missing $GUI — run scripts/build_linux.sh first" >&2; exit 1; }

[[ -f "$LEGACY_GUI" ]] || { echo "Missing $LEGACY_GUI — run scripts/build_linux.sh first" >&2; exit 1; }

rm -f "$OUT"
tar -czf "$OUT" -C "$ROOT/dist" recharge-ai-task recharge-ai-task-cli recharge-ai-task-tray recharge-ai-task-gui

HASH="$(sha256sum "$OUT" | awk '{print $1}')"
echo ""
echo "Created: $OUT"
echo "SHA256:  $HASH"
echo ""
echo "Upload to GitHub Release as: recharge-ai-task-linux-x86_64.tar.gz"
