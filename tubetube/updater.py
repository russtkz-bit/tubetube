"""Обновление библиотеки yt-dlp через pip.

YouTube нередко меняет сайт, и именно yt-dlp обычно быстро выпускает
исправление — поэтому саму программу tubetube обновлять не обязательно,
а вот yt-dlp полезно подтягивать свежим.
"""

from __future__ import annotations

import re
import subprocess
import sys
from typing import Callable, Optional

import yt_dlp

LogCallback = Callable[[str], None]

_INSTALLED_LINE_RE = re.compile(r"^Successfully installed\s+(.+)$", re.IGNORECASE | re.MULTILINE)
_YTDLP_TOKEN_RE = re.compile(r"^yt[_-]dlp-(\S+)$", re.IGNORECASE)


class UpdateError(RuntimeError):
    pass


def current_version() -> str:
    return yt_dlp.version.__version__


def is_frozen() -> bool:
    """True, если это собранный PyInstaller-ом .exe — там нет pip и
    отдельного интерпретатора Python, обновиться изнутри нельзя."""
    return bool(getattr(sys, "frozen", False))


def update_yt_dlp(on_log: Optional[LogCallback] = None) -> str:
    """Обновляет yt-dlp до последней версии с PyPI через pip.

    Возвращает текстовое описание результата. Бросает UpdateError, если
    обновление невозможно или завершилось ошибкой.
    """
    if is_frozen():
        raise UpdateError(
            "Это собранный .exe — в нём нет pip и отдельного Python, поэтому "
            "обновить yt-dlp изнутри программы нельзя. Чтобы получить свежую "
            "версию: обновите зависимости в исходниках (pip install --upgrade "
            "yt-dlp) и пересоберите .exe через build.bat/build.sh, либо "
            "запускайте tubetube из исходников (run-gui.bat/run-gui.sh)."
        )

    before = current_version()
    if on_log:
        on_log(f"Текущая версия yt-dlp: {before}")
        on_log("Обновляю через pip (pip install --upgrade yt-dlp)...")

    cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except OSError as exc:
        raise UpdateError(f"Не удалось запустить pip: {exc}") from exc

    if on_log:
        for line in (proc.stdout or "").splitlines():
            on_log(line)
        for line in (proc.stderr or "").splitlines():
            on_log(line)

    if proc.returncode != 0:
        raise UpdateError(f"pip завершился с ошибкой (код {proc.returncode}). Смотрите лог выше.")

    new_version = None
    line_match = _INSTALLED_LINE_RE.search(proc.stdout or "")
    if line_match:
        for token in line_match.group(1).split():
            token_match = _YTDLP_TOKEN_RE.match(token)
            if token_match:
                new_version = token_match.group(1)
                break

    if new_version:
        if on_log:
            on_log(f"yt-dlp обновлён: {before} -> {new_version}")
            on_log("Перезапустите программу, чтобы обновление применилось.")
        return f"yt-dlp обновлён до версии {new_version}. Перезапустите программу."

    if on_log:
        on_log(f"yt-dlp уже последней версии: {before}")
    return f"yt-dlp уже последней версии ({before})."
