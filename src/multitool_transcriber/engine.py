from __future__ import annotations

import json
import locale
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from .audio import BYTES_PER_SECOND, SAMPLE_RATE, iter_pcm16, probe

ProgressCallback = Callable[[float], None]
TextCallback = Callable[[str], None]


class EngineError(RuntimeError):
    pass


class TranscriptionCancelled(Exception):
    pass


@dataclass
class Word:
    text: str
    start: float
    end: float
    conf: float = 0.0

    def to_dict(self) -> dict:
        return {
            "word": self.text,
            "start": round(self.start, 3),
            "end": round(self.end, 3),
            "conf": round(self.conf, 4),
        }


@dataclass
class Segment:
    start: float
    end: float
    words: list[Word] = field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join(word.text for word in self.words).strip()


@dataclass
class Transcript:
    source: Path
    model_name: str
    language: str
    duration: float
    segments: list[Segment]

    @property
    def text(self) -> str:
        return "\n\n".join(segment.text for segment in self.segments if segment.text)

    def to_dict(self) -> dict:
        return {
            "source": str(self.source),
            "file_name": self.source.name,
            "model": self.model_name,
            "language": self.language,
            "duration": round(self.duration, 3),
            "text": self.text,
            "segments": [
                {
                    "start": round(segment.start, 3),
                    "end": round(segment.end, 3),
                    "text": segment.text,
                    "words": [word.to_dict() for word in segment.words],
                }
                for segment in self.segments
            ],
        }


def force_c_numeric_locale() -> None:
    try:
        locale.setlocale(locale.LC_NUMERIC, "C")
    except locale.Error:
        pass


class VoskEngine:
    def __init__(self, model_path: str | Path):
        force_c_numeric_locale()
        try:
            import vosk
        except ImportError as exc:
            raise EngineError("Не установлен Vosk. Выполните: pip install vosk") from exc
        vosk.SetLogLevel(-1)
        self.model_path = Path(model_path)
        try:
            self._model = vosk.Model(str(self.model_path))
        except Exception as exc:
            raise EngineError(f"Не удалось загрузить модель {self.model_path.name}: {exc}") from exc
        self._recognizer_class = vosk.KaldiRecognizer

    @property
    def model_name(self) -> str:
        return self.model_path.name

    def transcribe(
        self,
        path: str | Path,
        *,
        language: str = "ru",
        duration: Optional[float] = None,
        on_progress: Optional[ProgressCallback] = None,
        on_segment: Optional[TextCallback] = None,
        on_partial: Optional[TextCallback] = None,
        cancel=None,
    ) -> Transcript:
        force_c_numeric_locale()
        file_path = Path(path)
        if duration is None:
            duration = probe(file_path).duration
        recognizer = self._recognizer_class(self._model, SAMPLE_RATE)
        recognizer.SetWords(True)
        segments: list[Segment] = []
        processed = 0
        total = int(duration * BYTES_PER_SECOND) if duration and duration > 0 else 0
        chunks = iter_pcm16(file_path)
        try:
            for chunk in chunks:
                if cancel is not None and cancel.is_set():
                    raise TranscriptionCancelled()
                if recognizer.AcceptWaveform(chunk):
                    segment = _segment_from_json(recognizer.Result())
                    if segment is not None and segment.words:
                        segments.append(segment)
                        if on_segment is not None:
                            on_segment(segment.text)
                processed += len(chunk)
                if on_progress is not None:
                    on_progress(min(1.0, processed / total) if total else -1.0)
                if on_partial is not None:
                    partial = json.loads(recognizer.PartialResult()).get("partial", "").strip()
                    on_partial(partial)
        finally:
            chunks.close()
        final = _segment_from_json(recognizer.FinalResult())
        if final is not None and final.words:
            segments.append(final)
            if on_segment is not None:
                on_segment(final.text)
        if on_progress is not None:
            on_progress(1.0)
        return Transcript(file_path, self.model_name, language, duration or 0.0, segments)


def _segment_from_json(raw: str) -> Optional[Segment]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        fixed = re.sub(r'("(?:start|end|conf)"\s*:\s*-?\d+),(\d+)', r"\1.\2", raw)
        if fixed == raw:
            return None
        try:
            payload = json.loads(fixed)
        except json.JSONDecodeError:
            return None
    words: list[Word] = []
    for item in payload.get("result", []):
        text = str(item.get("word", "")).strip()
        if not text:
            continue
        start = float(item.get("start", 0.0))
        end = float(item.get("end", start))
        words.append(Word(text, start, end, float(item.get("conf", 0.0))))
    if not words:
        return None
    return Segment(words[0].start, words[-1].end, words)
