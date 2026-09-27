#!/usr/bin/env bash
# Запуск tubetube в Linux/macOS: создаёт venv при первом запуске,
# ставит зависимости и передаёт все аргументы в программу.
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$DIR/.venv"

if [ ! -d "$VENV" ]; then
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install --quiet --upgrade pip
    "$VENV/bin/pip" install --quiet -r "$DIR/requirements.txt"
fi

exec "$VENV/bin/python" -m tubetube.cli "$@"
