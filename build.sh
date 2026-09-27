#!/usr/bin/env bash
# Собирает Linux/macOS-приложение TubeTube (единый файл, с GUI) с
# помощью PyInstaller. PyInstaller собирает исполняемый файл только под
# ту ОС, где он запущен, поэтому для .exe нужно запускать build.bat в
# Windows (или в этом же скрипте под Wine/CI для Windows — см. README).
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$DIR/.venv-build"

if [ ! -d "$VENV" ]; then
    python3 -m venv "$VENV"
fi

"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet -r "$DIR/requirements-build.txt"

"$VENV/bin/pyinstaller" \
    --noconfirm \
    --onefile \
    --windowed \
    --name TubeTube \
    --collect-all yt_dlp \
    --collect-all certifi \
    "$DIR/tubetube_gui_launcher.py"

echo
echo "Готово: dist/TubeTube"
