"""Загрузка субтитров с YouTube (видео или плейлист) через yt-dlp.

Субтитры всегда запрашиваются у YouTube в формате WebVTT (его отдаёт
YouTube без дополнительных преобразований), а конвертация в SRT/TXT
делается своими силами в converter.py — это избавляет от зависимости
от ffmpeg.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Callable, Iterable, Optional

import yt_dlp
import yt_dlp.utils

from .converter import vtt_to_srt, vtt_to_text

LogCallback = Callable[[str], None]
CancelEvent = threading.Event


class DownloadError(RuntimeError):
    pass


class OperationCancelled(RuntimeError):
    """Операция остановлена пользователем (через cancel_event), не ошибка."""


def _check_cancelled(cancel_event: Optional[CancelEvent]) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise OperationCancelled("Отменено пользователем")


def _make_cancel_filter(cancel_event: Optional[CancelEvent]):
    """match_filter для yt-dlp: позволяет прервать обработку плейлиста
    между видео, если пользователь нажал «Отмена»."""

    def _filter(info_dict, *, incomplete=False):
        if cancel_event is not None and cancel_event.is_set():
            raise yt_dlp.utils.DownloadCancelled("Отменено пользователем")
        return None

    return _filter


class _YdlLogger:
    """Перенаправляет вывод yt-dlp в переданный колбэк (для GUI)."""

    def __init__(self, on_log: LogCallback):
        self._on_log = on_log

    def debug(self, msg: str) -> None:
        if msg.startswith("[debug] "):
            return
        self._on_log(msg)

    def info(self, msg: str) -> None:
        self._on_log(msg)

    def warning(self, msg: str) -> None:
        self._on_log(f"Предупреждение: {msg}")

    def error(self, msg: str) -> None:
        self._on_log(f"Ошибка: {msg}")


def _apply_logging_opts(opts: dict, on_log: Optional[LogCallback], verbose: bool) -> None:
    if on_log is not None:
        opts["logger"] = _YdlLogger(on_log)
        opts["quiet"] = True
        opts["no_warnings"] = True
    else:
        opts["quiet"] = not verbose
        opts["no_warnings"] = not verbose


def probe(
    url: str,
    on_log: Optional[LogCallback] = None,
    cancel_event: Optional[CancelEvent] = None,
) -> dict:
    """Возвращает информацию о ссылке без скачивания (для --list-langs)."""
    _check_cancelled(cancel_event)
    opts = {
        "skip_download": True,
        "extract_flat": False,
        "match_filter": _make_cancel_filter(cancel_event),
    }
    _apply_logging_opts(opts, on_log, verbose=False)
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadCancelled as exc:
        raise OperationCancelled(str(exc)) from exc
    except yt_dlp.utils.DownloadError as exc:
        raise DownloadError(f"Не удалось обработать ссылку: {exc}") from exc
    _check_cancelled(cancel_event)
    if info is None:
        raise DownloadError("Не удалось получить информацию по ссылке")
    if "entries" in info:
        entries = [e for e in info["entries"] if e]
        if not entries:
            raise DownloadError("Плейлист пуст или недоступен")
        return entries[0]
    return info


def list_available_languages(
    url: str,
    on_log: Optional[LogCallback] = None,
    cancel_event: Optional[CancelEvent] = None,
) -> tuple[dict, dict]:
    info = probe(url, on_log=on_log, cancel_event=cancel_event)
    manual = info.get("subtitles") or {}
    auto = info.get("automatic_captions") or {}
    return manual, auto


def _is_playlist(
    url: str,
    on_log: Optional[LogCallback] = None,
    cancel_event: Optional[CancelEvent] = None,
) -> bool:
    _check_cancelled(cancel_event)
    opts = {"extract_flat": True, "skip_download": True}
    _apply_logging_opts(opts, on_log, verbose=False)
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as exc:
        raise DownloadError(f"Не удалось обработать ссылку: {exc}") from exc
    _check_cancelled(cancel_event)
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
    on_log: Optional[LogCallback] = None,
    cancel_event: Optional[CancelEvent] = None,
) -> list[Path]:
    """Скачивает субтитры и конвертирует их в нужный формат.

    sub_type: "manual", "auto" или "both"
    fmt: "vtt", "srt" или "txt"
    on_log: необязательный колбэк для вывода хода работы (используется GUI)
    cancel_event: если установлен (threading.Event), операция останавливается
        и бросает OperationCancelled при первой безопасной возможности —
        между видео плейлиста или между конвертацией отдельных файлов.
        Уже скачанные к этому моменту файлы с диска не удаляются.
    Возвращает список путей к итоговым файлам субтитров.
    """
    _check_cancelled(cancel_event)
    langs = list(langs)
    is_playlist = _is_playlist(url, on_log=on_log, cancel_event=cancel_event)
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
        "restrictfilenames": False,
        "match_filter": _make_cancel_filter(cancel_event),
    }
    _apply_logging_opts(ydl_opts, on_log, verbose=verbose)
    if on_log is not None:
        ydl_opts["progress_hooks"] = [
            lambda d: on_log(f"Скачивание: {Path(d['filename']).name}")
            if d.get("status") == "finished" and "filename" in d
            else None
        ]

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except yt_dlp.utils.DownloadCancelled as exc:
        raise OperationCancelled(
            f"Скачивание отменено. Уже скачанные файлы (если есть) остались в папке {out_base}."
        ) from exc
    except yt_dlp.utils.DownloadError as exc:
        raise DownloadError(f"Ошибка загрузки: {exc}") from exc

    written_vtt_files = sorted(_collect_subtitle_filepaths(info))

    if not written_vtt_files:
        raise DownloadError(
            "Субтитры не найдены. Попробуйте --type auto (автоматические субтитры) "
            "или проверьте доступные языки через --list-langs."
        )

    if cancel_event is not None and cancel_event.is_set():
        raise OperationCancelled(
            f"Отменено. Успели скачать файлов: {len(written_vtt_files)} (формат vtt). "
            f"Папка: {out_base}."
        )

    if fmt == "vtt":
        return written_vtt_files

    if on_log is not None:
        on_log(f"Конвертация {len(written_vtt_files)} файл(ов) в формат {fmt}...")

    results: list[Path] = []
    for vtt_path in written_vtt_files:
        if cancel_event is not None and cancel_event.is_set():
            raise OperationCancelled(
                f"Отменено при конвертации. Готово файлов: {len(results)} из {len(written_vtt_files)}."
            )
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
