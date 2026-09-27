#!/usr/bin/env bash
# Запуск графического интерфейса tubetube в Linux/macOS без сборки .exe.
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$DIR/.venv"

if [ ! -x "$VENV/bin/python" ]; then
    python3 -m venv "$VENV"
fi

# Всегда (пере)ставим зависимости — это быстро, если они уже установлены,
# зато чинит окружение, если предыдущая установка не завершилась.
"$VENV/bin/python" -m pip install --quiet --upgrade pip
"$VENV/bin/python" -m pip install --quiet -r "$DIR/requirements.txt"

exec "$VENV/bin/python" -m tubetube.gui
