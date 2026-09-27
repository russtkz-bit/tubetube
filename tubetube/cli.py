"""Командная строка tubetube: скачивание субтитров с YouTube."""

from __future__ import annotations

import argparse
import sys

from .downloader import DownloadError, download_subtitles, list_available_languages


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
        "-v", "--verbose",
        action="store_true",
        help="Подробный вывод yt-dlp",
    )
    return parser


def _print_languages(url: str) -> None:
    manual, auto = list_available_languages(url)
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
            _print_languages(args.url)
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
