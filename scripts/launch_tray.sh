#!/bin/sh
# Compatibility command for the combined desktop executable.
# Preserve older dashboard/settings/helper invocations as well as tray startup.
ROOT=$(dirname -- "$(readlink -f -- "$0")")
for argument in "$@"; do
  case "$argument" in
    --targets|--settings|--resume-goal-ui)
      exec "$ROOT/recharge-ai-task" "$@"
      ;;
  esac
done
exec "$ROOT/recharge-ai-task" --tray "$@"
