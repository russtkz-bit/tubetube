"""Обновление yt-dlp (через pip) и самого кода tubetube (через git pull).

YouTube нередко меняет сайт, и именно yt-dlp обычно быстро выпускает
исправление — эту библиотеку стоит обновлять чаще всего. Код самого
tubetube тоже можно подтянуть из репозитория (git pull), если он
запущен из исходников (не из собранного .exe).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
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


def _project_root() -> Path:
    """Корень репозитория tubetube (папка на уровень выше пакета)."""
    return Path(__file__).resolve().parent.parent


def is_git_checkout() -> bool:
    """True, если программа запущена из git-репозитория, а не из
    собранного .exe (там исходников и .git нет)."""
    return not is_frozen() and (_project_root() / ".git").is_dir()


def git_pull(on_log: Optional[LogCallback] = None) -> str:
    """Подтягивает последние изменения кода tubetube из git-репозитория
    (git pull --ff-only, без слияний и без потери локальных изменений).

    Возвращает текстовое описание результата. Бросает UpdateError, если
    обновление невозможно или завершилось ошибкой.
    """
    if is_frozen():
        raise UpdateError(
            "Это собранный .exe — в нём нет исходников и git, поэтому обновить "
            "код tubetube изнутри программы нельзя. Обновите исходники на "
            "компьютере с git (git pull) и пересоберите .exe через "
            "build.bat/build.sh, либо запускайте tubetube из исходников "
            "(run-gui.bat/run-gui.sh) — там кнопка обновления работает."
        )

    root = _project_root()
    if not (root / ".git").is_dir():
        raise UpdateError(
            f"Папка {root} не является git-репозиторием — обновление кода невозможно."
        )

    if on_log:
        on_log(f"Каталог проекта: {root}")
        on_log("Выполняю git pull --ff-only...")

    cmd = ["git", "pull", "--ff-only"]
    try:
        proc = subprocess.run(cmd, cwd=root, capture_output=True, text=True, check=False)
    except OSError as exc:
        raise UpdateError(f"Не удалось запустить git: {exc}") from exc

    if on_log:
        for line in (proc.stdout or "").splitlines():
            on_log(line)
        for line in (proc.stderr or "").splitlines():
            on_log(line)

    if proc.returncode != 0:
        raise UpdateError(
            f"git pull завершился с ошибкой (код {proc.returncode}). Смотрите лог выше — "
            "возможно, есть несохранённые локальные изменения или ветка разошлась с сервером."
        )

    output = (proc.stdout or "") + (proc.stderr or "")
    if "Already up to date" in output or "Already up-to-date" in output:
        if on_log:
            on_log("Код tubetube уже последней версии.")
        return "Код tubetube уже последней версии."

    if on_log:
        on_log("Код tubetube обновлён.")
        on_log("Перезапустите программу, чтобы изменения применились.")
    return "Код tubetube обновлён. Перезапустите программу, чтобы изменения применились."
