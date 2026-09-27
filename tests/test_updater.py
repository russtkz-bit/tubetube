import unittest

from tubetube.updater import _INSTALLED_LINE_RE, _YTDLP_TOKEN_RE

PIP_OUTPUT_UPGRADE = """Requirement already satisfied: yt-dlp in /venv/lib (2024.3.10)
Collecting yt-dlp
  Using cached yt_dlp-2026.8.19-py3-none-any.whl.metadata (183 kB)
Using cached yt_dlp-2026.8.19-py3-none-any.whl (3.2 MB)
Installing collected packages: yt-dlp
  Attempting uninstall: yt-dlp
    Found existing installation: yt-dlp 2024.3.10
    Uninstalling yt-dlp-2024.3.10:
      Successfully uninstalled yt-dlp-2024.3.10
Successfully installed yt-dlp-2026.8.19
"""

PIP_OUTPUT_ALREADY_LATEST = """Requirement already satisfied: yt-dlp in /venv/lib (2026.8.19)
"""


def _extract_version(pip_stdout: str):
    line_match = _INSTALLED_LINE_RE.search(pip_stdout)
    if not line_match:
        return None
    for token in line_match.group(1).split():
        m = _YTDLP_TOKEN_RE.match(token)
        if m:
            return m.group(1)
    return None


class TestUpdaterParsing(unittest.TestCase):
    def test_parses_new_version_after_upgrade(self):
        # Регрессия: раньше regex цеплялся за "Using cached yt_dlp-...whl.metadata"
        # вместо реальной строки "Successfully installed yt-dlp-...".
        self.assertEqual(_extract_version(PIP_OUTPUT_UPGRADE), "2026.8.19")

    def test_no_version_when_already_latest(self):
        self.assertIsNone(_extract_version(PIP_OUTPUT_ALREADY_LATEST))


if __name__ == "__main__":
    unittest.main()
