from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

SAMPLE_RATE = 16000
BYTES_PER_SECOND = SAMPLE_RATE * 2
DEFAULT_CHUNK_BYTES = 8000


class AudioError(RuntimeError):
    pass


@dataclass(frozen=True)
class AudioInfo:
    duration: float
    sample_rate: int
    channels: int
    codec: str


def format_duration(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def probe(path: str | Path) -> AudioInfo:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(str(file_path))
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        return _probe_ffprobe(ffprobe, file_path)
    return _probe_pyav(file_path)


def iter_pcm16(path: str | Path, chunk_bytes: int = DEFAULT_CHUNK_BYTES) -> Iterator[bytes]:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(str(file_path))
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        yield from _iter_ffmpeg(ffmpeg, file_path, chunk_bytes)
    else:
        yield from _iter_pyav(file_path, chunk_bytes)


def _to_float(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _probe_ffprobe(ffprobe: str, path: Path) -> AudioInfo:
    command = [
        ffprobe,
        "-v",
        "error",
        "-select_streams",
        "a:0",
        "-show_entries",
        "stream=codec_name,sample_rate,channels,duration:format=duration",
        "-of",
        "json",
        str(path),
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AudioError(f"Не удалось запустить ffprobe: {exc}") from exc
    if result.returncode != 0:
        message = result.stderr.strip() or "ffprobe не смог прочитать файл"
        raise AudioError(message)
    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise AudioError("ffprobe вернул некорректный ответ") from exc
    streams = payload.get("streams") or []
    if not streams:
        raise AudioError("В файле нет аудиодорожки")
    stream = streams[0]
    format_info = payload.get("format") or {}
    duration = _to_float(stream.get("duration")) or _to_float(format_info.get("duration"))
    return AudioInfo(
        duration=duration,
        sample_rate=int(stream.get("sample_rate") or 0),
        channels=int(stream.get("channels") or 0),
        codec=str(stream.get("codec_name") or ""),
    )


def _import_av():
    try:
        import av
    except ImportError as exc:
        raise AudioError("Не установлен PyAV. Выполните: pip install av") from exc
    return av


def _probe_pyav(path: Path) -> AudioInfo:
    av = _import_av()
    try:
        with av.open(str(path)) as container:
            streams = [stream for stream in container.streams if stream.type == "audio"]
            if not streams:
                raise AudioError("В файле нет аудиодорожки")
            stream = streams[0]
            duration = 0.0
            if stream.duration is not None and stream.time_base is not None:
                duration = float(stream.duration * stream.time_base)
            elif container.duration is not None:
                duration = float(container.duration) / 1_000_000
            return AudioInfo(
                duration=duration,
                sample_rate=int(stream.rate or 0),
                channels=int(stream.channels or 0),
                codec=str(stream.codec_context.name or ""),
            )
    except AudioError:
        raise
    except Exception as exc:
        raise AudioError(f"Не удалось прочитать аудио: {exc}") from exc


def _iter_pyav(path: Path, chunk_bytes: int) -> Iterator[bytes]:
    av = _import_av()
    try:
        with av.open(str(path)) as container:
            streams = [stream for stream in container.streams if stream.type == "audio"]
            if not streams:
                raise AudioError("В файле нет аудиодорожки")
            stream = streams[0]
            resampler = av.AudioResampler(format="s16", layout="mono", rate=SAMPLE_RATE)
            buffer = bytearray()

            def collect(frames) -> None:
                for frame in frames:
                    buffer.extend(frame.to_ndarray().tobytes())

            for frame in container.decode(stream):
                collect(resampler.resample(frame))
                while len(buffer) >= chunk_bytes:
                    yield bytes(buffer[:chunk_bytes])
                    del buffer[:chunk_bytes]
            collect(resampler.resample(None))
            while len(buffer) >= chunk_bytes:
                yield bytes(buffer[:chunk_bytes])
                del buffer[:chunk_bytes]
            if len(buffer) % 2:
                del buffer[-1]
            if buffer:
                yield bytes(buffer)
    except AudioError:
        raise
    except Exception as exc:
        raise AudioError(f"Не удалось декодировать аудио: {exc}") from exc


def _iter_ffmpeg(ffmpeg: str, path: Path, chunk_bytes: int) -> Iterator[bytes]:
    command = [
        ffmpeg,
        "-nostdin",
        "-v",
        "error",
        "-i",
        str(path),
        "-map",
        "0:a:0",
        "-vn",
        "-f",
        "s16le",
        "-acodec",
        "pcm_s16le",
        "-ac",
        "1",
        "-ar",
        str(SAMPLE_RATE),
        "-",
    ]
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as exc:
        raise AudioError(f"Не удалось запустить ffmpeg: {exc}") from exc
    try:
        assert process.stdout is not None
        while True:
            chunk = process.stdout.read(chunk_bytes)
            if not chunk:
                break
            yield chunk
        stderr = b""
        if process.stderr is not None:
            stderr = process.stderr.read()
        code = process.wait()
        if code != 0:
            message = stderr.decode("utf-8", "replace").strip()
            raise AudioError(message or f"ffmpeg завершился с кодом {code}")
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
