# tubetube

Кроссплатформенная (Windows / Linux) программа для скачивания субтитров
с видео и плейлистов YouTube. Работает на Python + [yt-dlp](https://github.com/yt-dlp/yt-dlp),
сама видео не скачивает — только субтитры (обычные, авторские, и/или
автоматически сгенерированные), с конвертацией в `.srt`, `.vtt` или обычный
текст `.txt`. Для конвертации ffmpeg не требуется.

## Установка

Нужен Python 3.8+.

### Linux / macOS

```bash
git clone <repo> tubetube
cd tubetube
./run.sh --help
```

При первом запуске `run.sh` сам создаст виртуальное окружение `.venv`
и поставит зависимости.

Либо вручную:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m tubetube.cli --help
```

Также можно установить как консольную команду:

```bash
pip install -e .
tubetube --help
```

### Windows

```bat
git clone <repo> tubetube
cd tubetube
run.bat --help
```

При первом запуске `run.bat` сам создаст виртуальное окружение `.venv`
и поставит зависимости (нужен установленный Python с добавлением в PATH).

Либо вручную (PowerShell/cmd):

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m tubetube.cli --help
```

## Использование

Скачать субтитры одного видео (по умолчанию — русские и английские,
и авторские, и автоматические, формат `.srt`):

```bash
tubetube "https://www.youtube.com/watch?v=XXXXXXXXXXX"
```

Скачать субтитры для целого плейлиста (ссылка на плейлист определяется
автоматически, файлы раскладываются по папке с названием плейлиста):

```bash
tubetube "https://www.youtube.com/playlist?list=XXXXXXXXXXXXXXXXX"
```

Посмотреть, какие языки субтитров вообще есть у видео:

```bash
tubetube --list-langs "https://www.youtube.com/watch?v=XXXXXXXXXXX"
```

Скачать субтитры на всех доступных языках в виде простого текста
(без таймкодов), только автоматические:

```bash
tubetube -l all -t auto -f txt "https://www.youtube.com/watch?v=XXXXXXXXXXX"
```

### Параметры

| Флаг | Описание | По умолчанию |
| --- | --- | --- |
| `-l`, `--langs` | Языки через запятую (`ru,en`) или `all` | `ru,en` |
| `-t`, `--type` | `manual` (авторские), `auto` (автоматические), `both` (оба) | `both` |
| `-f`, `--format` | `srt`, `vtt` или `txt` | `srt` |
| `-o`, `--output` | Папка для сохранения | `./subtitles` |
| `--keep-vtt` | Не удалять промежуточный `.vtt` при конвертации | выкл. |
| `--list-langs` | Только показать доступные языки и выйти | — |
| `-v`, `--verbose` | Подробный вывод yt-dlp | выкл. |

## Как это работает

- Ссылка на видео или плейлист передаётся в `yt-dlp`, который сам
  определяет, что это (одно видео или плейлист), и скачивает только
  файлы субтитров (`skip_download=True`, видео не загружается).
- YouTube отдаёт субтитры в формате WebVTT — программа скачивает именно
  его, а затем конвертирует в `.srt` или чистый `.txt` собственным кодом
  (`tubetube/converter.py`), без внешних зависимостей вроде ffmpeg.
- При конвертации в `.txt` автоматически убираются дублирующиеся строки,
  характерные для «наезжающих» автоматических субтитров YouTube.

## Тесты

```bash
python -m unittest discover -s tests
```
