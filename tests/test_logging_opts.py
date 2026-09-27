import unittest

from tubetube.downloader import _YdlLogger, _apply_logging_opts


class TestApplyLoggingOpts(unittest.TestCase):
    def test_verbose_flows_through_to_ydl_params_with_on_log(self):
        # Регрессия: раньше verbose учитывался только при on_log=None,
        # поэтому yt-dlp никогда не получал params["verbose"]=True при
        # работе с GUI/CLI+on_log, и его debug-объяснения (например, про
        # PO Token, из-за которого пропадают субтитры) никогда не
        # доходили до лога.
        opts = {}
        _apply_logging_opts(opts, on_log=lambda m: None, verbose=True)
        self.assertTrue(opts["verbose"])

    def test_verbose_flows_through_without_on_log(self):
        opts = {}
        _apply_logging_opts(opts, on_log=None, verbose=True)
        self.assertTrue(opts["verbose"])
        self.assertFalse(opts["quiet"])

    def test_no_color_set_only_with_on_log(self):
        opts = {}
        _apply_logging_opts(opts, on_log=lambda m: None, verbose=False)
        self.assertEqual(opts["color"], "no_color")

        opts2 = {}
        _apply_logging_opts(opts2, on_log=None, verbose=False)
        self.assertNotIn("color", opts2)


class TestYdlLoggerVerboseFiltering(unittest.TestCase):
    def test_debug_lines_suppressed_by_default(self):
        messages = []
        logger = _YdlLogger(messages.append, verbose=False)
        logger.debug("[debug] some internal noise")
        self.assertEqual(messages, [])

    def test_debug_lines_forwarded_when_verbose(self):
        messages = []
        logger = _YdlLogger(messages.append, verbose=True)
        logger.debug("[debug] Some STM3EUvL7wg client subtitles require a PO Token")
        self.assertEqual(len(messages), 1)
        self.assertIn("PO Token", messages[0])

    def test_non_debug_lines_always_forwarded(self):
        messages = []
        logger = _YdlLogger(messages.append, verbose=False)
        logger.debug("[youtube] Extracting URL: ...")
        self.assertEqual(len(messages), 1)


if __name__ == "__main__":
    unittest.main()
