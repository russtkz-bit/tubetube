"""Загрузка субтитров с YouTube (видео или плейлист) через yt-dlp.

Субтитры всегда запрашиваются у YouTube в формате WebVTT (его отдаёт
YouTube без дополнительных преобразований), а конвертация в SRT/TXT
делается своими силами в converter.py — это избавляет от зависимости
от ffmpeg.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

import yt_dlp
import yt_dlp.utils

from .converter import vtt_to_srt, vtt_to_text


class DownloadError(RuntimeError):
    pass


def probe(url: str) -> dict:
    """Возвращает информацию о ссылке без скачивания (для --list-langs)."""
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": False,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as exc:
        raise DownloadError(f"Не удалось обработать ссылку: {exc}") from exc
    if info is None:
        raise DownloadError("Не удалось получить информацию по ссылке")
    if "entries" in info:
        entries = [e for e in info["entries"] if e]
        if not entries:
            raise DownloadError("Плейлист пуст или недоступен")
        return entries[0]
    return info


def list_available_languages(url: str) -> tuple[dict, dict]:
    info = probe(url)
    manual = info.get("subtitles") or {}
    auto = info.get("automatic_captions") or {}
    return manual, auto


def _is_playlist(url: str) -> bool:
    opts = {"quiet": True, "no_warnings": True, "extract_flat": True, "skip_download": True}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as exc:
        raise DownloadError(f"Не удалось обработать ссылку: {exc}") from exc
    return bool(info) and "entries" in info


def _collect_subtitle_filepaths(info: dict | None) -> set[Path]:
    paths: set[Path] = set()
    if not info:
        return paths
    entries = info.get("entries")
    if entries is not None:
        for entry in entries:
            paths |= _collect_subtitle_filepaths(entry)
        return paths
    requested = info.get("requested_subtitles") or {}
    for sub_info in requested.values():
        filepath = sub_info.get("filepath") if isinstance(sub_info, dict) else None
        if filepath:
            paths.add(Path(filepath))
    return paths


def download_subtitles(
    url: str,
    output_dir: str,
    langs: Iterable[str],
    sub_type: str = "manual",
    fmt: str = "srt",
    keep_vtt: bool = False,
    verbose: bool = False,
) -> list[Path]:
    """Скачивает субтитры и конвертирует их в нужный формат.

    sub_type: "manual", "auto" или "both"
    fmt: "vtt", "srt" или "txt"
    Возвращает список путей к итоговым файлам субтитров.
    """
    langs = list(langs)
    is_playlist = _is_playlist(url)
    out_base = Path(output_dir)
    out_base.mkdir(parents=True, exist_ok=True)

    if is_playlist:
        outtmpl = str(out_base / "%(playlist_title)s" / "%(playlist_index)03d - %(title)s.%(ext)s")
    else:
        outtmpl = str(out_base / "%(title)s.%(ext)s")

    ydl_opts = {
        "skip_download": True,
        "writesubtitles": sub_type in ("manual", "both"),
        "writeautomaticsub": sub_type in ("auto", "both"),
        "subtitleslangs": langs,
        "subtitlesformat": "vtt",
        "outtmpl": outtmpl,
        "ignoreerrors": True,
        "quiet": not verbose,
        "no_warnings": not verbose,
        "restrictfilenames": False,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except yt_dlp.utils.DownloadError as exc:
        raise DownloadError(f"Ошибка загрузки: {exc}") from exc

    written_vtt_files = sorted(_collect_subtitle_filepaths(info))

    if not written_vtt_files:
        raise DownloadError(
            "Субтитры не найдены. Попробуйте --type auto (автоматические субтитры) "
            "или проверьте доступные языки через --list-langs."
        )

    if fmt == "vtt":
        return written_vtt_files

    results: list[Path] = []
    for vtt_path in written_vtt_files:
        text = vtt_path.read_text(encoding="utf-8", errors="replace")
        if fmt == "srt":
            converted = vtt_to_srt(text)
            target = vtt_path.with_suffix(".srt")
        elif fmt == "txt":
            converted = vtt_to_text(text)
            target = vtt_path.with_suffix(".txt")
        else:
            raise ValueError(f"Неизвестный формат: {fmt}")
        target.write_text(converted, encoding="utf-8")
        results.append(target)
        if not keep_vtt:
            os.remove(vtt_path)

    return results
