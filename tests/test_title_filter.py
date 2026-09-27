import unittest

from tubetube.downloader import (
    DownloadError,
    _entry_titles,
    _is_playlist_info,
    _make_match_filter,
    compile_title_filter,
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


if __name__ == "__main__":
    unittest.main()
