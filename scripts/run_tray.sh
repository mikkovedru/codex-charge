#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec "$ROOT/.venv/bin/python" -m recharge_ai_task.gui --tray "$@"
