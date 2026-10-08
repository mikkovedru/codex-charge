#!/usr/bin/env bash
# Package Linux release tar.gz from dist/ artifacts.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

CLI="$ROOT/dist/codex-charge"
TRAY="$ROOT/dist/codex-charge-tray"
GUI="$ROOT/dist/codex-charge-gui"
OUT="$ROOT/dist/codex-charge-linux-x86_64.tar.gz"

[[ -f "$CLI" ]] || { echo "Missing $CLI — run scripts/build_linux.sh first" >&2; exit 1; }
[[ -f "$TRAY" ]] || { echo "Missing $TRAY — run scripts/build_linux.sh first" >&2; exit 1; }

[[ -f "$GUI" ]] || { echo "Missing $GUI — run scripts/build_linux.sh first" >&2; exit 1; }

rm -f "$OUT"
tar -czf "$OUT" -C "$ROOT/dist" codex-charge codex-charge-tray codex-charge-gui

HASH="$(sha256sum "$OUT" | awk '{print $1}')"
echo ""
echo "Created: $OUT"
echo "SHA256:  $HASH"
echo ""
echo "Upload to GitHub Release as: codex-charge-linux-x86_64.tar.gz"
