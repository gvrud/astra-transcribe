from __future__ import annotations

import json
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .audio import format_duration
from .engine import Segment, Transcript


@dataclass
class Cue:
    start: float
    end: float
    text: str


def capitalize_sentences(text: str) -> str:
    if not text:
        return text
    characters = list(text)
    capitalize = True
    for index, character in enumerate(characters):
        if capitalize:
            if character.isalpha():
                characters[index] = character.upper()
                capitalize = False
            elif character.isdigit():
                capitalize = False
        if character in ".!?…":
            capitalize = True
        elif character == "\n":
            capitalize = True
    return "".join(characters)


def _apply(text: str, capitalize: bool) -> str:
    return capitalize_sentences(text) if capitalize else text


def build_cues(
    segments: Iterable[Segment],
    *,
    max_chars: int = 84,
    max_duration: float = 7.0,
    max_gap: float = 0.9,
) -> list[Cue]:
    words = [word for segment in segments for word in segment.words]
    cues: list[Cue] = []
    current = []
    for word in words:
        if current:
            gap = word.start - current[-1].end
            length = sum(len(item.text) + 1 for item in current) + len(word.text)
            if gap > max_gap or word.end - current[0].start > max_duration or length > max_chars:
                cues.append(Cue(current[0].start, current[-1].end, " ".join(item.text for item in current)))
                current = []
        current.append(word)
    if current:
        cues.append(Cue(current[0].start, current[-1].end, " ".join(item.text for item in current)))
    return cues


def format_srt_time(seconds: float) -> str:
    milliseconds = max(0, int(round(seconds * 1000)))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def render_txt(transcript: Transcript, capitalize: bool = True) -> str:
    paragraphs = [_apply(segment.text, capitalize) for segment in transcript.segments if segment.text]
    if not paragraphs:
        return ""
    return "\n\n".join(paragraphs) + "\n"


def render_srt(
    transcript: Transcript,
    capitalize: bool = True,
    max_chars: int = 84,
    max_duration: float = 7.0,
    max_gap: float = 0.9,
) -> str:
    cues = build_cues(
        transcript.segments,
        max_chars=max_chars,
        max_duration=max_duration,
        max_gap=max_gap,
    )
    if not cues:
        return ""
    blocks: list[str] = []
    for index, cue in enumerate(cues, start=1):
        text = _apply(cue.text, capitalize)
        wrapped = textwrap.wrap(text, width=42, break_long_words=False, break_on_hyphens=False) or [text]
        if len(wrapped) > 2:
            wrapped = [wrapped[0], " ".join(wrapped[1:])]
        start = cue.start
        end = max(cue.end, start + 0.2)
        block = "\n".join(
            [
                str(index),
                f"{format_srt_time(start)} --> {format_srt_time(end)}",
                *wrapped,
            ]
        )
        blocks.append(block)
    return "\n\n".join(blocks) + "\n"


def render_json(transcript: Transcript, capitalize: bool = False) -> str:
    payload = transcript.to_dict()
    if capitalize:
        payload["text"] = capitalize_sentences(payload["text"])
        for segment in payload["segments"]:
            segment["text"] = capitalize_sentences(segment["text"])
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def write_docx(transcript: Transcript, path: str | Path, capitalize: bool = True) -> None:
    try:
        from docx import Document
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.shared import Cm, Pt, RGBColor
    except ImportError as exc:
        raise RuntimeError(
            "Для сохранения в DOCX установите python-docx: pip install python-docx"
        ) from exc
    document = Document()
    for section in document.sections:
        section.top_margin = Cm(2)
        section.bottom_margin = Cm(2)
        section.left_margin = Cm(2.2)
        section.right_margin = Cm(2.2)
    normal = document.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(11)
    normal.paragraph_format.line_spacing = 1.15
    normal.paragraph_format.space_after = Pt(6)

    title = document.add_heading("Расшифровка аудио", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.LEFT

    meta = document.add_paragraph()
    meta.alignment = WD_ALIGN_PARAGRAPH.LEFT
    meta_run = meta.add_run(
        f"Файл: {transcript.source.name}\n"
        f"Модель: {transcript.model_name}\n"
        f"Длительность: {format_duration(transcript.duration)}"
    )
    meta_run.font.size = Pt(9)
    meta_run.font.color.rgb = RGBColor(0x6B, 0x72, 0x80)
    meta.paragraph_format.space_after = Pt(16)

    has_text = False
    for segment in transcript.segments:
        text = _apply(segment.text, capitalize)
        if not text:
            continue
        has_text = True
        paragraph = document.add_paragraph(text)
        paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        paragraph.paragraph_format.first_line_indent = Cm(0.8)
        paragraph.paragraph_format.space_after = Pt(6)
    if not has_text:
        document.add_paragraph("Речь не распознана.")

    document.core_properties.title = "Расшифровка аудио"
    document.core_properties.subject = transcript.source.name
    document.core_properties.author = "Astra Transcribe"
    document.save(str(path))


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    counter = 2
    while True:
        candidate = path.with_name(f"{path.stem} ({counter}){path.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def unique_base_name(base: str, used: set[str]) -> str:
    name = Path(str(base or "audio")).name.strip() or "audio"
    key = name.casefold()
    if key not in used:
        used.add(key)
        return name
    counter = 2
    while True:
        candidate = f"{name} ({counter})"
        key = candidate.casefold()
        if key not in used:
            used.add(key)
            return candidate
        counter += 1


def write_outputs(
    transcript: Transcript,
    output_dir: str | Path,
    formats: Iterable[str],
    *,
    capitalize: bool = True,
    overwrite: bool = True,
    base_name: str | None = None,
) -> dict[str, str]:
    destination = Path(output_dir).expanduser()
    destination.mkdir(parents=True, exist_ok=True)
    writers = {
        "txt": render_txt,
        "srt": render_srt,
        "json": render_json,
    }
    base = base_name if base_name else (transcript.source.stem or "audio")
    result: dict[str, str] = {}
    for fmt in dict.fromkeys(item.lower().lstrip(".") for item in formats):
        if fmt != "docx" and fmt not in writers:
            raise ValueError(f"Неизвестный формат: {fmt}")
        path = destination / f"{base}.{fmt}"
        if not overwrite:
            path = unique_path(path)
        if fmt == "docx":
            write_docx(transcript, path, capitalize=capitalize)
        else:
            path.write_text(writers[fmt](transcript, capitalize=capitalize), encoding="utf-8")
        result[fmt] = str(path)
    return result
