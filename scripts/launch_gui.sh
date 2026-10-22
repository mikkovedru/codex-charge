#!/bin/sh
# Compatibility command for the primary desktop executable.
ROOT=$(dirname -- "$(readlink -f -- "$0")")
exec "$ROOT/recharge-ai-task" "$@"
