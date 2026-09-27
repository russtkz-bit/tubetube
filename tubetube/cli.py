"""Командная строка tubetube: скачивание субтитров с YouTube."""

from __future__ import annotations

import argparse
import sys

from .downloader import (
    DownloadError,
    compile_title_filter,
    download_subtitles,
    list_available_languages,
    list_playlist_entries,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tubetube",
        description=(
            "Скачивает субтитры с видео или плейлиста YouTube "
            "и сохраняет их в формате SRT, VTT или обычного текста."
        ),
    )
    parser.add_argument(
        "url", nargs="?", default=None,
        help="Ссылка на видео или плейлист YouTube (не нужна с --gui)",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Запустить графический интерфейс вместо командной строки",
    )
    parser.add_argument(
        "-l", "--langs",
        default="ru,en",
        help="Список языков через запятую (например 'ru,en') или 'all' для всех доступных. По умолчанию: ru,en",
    )
    parser.add_argument(
        "-t", "--type",
        choices=["manual", "auto", "both"],
        default="both",
        help="Какие субтитры скачивать: авторские (manual), автоматические (auto) или оба варианта (both, по умолчанию)",
    )
    parser.add_argument(
        "-f", "--format",
        choices=["srt", "vtt", "txt"],
        default="srt",
        help="Формат сохранения субтитров (по умолчанию: srt)",
    )
    parser.add_argument(
        "-o", "--output",
        default="subtitles",
        help="Папка для сохранения субтитров (по умолчанию: ./subtitles)",
    )
    parser.add_argument(
        "--keep-vtt",
        action="store_true",
        help="Не удалять промежуточный .vtt файл при конвертации в srt/txt",
    )
    parser.add_argument(
        "--list-langs",
        action="store_true",
        help="Показать доступные языки субтитров для видео и выйти (для плейлиста — по первому видео)",
    )
    parser.add_argument(
        "-T", "--title-filter",
        default=None,
        metavar="REGEX",
        help=(
            "Скачивать субтитры только тех видео плейлиста, чьё название подходит "
            "под это регулярное выражение (без учёта регистра). Например: "
            "'^1\\.' — только раздел 1.x, 'Domain 1' — по слову в названии. "
            "Подберите паттерн через --list-titles."
        ),
    )
    parser.add_argument(
        "--list-titles",
        action="store_true",
        help=(
            "Показать список видео плейлиста (индекс + название) и выйти, ничего не скачивая. "
            "Вместе с --title-filter отмечает, какие видео под него подходят — удобно для подбора паттерна."
        ),
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Подробный вывод yt-dlp",
    )
    return parser


def _print_languages(url: str, verbose: bool = False) -> None:
    manual, auto = list_available_languages(url, verbose=verbose)
    print("Авторские субтитры (manual):")
    if manual:
        for lang in sorted(manual):
            print(f"  - {lang}")
    else:
        print("  (нет)")
    print("Автоматические субтитры (auto-generated):")
    if auto:
        for lang in sorted(auto):
            print(f"  - {lang}")
    else:
        print("  (нет)")


def _print_titles(url: str, title_filter: str | None) -> None:
    pattern = compile_title_filter(title_filter) if title_filter else None
    is_playlist, entries = list_playlist_entries(url)
    kind = "Плейлист" if is_playlist else "Видео"
    print(f"{kind}: {len(entries)} видео")
    matched_count = 0
    for entry in entries:
        title = entry["title"]
        if pattern is not None:
            matched = bool(pattern.search(title))
            matched_count += matched
            mark = "[+]" if matched else "[ ]"
            print(f"  {mark} {entry['index']:>3}. {title}")
        else:
            print(f"  {entry['index']:>3}. {title}")
    if pattern is not None:
        print(f"\nПодходит под фильтр '{title_filter}': {matched_count} из {len(entries)}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.gui:
        from .gui import main as gui_main
        return gui_main()

    if not args.url:
        parser.error("укажите ссылку (url) или используйте --gui")

    try:
        if args.list_langs:
            _print_languages(args.url, verbose=args.verbose)
            return 0

        if args.list_titles:
            _print_titles(args.url, args.title_filter)
            return 0

        langs = ["all"] if args.langs.strip().lower() == "all" else [
            lang.strip() for lang in args.langs.split(",") if lang.strip()
        ]

        results = download_subtitles(
            url=args.url,
            output_dir=args.output,
            langs=langs,
            sub_type=args.type,
            fmt=args.format,
            keep_vtt=args.keep_vtt,
            verbose=args.verbose,
            title_filter=args.title_filter,
            on_log=print if args.title_filter else None,
        )

        print(f"\nГотово. Сохранено файлов субтитров: {len(results)}")
        for path in results:
            print(f"  - {path}")
        return 0
    except DownloadError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nПрервано пользователем.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
