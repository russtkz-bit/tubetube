import unittest

from tubetube.converter import vtt_to_srt, vtt_to_text

MANUAL_VTT = """WEBVTT

00:00:00.000 --> 00:00:02.500
Привет, это тестовое видео.

00:00:02.500 --> 00:00:05.000
Сегодня мы поговорим о субтитрах.
"""

# Типичный "накатывающийся" автоматический VTT от YouTube: одна и та же
# строка повторяется в соседних репликах по мере появления новых слов.
AUTO_VTT = """WEBVTT
Kind: captions
Language: en

00:00:00.000 --> 00:00:02.000 align:start position:0%
Hello<00:00:00.500><c> everyone</c><00:00:01.000><c> and</c>

00:00:02.000 --> 00:00:04.000 align:start position:0%
Hello everyone and
welcome to the show

00:00:04.000 --> 00:00:06.000 align:start position:0%
welcome to the show
today we talk
"""


class TestVttToSrt(unittest.TestCase):
    def test_basic_conversion(self):
        srt = vtt_to_srt(MANUAL_VTT)
        self.assertIn("1\n00:00:00,000 --> 00:00:02,500\nПривет, это тестовое видео.", srt)
        self.assertIn("2\n00:00:02,500 --> 00:00:05,000\nСегодня мы поговорим о субтитрах.", srt)

    def test_strips_inline_tags(self):
        srt = vtt_to_srt(AUTO_VTT)
        self.assertNotIn("<c>", srt)
        self.assertNotIn("00:00:00.500", srt)  # inline karaoke timestamp tag


class TestVttToText(unittest.TestCase):
    def test_removes_consecutive_duplicate_lines(self):
        text = vtt_to_text(AUTO_VTT)
        lines = text.strip().split("\n")
        # "Hello everyone and" и "welcome to the show" не должны дублироваться подряд
        self.assertEqual(lines.count("Hello everyone and"), 1)
        self.assertEqual(lines.count("welcome to the show"), 1)

    def test_plain_text_content(self):
        text = vtt_to_text(MANUAL_VTT)
        self.assertIn("Привет, это тестовое видео.", text)
        self.assertIn("Сегодня мы поговорим о субтитрах.", text)


if __name__ == "__main__":
    unittest.main()
