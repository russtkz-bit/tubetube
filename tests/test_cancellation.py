import threading
import unittest

import yt_dlp.utils as ydl_utils

from tubetube.downloader import (
    OperationCancelled,
    _check_cancelled,
    _make_match_filter,
    download_subtitles,
    list_available_languages,
)


class TestCancellation(unittest.TestCase):
    def test_check_cancelled_noop_when_not_set(self):
        ev = threading.Event()
        _check_cancelled(ev)  # не должно бросать
        _check_cancelled(None)  # тоже не должно бросать

    def test_check_cancelled_raises_when_set(self):
        ev = threading.Event()
        ev.set()
        with self.assertRaises(OperationCancelled):
            _check_cancelled(ev)

    def test_match_filter_raises_download_cancelled_when_set(self):
        ev = threading.Event()
        f = _make_match_filter(ev)
        self.assertIsNone(f({"id": "x"}))  # пока не отменено — пропускает видео
        ev.set()
        with self.assertRaises(ydl_utils.DownloadCancelled):
            f({"id": "x"})

    def test_match_filter_with_no_event_never_cancels(self):
        f = _make_match_filter(None)
        self.assertIsNone(f({"id": "x"}))

    def test_download_subtitles_bails_immediately_if_pre_cancelled(self):
        ev = threading.Event()
        ev.set()
        with self.assertRaises(OperationCancelled):
            download_subtitles("https://youtu.be/dummy", "irrelevant-output-dir", ["en"], cancel_event=ev)

    def test_list_available_languages_bails_immediately_if_pre_cancelled(self):
        ev = threading.Event()
        ev.set()
        with self.assertRaises(OperationCancelled):
            list_available_languages("https://youtu.be/dummy", cancel_event=ev)


if __name__ == "__main__":
    unittest.main()
