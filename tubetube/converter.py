"""Конвертация субтитров YouTube (WebVTT) в SRT и обычный текст.

Реализовано без ffmpeg: YouTube всегда отдаёт субтитры в формате WebVTT,
поэтому достаточно уметь разбирать .vtt самим и конвертировать его в
нужный пользователю формат.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_TAG_RE = re.compile(r"<[^>]+>")
_TIMING_LINE_RE = re.compile(
    r"(\d{2}:\d{2}:\d{2}[.,]\d{3}|\d{2}:\d{2}[.,]\d{3})\s*-->\s*"
    r"(\d{2}:\d{2}:\d{2}[.,]\d{3}|\d{2}:\d{2}[.,]\d{3})"
)


@dataclass
class Cue:
    start: str
    end: str
    lines: list


def _normalize_timestamp(ts: str) -> str:
    ts = ts.replace(",", ".")
    if ts.count(":") == 1:
        ts = "00:" + ts
    hh, mm, rest = ts.split(":")
    ss, ms = rest.split(".")
    ms = (ms + "000")[:3]
    return f"{int(hh):02d}:{int(mm):02d}:{int(ss):02d}.{ms}"


def parse_vtt(text: str) -> list[Cue]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    blocks = text.split("\n\n")
    cues: list[Cue] = []
    for block in blocks:
        lines = [ln for ln in block.split("\n") if ln.strip() != ""]
        if not lines:
            continue
        timing_idx = None
        for i, ln in enumerate(lines):
            if "-->" in ln:
                timing_idx = i
                break
        if timing_idx is None:
            continue
        m = _TIMING_LINE_RE.search(lines[timing_idx])
        if not m:
            continue
        start, end = _normalize_timestamp(m.group(1)), _normalize_timestamp(m.group(2))
        text_lines = []
        for ln in lines[timing_idx + 1:]:
            cleaned = _TAG_RE.sub("", ln).strip()
            if cleaned:
                text_lines.append(cleaned)
        if text_lines:
            cues.append(Cue(start=start, end=end, lines=text_lines))
    return cues


def vtt_to_srt(vtt_text: str) -> str:
    cues = parse_vtt(vtt_text)
    out = []
    for idx, cue in enumerate(cues, start=1):
        start = cue.start.replace(".", ",")
        end = cue.end.replace(".", ",")
        out.append(str(idx))
        out.append(f"{start} --> {end}")
        out.extend(cue.lines)
        out.append("")
    return "\n".join(out).strip() + "\n"


def vtt_to_text(vtt_text: str) -> str:
    """Извлекает читаемый текст, убирая дублирующиеся "накатывающиеся"
    строки, характерные для автоматических субтитров YouTube."""
    cues = parse_vtt(vtt_text)
    result = []
    last_line = None
    for cue in cues:
        for line in cue.lines:
            if line == last_line:
                continue
            result.append(line)
            last_line = line
    return "\n".join(result).strip() + "\n"
