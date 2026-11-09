from __future__ import annotations

from pathlib import Path
from typing import Iterable

AUDIO_EXTENSIONS = {
    ".aac",
    ".aif",
    ".aiff",
    ".amr",
    ".avi",
    ".flac",
    ".m4a",
    ".m4b",
    ".m4v",
    ".mkv",
    ".mov",
    ".mp3",
    ".mp4",
    ".mpeg",
    ".mpg",
    ".oga",
    ".ogg",
    ".opus",
    ".ts",
    ".wav",
    ".webm",
    ".wma",
    ".wv",
}


def is_supported(path: str | Path) -> bool:
    return Path(path).suffix.lower() in AUDIO_EXTENSIONS


def dialog_filter() -> str:
    patterns = " ".join(f"*{ext}" for ext in sorted(AUDIO_EXTENSIONS))
    return f"Аудио и видео ({patterns});;Все файлы (*)"


def collect_files(inputs: Iterable[str | Path]) -> list[Path]:
    result: list[Path] = []
    seen: set[Path] = set()
    for item in inputs:
        path = Path(item).expanduser()
        if path.is_dir():
            candidates = sorted(child for child in path.rglob("*") if child.is_file() and is_supported(child))
        elif path.is_file():
            candidates = [path]
        else:
            continue
        for candidate in candidates:
            try:
                resolved = candidate.resolve()
            except OSError:
                resolved = candidate
            if resolved in seen:
                continue
            seen.add(resolved)
            result.append(candidate)
    return result
