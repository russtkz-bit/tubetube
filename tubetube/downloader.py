"""Загрузка субтитров с YouTube (видео или плейлист) через yt-dlp.

Субтитры всегда запрашиваются у YouTube в формате WebVTT (его отдаёт
YouTube без дополнительных преобразований), а конвертация в SRT/TXT
делается своими силами в converter.py — это избавляет от зависимости
от ffmpeg.
"""

from __future__ import annotations

import os
import re
import threading
from pathlib import Path
from typing import Callable, Iterable, Optional

import yt_dlp
import yt_dlp.utils

from .converter import vtt_to_srt, vtt_to_text

LogCallback = Callable[[str], None]
CancelEvent = threading.Event

# Без установленного JS-рантайма (Deno и т.п.) yt-dlp по умолчанию
# запрашивает данные о видео только через клиент "visionos" — у него
# иногда отсутствует информация о доступных субтитрах, и тогда yt-dlp
# сообщает "there are no subtitles", хотя на самом деле они есть.
# Добавляем "web" в список клиентов через "default" (не заменяя
# стандартный набор, а дополняя его) — для получения самого списка
# субтитров ему JS-рантайм не нужен, только для решения новых
# анти-бот-испытаний YouTube (PO Token), которые встречаются не всегда.
_YOUTUBE_EXTRACTOR_ARGS = {"youtube": {"player_client": ["web", "default"]}}


class DownloadError(RuntimeError):
    pass


class OperationCancelled(RuntimeError):
    """Операция остановлена пользователем (через cancel_event), не ошибка."""


def _check_cancelled(cancel_event: Optional[CancelEvent]) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise OperationCancelled("Отменено пользователем")


def compile_title_filter(pattern: str) -> "re.Pattern[str]":
    """Компилирует пользовательский regex-фильтр по названию видео
    (без учёта регистра). Бросает DownloadError при некорректном regex."""
    try:
        return re.compile(pattern, re.IGNORECASE)
    except re.error as exc:
        raise DownloadError(f"Некорректное регулярное выражение фильтра: {exc}") from exc


def _make_match_filter(
    cancel_event: Optional[CancelEvent],
    title_pattern: "Optional[re.Pattern[str]]" = None,
):
    """match_filter для yt-dlp: совмещает два назначения —
    1) позволяет прервать обработку плейлиста между видео, если
       пользователь нажал «Отмена»;
    2) если задан title_pattern, пропускает (не скачивает) видео,
       чьё название под него не подходит — это и есть фильтр по
       названию/разделу плейлиста (например, "только Домен 1.0")."""

    def _filter(info_dict, *, incomplete=False):
        if cancel_event is not None and cancel_event.is_set():
            raise yt_dlp.utils.DownloadCancelled("Отменено пользователем")
        if title_pattern is not None:
            title = info_dict.get("title")
            # yt-dlp вызывает match_filter не только для каждого видео, но и
            # один раз для метаданных всего плейлиста целиком (у него нет
            # поля "title", только "playlist"). Если title не известен —
            # это не видео, и фильтровать нечего: пропускаем проверку,
            # иначе плейлист обрывался бы целиком ещё до первого видео.
            if title and not title_pattern.search(title):
                return f"название не подходит под фильтр: {title!r}"
        return None

    return _filter


class _YdlLogger:
    """Перенаправляет вывод yt-dlp в переданный колбэк (для GUI)."""

    def __init__(self, on_log: LogCallback, verbose: bool = False):
        self._on_log = on_log
        self._verbose = verbose

    def debug(self, msg: str) -> None:
        # В подробном (verbose) режиме debug-сообщения yt-dlp могут
        # объяснять, почему что-то не скачалось — например, что часть
        # субтитров пропущена из-за требования PO Token (см. README).
        # В обычном режиме это в основном шум, поэтому по умолчанию скрыто.
        if msg.startswith("[debug] ") and not self._verbose:
            return
        self._on_log(msg)

    def info(self, msg: str) -> None:
        self._on_log(msg)

    def warning(self, msg: str) -> None:
        self._on_log(f"Предупреждение: {msg}")

    def error(self, msg: str) -> None:
        self._on_log(f"Ошибка: {msg}")


def _apply_logging_opts(opts: dict, on_log: Optional[LogCallback], verbose: bool) -> None:
    # Раньше verbose учитывался только при on_log=None — из-за этого
    # yt-dlp никогда не получал params["verbose"]=True при работе с GUI,
    # и его собственные debug-объяснения (например, про PO Token, из-за
    # которого могут пропадать субтитры) никогда не доходили до лога.
    opts["verbose"] = verbose
    if on_log is not None:
        opts["logger"] = _YdlLogger(on_log, verbose=verbose)
        opts["quiet"] = True
        opts["no_warnings"] = True
        # Без этого yt-dlp иногда вставляет ANSI-коды подсветки в сообщения
        # (думая, что пишет в цветной терминал) — в текстовом поле GUI они
        # выглядят как мусор вроде "[0;32m".
        opts["color"] = "no_color"
    else:
        opts["quiet"] = not verbose
        opts["no_warnings"] = not verbose


def probe(
    url: str,
    on_log: Optional[LogCallback] = None,
    cancel_event: Optional[CancelEvent] = None,
    verbose: bool = False,
) -> dict:
    """Возвращает информацию о ссылке без скачивания (для --list-langs)."""
    _check_cancelled(cancel_event)
    opts = {
        "skip_download": True,
        "extract_flat": False,
        "match_filter": _make_match_filter(cancel_event),
        "extractor_args": _YOUTUBE_EXTRACTOR_ARGS,
    }
    _apply_logging_opts(opts, on_log, verbose=verbose)
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
    verbose: bool = False,
) -> tuple[dict, dict]:
    info = probe(url, on_log=on_log, cancel_event=cancel_event, verbose=verbose)
    manual = info.get("subtitles") or {}
    auto = info.get("automatic_captions") or {}
    return manual, auto


def _get_flat_info(
    url: str,
    on_log: Optional[LogCallback] = None,
    cancel_event: Optional[CancelEvent] = None,
) -> dict:
    """Быстрый листинг ссылки (extract_flat) — без полного разбора
    каждого видео. Используется и для определения "это плейлист?",
    и для превью названий видео (см. list_playlist_entries)."""
    _check_cancelled(cancel_event)
    opts = {"extract_flat": True, "skip_download": True}
    _apply_logging_opts(opts, on_log, verbose=False)
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as exc:
        raise DownloadError(f"Не удалось обработать ссылку: {exc}") from exc
    _check_cancelled(cancel_event)
    return info or {}


def _is_playlist_info(info: dict) -> bool:
    return bool(info) and "entries" in info


def _entry_titles(info: dict) -> list[dict]:
    """[{'index': 1, 'title': ..., 'id': ...}, ...] — для плейлиста все
    видео по порядку, для одиночного видео список из одной записи."""
    if _is_playlist_info(info):
        entries = [e for e in info["entries"] if e]
        return [
            {"index": i, "title": e.get("title") or e.get("id") or "?", "id": e.get("id")}
            for i, e in enumerate(entries, start=1)
        ]
    return [{"index": 1, "title": info.get("title") or info.get("id") or "?", "id": info.get("id")}]


def list_playlist_entries(
    url: str,
    on_log: Optional[LogCallback] = None,
    cancel_event: Optional[CancelEvent] = None,
) -> tuple[bool, list[dict]]:
    """Превью плейлиста/видео без скачивания: возвращает (is_playlist,
    список {"index", "title", "id"}). Дёшево — использует extract_flat,
    не разбирает субтитры каждого видео. Полезно, чтобы подобрать
    --title-filter перед скачиванием."""
    info = _get_flat_info(url, on_log=on_log, cancel_event=cancel_event)
    return _is_playlist_info(info), _entry_titles(info)


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
    title_filter: Optional[str] = None,
) -> list[Path]:
    """Скачивает субтитры и конвертирует их в нужный формат.

    sub_type: "manual", "auto" или "both"
    fmt: "vtt", "srt" или "txt"
    on_log: необязательный колбэк для вывода хода работы (используется GUI)
    cancel_event: если установлен (threading.Event), операция останавливается
        и бросает OperationCancelled при первой безопасной возможности —
        между видео плейлиста или между конвертацией отдельных файлов.
        Уже скачанные к этому моменту файлы с диска не удаляются.
    title_filter: необязательный regex (без учёта регистра). Если задан,
        в плейлисте скачиваются субтитры только тех видео, чьё название
        ему соответствует — например, только раздел "Домен 1.0" курса.
        Для одиночного видео фильтр применяется к его названию так же.
    Возвращает список путей к итоговым файлам субтитров.
    """
    _check_cancelled(cancel_event)
    langs = list(langs)
    title_pattern = compile_title_filter(title_filter) if title_filter else None

    flat_info = _get_flat_info(url, on_log=on_log, cancel_event=cancel_event)
    is_playlist = _is_playlist_info(flat_info)

    if title_pattern is not None:
        entries = _entry_titles(flat_info)
        matched = [e for e in entries if title_pattern.search(e["title"])]
        if on_log is not None:
            on_log(f"Фильтр по названию '{title_filter}': подходит {len(matched)} из {len(entries)} видео.")
        if not matched:
            raise DownloadError(
                f"Ни одно видео не подошло под фильтр названия '{title_filter}'. "
                "Проверьте регулярное выражение или посмотрите список видео (--list-titles)."
            )

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
        "match_filter": _make_match_filter(cancel_event, title_pattern),
        "extractor_args": _YOUTUBE_EXTRACTOR_ARGS,
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
