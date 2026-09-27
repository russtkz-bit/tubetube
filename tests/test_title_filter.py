import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yt_dlp

import tubetube.downloader as downloader_module
from tubetube.downloader import (
    DownloadError,
    _entry_titles,
    _is_playlist_info,
    _make_match_filter,
    compile_title_filter,
    download_subtitles,
)

PLAYLIST_FLAT_INFO = {
    "entries": [
        {"title": "1.1 Compare Security Controls", "id": "a"},
        {"title": "1.2 Fundamental Security Concepts", "id": "b"},
        {"title": "2.1 Common Threat Actors", "id": "c"},
        None,  # yt-dlp иногда отдаёт None для недоступных видео
    ],
}

SINGLE_VIDEO_FLAT_INFO = {"title": "Just one video", "id": "z"}


class TestTitleFilterParsing(unittest.TestCase):
    def test_is_playlist_info(self):
        self.assertTrue(_is_playlist_info(PLAYLIST_FLAT_INFO))
        self.assertFalse(_is_playlist_info(SINGLE_VIDEO_FLAT_INFO))

    def test_entry_titles_playlist_skips_none_entries(self):
        entries = _entry_titles(PLAYLIST_FLAT_INFO)
        self.assertEqual(len(entries), 3)
        self.assertEqual(entries[0], {"index": 1, "title": "1.1 Compare Security Controls", "id": "a"})

    def test_entry_titles_single_video(self):
        entries = _entry_titles(SINGLE_VIDEO_FLAT_INFO)
        self.assertEqual(entries, [{"index": 1, "title": "Just one video", "id": "z"}])

    def test_compile_title_filter_invalid_regex_raises_download_error(self):
        with self.assertRaises(DownloadError):
            compile_title_filter("(unclosed[")

    def test_compile_title_filter_matches_case_insensitively(self):
        pattern = compile_title_filter("domain 1")
        self.assertTrue(pattern.search("Domain 1.0 Security Concepts"))
        self.assertFalse(pattern.search("Domain 2.0 Threats"))


class TestMatchFilterTitleFiltering(unittest.TestCase):
    def test_filters_out_non_matching_titles(self):
        pattern = compile_title_filter(r"^1\.")
        f = _make_match_filter(None, pattern)
        self.assertIsNone(f({"title": "1.1 Compare Security Controls"}))
        reason = f({"title": "2.1 Common Threat Actors"})
        self.assertIsNotNone(reason)
        self.assertIn("не подходит", reason)

    def test_no_pattern_matches_everything(self):
        f = _make_match_filter(None, None)
        self.assertIsNone(f({"title": "anything at all"}))

    def test_entries_without_title_are_not_rejected(self):
        """Регрессия: yt-dlp вызывает match_filter не только на каждом
        видео плейлиста, но и один раз на метаданных всего плейлиста
        целиком (там есть "playlist", но нет "title"). Раньше фильтр
        трактовал отсутствующий title как пустую строку и отклонял этот
        псевдо-элемент, из-за чего весь плейлист обрывался ещё до того,
        как начиналась обработка хотя бы одного настоящего видео."""
        pattern = compile_title_filter(r"^1\.")
        f = _make_match_filter(None, pattern)
        self.assertIsNone(f({"playlist": "CompTIA Security+ Training Course"}))
        self.assertIsNone(f({"title": ""}))
        self.assertIsNone(f({}))


class TestPartialDownloadWarning(unittest.TestCase):
    """Регрессия: реальный плейлист (121 видео) — фильтр правильно нашёл
    18 подходящих, но одно из них не скачалось из-за временного HTTP 429
    от YouTube. Пользователь должен увидеть явное предупреждение об этом
    в логе, а не тихо получить на файл меньше без объяснения."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)

        def fake_get_flat_info(url, on_log=None, cancel_event=None):
            return {
                "entries": [
                    {"title": "1.1 A", "id": "a"},
                    {"title": "1.2 B", "id": "b"},
                    {"title": "1.3 C", "id": "c"},  # эта "упадёт" с 429
                    {"title": "2.1 D", "id": "d"},  # не подходит под фильтр
                ]
            }

        patcher = mock.patch.object(downloader_module, "_get_flat_info", fake_get_flat_info)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _write_fake_vtt(self, name: str) -> str:
        path = str(Path(self.tmpdir) / name)
        Path(path).write_text("WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nhi\n", encoding="utf-8")
        return path

    def _run_with_fake_ydl(self, extract_info_result, **kwargs):
        class FakeYDL:
            def __init__(self, opts):
                self.opts = opts

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def extract_info(self, url, download=True):
                return extract_info_result

        logs = []
        with mock.patch.object(yt_dlp, "YoutubeDL", FakeYDL):
            results = download_subtitles(
                "https://example.com/playlist",
                self.tmpdir,
                ["en"],
                title_filter=r"^1\.",
                on_log=logs.append,
                **kwargs,
            )
        return results, logs

    def test_warns_when_fewer_files_than_matched(self):
        p1 = self._write_fake_vtt("001 - 1.1 A.en.vtt")
        p2 = self._write_fake_vtt("002 - 1.2 B.en.vtt")
        # видео 'c' (1.3) отсутствует в requested_subtitles — как если бы
        # yt-dlp получил на него HTTP 429 и пропустил с предупреждением
        info = {
            "entries": [
                {"requested_subtitles": {"en": {"filepath": p1}}},
                {"requested_subtitles": {"en": {"filepath": p2}}},
            ]
        }
        results, logs = self._run_with_fake_ydl(info, keep_vtt=False)

        self.assertEqual(len(results), 2)
        retry_line = next((line for line in logs if "повторная попытка" in line), None)
        self.assertIsNotNone(retry_line, f"Не было автоматической повторной попытки. Лог: {logs}")
        self.assertIn("индексы: 3", retry_line)  # видео 'c' — третье по счёту (индекс 3)
        warning = next((line for line in logs if line.startswith("Внимание:")), None)
        self.assertIsNotNone(warning, f"Не найдено предупреждение о нехватке файлов. Лог: {logs}")
        self.assertIn("2 файл(ов) из 3", warning)
        self.assertIn("--keep-vtt", warning)  # т.к. keep_vtt=False — совет его включить

    def test_retry_recovers_missing_file(self):
        """Первый проход недосчитался одного видео (как при HTTP 429),
        но автоматическая повторная попытка (playlist_items) его
        находит — в этом случае итоговый результат полный, и
        предупреждения быть не должно."""
        p1 = self._write_fake_vtt("001 - 1.1 A.en.vtt")
        p2 = self._write_fake_vtt("002 - 1.2 B.en.vtt")
        p3 = self._write_fake_vtt("003 - 1.3 C.en.vtt")

        first_pass = {
            "entries": [
                {"requested_subtitles": {"en": {"filepath": p1}}},
                {"requested_subtitles": {"en": {"filepath": p2}}},
            ]
        }
        retry_pass = {"requested_subtitles": {"en": {"filepath": p3}}}

        captured_opts = []

        class StatefulFakeYDL:
            call_count = 0

            def __init__(self, opts):
                captured_opts.append(opts)
                self.opts = opts

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def extract_info(self, url, download=True):
                StatefulFakeYDL.call_count += 1
                return first_pass if StatefulFakeYDL.call_count == 1 else retry_pass

        logs = []
        with mock.patch.object(yt_dlp, "YoutubeDL", StatefulFakeYDL):
            results = download_subtitles(
                "https://example.com/playlist",
                self.tmpdir,
                ["en"],
                title_filter=r"^1\.",
                on_log=logs.append,
                keep_vtt=False,
            )

        self.assertEqual(StatefulFakeYDL.call_count, 2)
        self.assertEqual(len(results), 3)
        self.assertEqual(captured_opts[1]["playlist_items"], "3")
        warning = next((line for line in logs if line.startswith("Внимание:")), None)
        self.assertIsNone(warning, f"После успешной повторной попытки предупреждения быть не должно. Лог: {logs}")
        success_line = next((line for line in logs if "скачано ещё 1 файл" in line), None)
        self.assertIsNotNone(success_line, f"Не было сообщения об успехе повторной попытки. Лог: {logs}")

    def test_no_warning_when_all_matched_files_present(self):
        p1 = self._write_fake_vtt("001 - 1.1 A.en.vtt")
        p2 = self._write_fake_vtt("002 - 1.2 B.en.vtt")
        p3 = self._write_fake_vtt("003 - 1.3 C.en.vtt")
        info = {
            "entries": [
                {"requested_subtitles": {"en": {"filepath": p1}}},
                {"requested_subtitles": {"en": {"filepath": p2}}},
                {"requested_subtitles": {"en": {"filepath": p3}}},
            ]
        }
        results, logs = self._run_with_fake_ydl(info, keep_vtt=False)

        self.assertEqual(len(results), 3)
        warning = next((line for line in logs if line.startswith("Внимание:")), None)
        self.assertIsNone(warning, f"Предупреждение не должно появляться, когда всё скачалось. Лог: {logs}")


if __name__ == "__main__":
    unittest.main()
