from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Optional

from . import APP_ID, LEGACY_APP_ID

USER_AGENT = "Astra-Transcribe/1.0"
HF_API = "https://huggingface.co/api/models/{repo}"
HF_RESOLVE = "https://huggingface.co/{repo}/resolve/main/{path}"
DOWNLOAD_CHUNK = 262144
DOWNLOAD_TIMEOUT = 60
DOWNLOAD_ATTEMPTS = 5
DOWNLOAD_RETRY_DELAY = 1.0


class DownloadError(RuntimeError):
    pass


class DownloadCancelled(Exception):
    pass


@dataclass(frozen=True)
class ModelSpec:
    name: str
    title: str
    language: str
    size: int
    urls: tuple[str, ...]
    hf_repo: str = ""
    hf_path: str = ""


@dataclass(frozen=True)
class ModelInfo:
    name: str
    path: Path
    size: int
    language: str

    @property
    def title(self) -> str:
        spec = CATALOG.get(self.name)
        return spec.title if spec else self.name


CATALOG: dict[str, ModelSpec] = {
    "vosk-model-small-ru-0.22": ModelSpec(
        name="vosk-model-small-ru-0.22",
        title="Русский · компактная",
        language="ru",
        size=47_000_000,
        urls=(
            "https://huggingface.co/rhasspy/vosk-models/resolve/main/ru/vosk-model-small-ru-0.22.zip",
            "https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip",
        ),
    ),
    "vosk-model-small-en-us-0.15": ModelSpec(
        name="vosk-model-small-en-us-0.15",
        title="Английский · компактная",
        language="en",
        size=42_000_000,
        urls=(
            "https://huggingface.co/rhasspy/vosk-models/resolve/main/en/vosk-model-small-en-us-0.15.zip",
            "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip",
        ),
    ),
    "vosk-model-ru-0.42": ModelSpec(
        name="vosk-model-ru-0.42",
        title="Русский · полная",
        language="ru",
        size=3_700_000_000,
        urls=("https://alphacephei.com/vosk/models/vosk-model-ru-0.42.zip",),
        hf_repo="Derur/vosk-models",
        hf_path="stt/ru/vosk-model-ru-0.42",
    ),
}


def _data_dir(app_id: str) -> Path:
    base = os.environ.get("XDG_DATA_HOME")
    if base:
        return Path(base) / app_id
    return Path.home() / ".local" / "share" / app_id


def app_data_dir() -> Path:
    return _data_dir(APP_ID)


def legacy_data_dir() -> Path:
    return _data_dir(LEGACY_APP_ID)


def default_models_dir() -> Path:
    return app_data_dir() / "models"


def legacy_models_dir() -> Path:
    return legacy_data_dir() / "models"


def is_vosk_model(path: str | Path) -> bool:
    root = Path(path)
    return (
        (root / "am" / "final.mdl").is_file()
        and (root / "conf" / "model.conf").is_file()
        and ((root / "graph").is_dir() or (root / "ivector").is_dir())
    )


def model_size(path: str | Path) -> int:
    total = 0
    try:
        for item in Path(path).rglob("*"):
            if item.is_file():
                try:
                    total += item.stat().st_size
                except OSError:
                    continue
    except OSError:
        return total
    return total


def _language_for(name: str) -> str:
    spec = CATALOG.get(name)
    if spec:
        return spec.language
    lowered = name.lower()
    if "-ru" in lowered:
        return "ru"
    if "-en" in lowered:
        return "en"
    return ""


def discover_models(extra_dirs: Iterable[str | Path] = ()) -> list[ModelInfo]:
    roots: list[Path] = []
    for env_name in ("ASTRA_TRANSCRIBE_MODELS_DIR", "MULTITOOL_MODELS_DIR"):
        env_value = os.environ.get(env_name)
        if env_value:
            roots.extend(Path(item).expanduser() for item in env_value.split(os.pathsep) if item)
    roots.append(default_models_dir())
    roots.append(legacy_models_dir())
    roots.extend(Path(item).expanduser() for item in extra_dirs)
    found: list[ModelInfo] = []
    seen: set[Path] = set()
    for root in roots:
        if is_vosk_model(root):
            try:
                resolved = root.resolve()
            except OSError:
                resolved = root
            if resolved not in seen:
                seen.add(resolved)
                found.append(ModelInfo(root.name, root, model_size(root), _language_for(root.name)))
            continue
        if not root.is_dir():
            continue
        try:
            children = sorted(root.iterdir(), key=lambda item: item.name.lower())
        except OSError:
            continue
        for child in children:
            if not child.is_dir() or child.name.startswith("."):
                continue
            if not is_vosk_model(child):
                continue
            try:
                resolved = child.resolve()
            except OSError:
                resolved = child
            if resolved in seen:
                continue
            seen.add(resolved)
            found.append(ModelInfo(child.name, child, model_size(child), _language_for(child.name)))
    found.sort(
        key=lambda info: (
            info.name not in CATALOG,
            info.language != "ru",
            info.name.lower(),
        )
    )
    return found


def find_installed(name: str, models_dir: str | Path | None = None) -> Optional[Path]:
    roots = [Path(models_dir)] if models_dir else [default_models_dir(), legacy_models_dir()]
    for root in roots:
        candidate = root / name
        if is_vosk_model(candidate):
            return candidate
    return None


def human_size(size: int) -> str:
    value = float(max(0, size))
    for unit in ("Б", "КБ", "МБ", "ГБ"):
        if value < 1024 or unit == "ГБ":
            if unit == "Б":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} ГБ"


def download_model(
    name: str,
    models_dir: str | Path | None = None,
    *,
    progress: Optional[Callable[[int, int], None]] = None,
    cancel=None,
) -> Path:
    spec = CATALOG.get(name)
    if spec is None:
        raise DownloadError(f"Неизвестная модель: {name}")
    root = Path(models_dir) if models_dir else default_models_dir()
    root.mkdir(parents=True, exist_ok=True)
    installed = find_installed(spec.name, models_dir) if models_dir else find_installed(spec.name)
    if installed is not None:
        return installed
    target = root / spec.name
    if target.exists():
        raise DownloadError(f"Папка {target} уже существует, но не является корректной моделью")
    temporary = root / f".download-{spec.name}"
    temporary.mkdir(parents=True, exist_ok=True)
    keep_temporary = False
    try:
        archive = temporary / "model.zip"
        errors: list[str] = []
        if spec.hf_repo:
            try:
                unpacked = temporary / "unpacked"
                _download_hf_directory(spec, unpacked, progress, cancel)
                if not is_vosk_model(unpacked):
                    raise DownloadError("Зеркало Hugging Face не содержит полную модель Vosk")
                shutil.move(str(unpacked), str(target))
                return target
            except DownloadCancelled:
                raise
            except Exception as exc:
                errors.append(f"huggingface: {exc}")
        for url in spec.urls:
            try:
                _download_url(url, archive, progress, cancel)
                break
            except DownloadCancelled:
                raise
            except Exception as exc:
                errors.append(f"{url}: {exc}")
                if archive.exists():
                    archive.unlink()
        else:
            details = " | ".join(errors)
            raise DownloadError(f"Не удалось скачать модель. {details}")
        if not zipfile.is_zipfile(archive):
            raise DownloadError("Скачанный файл не является ZIP-архивом")
        unpacked = temporary / "unpacked"
        _safe_extract(archive, unpacked)
        source = _find_root(unpacked, spec.name)
        if not is_vosk_model(source):
            raise DownloadError("В архиве не найдена модель Vosk")
        if target.exists():
            raise DownloadError(f"Папка {target} уже существует, но не является корректной моделью")
        shutil.move(str(source), str(target))
        return target
    except DownloadCancelled:
        raise
    except Exception:
        keep_temporary = True
        raise
    finally:
        if not keep_temporary:
            shutil.rmtree(temporary, ignore_errors=True)


def _hf_files(repo: str, prefix: str) -> list[str]:
    request = urllib.request.Request(
        HF_API.format(repo=repo),
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise DownloadError(f"Не удалось получить список файлов: {exc}") from exc
    normalized = prefix.rstrip("/") + "/"
    files = sorted(
        str(item.get("rfilename", ""))
        for item in payload.get("siblings", [])
        if str(item.get("rfilename", "")).startswith(normalized)
    )
    if not files:
        raise DownloadError("На зеркале не найдены файлы модели")
    return files


def _content_range_total(value: str) -> int:
    match = re.search(r"/(\d+)\s*$", value or "")
    return int(match.group(1)) if match else 0


def _download_file(
    url: str,
    destination: Path,
    progress: Optional[Callable[[int, int], None]],
    cancel,
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    part = destination.with_name(destination.name + ".part")
    if destination.exists():
        return
    if part.exists() and part.stat().st_size == 0:
        part.unlink()
    last_error: Exception | None = None
    for attempt in range(DOWNLOAD_ATTEMPTS):
        if cancel is not None and cancel.is_set():
            raise DownloadCancelled()
        try:
            _download_attempt(url, part, destination, progress, cancel)
            return
        except DownloadCancelled:
            raise
        except Exception as exc:
            last_error = exc
            if attempt + 1 >= DOWNLOAD_ATTEMPTS:
                break
            time.sleep(min(DOWNLOAD_RETRY_DELAY * (2 ** attempt), 8.0))
    detail = str(last_error).strip() if last_error else "неизвестная ошибка"
    raise DownloadError(f"Не удалось скачать {destination.name}: {detail}") from last_error


def _download_attempt(
    url: str,
    part: Path,
    destination: Path,
    progress: Optional[Callable[[int, int], None]],
    cancel,
) -> None:
    offset = part.stat().st_size if part.exists() else 0
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "*/*",
        "Accept-Encoding": "identity",
    }
    if offset:
        headers["Range"] = f"bytes={offset}-"
    request = urllib.request.Request(url, headers=headers)
    try:
        response = urllib.request.urlopen(request, timeout=DOWNLOAD_TIMEOUT)
    except urllib.error.HTTPError as exc:
        if exc.code == 416 and offset:
            if _content_range_total(exc.headers.get("Content-Range", "")) == offset:
                part.replace(destination)
                return
            part.unlink(missing_ok=True)
        raise
    with response:
        status = response.getcode()
        total = 0
        if offset and status == 206:
            content_range = response.headers.get("Content-Range", "")
            match = re.match(r"bytes\s+(\d+)-(\d+)/(\d+|\*)", content_range)
            if match is None or int(match.group(1)) != offset:
                raise DownloadError("Сервер вернул неверный диапазон данных")
            if match.group(3) != "*":
                total = int(match.group(3))
            mode = "ab"
        elif status == 200:
            offset = 0
            total = int(response.headers.get("Content-Length") or 0)
            mode = "wb"
        else:
            raise DownloadError(f"Неожиданный ответ сервера: HTTP {status}")
        if total and offset > total:
            part.unlink(missing_ok=True)
            raise DownloadError("Локальный файл больше размера на сервере")
        if progress is not None:
            progress(offset, total)
        with open(part, mode) as output:
            current = offset
            while True:
                if cancel is not None and cancel.is_set():
                    raise DownloadCancelled()
                chunk = response.read(DOWNLOAD_CHUNK)
                if not chunk:
                    break
                output.write(chunk)
                current += len(chunk)
                if progress is not None:
                    progress(current, total)
        actual = part.stat().st_size
        if total and actual != total:
            raise DownloadError(f"Получено {actual} из {total} байт")
        if actual == 0:
            raise DownloadError("Сервер вернул пустой файл")
    part.replace(destination)


def _download_hf_directory(
    spec: ModelSpec,
    destination: Path,
    progress: Optional[Callable[[int, int], None]],
    cancel,
) -> None:
    files = _hf_files(spec.hf_repo, spec.hf_path)
    destination.mkdir(parents=True, exist_ok=True)
    prefix = spec.hf_path.rstrip("/") + "/"
    total = spec.size
    done = 0
    targets: list[tuple[str, Path]] = []
    for path in files:
        relative = path[len(prefix):]
        if not relative or relative.startswith(".git"):
            continue
        url = HF_RESOLVE.format(
            repo=spec.hf_repo,
            path=urllib.parse.quote(path, safe="/"),
        )
        target = destination / relative
        targets.append((url, target))
        if target.exists():
            done += target.stat().st_size
    if progress is not None:
        progress(done, total)
    for url, target in targets:
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)

        def on_progress(current: int, file_total: int, base: int = done) -> None:
            if progress is not None:
                value = base + current
                progress(min(total, value) if total else value, total)

        _download_file(url, target, on_progress, cancel)
        done += target.stat().st_size
        if progress is not None:
            progress(done, total)
    if progress is not None:
        progress(done, max(total, done))


def _download_url(
    url: str,
    destination: Path,
    progress: Optional[Callable[[int, int], None]],
    cancel,
) -> None:
    _download_file(url, destination, progress, cancel)


def _safe_extract(
    archive: Path,
    destination: Path,
    progress: Optional[Callable[[str], None]] = None,
) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    with zipfile.ZipFile(archive) as bundle:
        for info in bundle.infolist():
            name = info.filename.replace("\\", "/")
            if name.startswith("/") or any(part == ".." for part in Path(name).parts):
                raise DownloadError("Архив содержит недопустимые пути")
            mode = (info.external_attr >> 16) & 0o170000
            if mode == 0o120000:
                raise DownloadError("Архив содержит символические ссылки")
            target = (destination / name).resolve()
            if target != root and root not in target.parents:
                raise DownloadError("Архив содержит недопустимые пути")
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(info) as source, open(target, "wb") as output:
                shutil.copyfileobj(source, output)
            if progress is not None and name:
                progress(Path(name).name)


def _find_root(unpacked: Path, expected_name: str) -> Path:
    candidate = unpacked / expected_name
    if candidate.is_dir():
        return candidate
    children = [item for item in unpacked.iterdir() if item.is_dir()]
    if len(children) == 1:
        return children[0]
    return unpacked


def _find_model_root(unpacked: Path) -> Path | None:
    if is_vosk_model(unpacked):
        return unpacked
    for current, directories, _ in os.walk(unpacked):
        directories[:] = [item for item in directories if item != "__MACOSX"]
        path = Path(current)
        if path != unpacked and is_vosk_model(path):
            return path
    return None


def _safe_model_name(value: str) -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip(".-")
    return name or "vosk-model"


def import_model_zip(
    archive: str | Path,
    models_dir: str | Path | None = None,
    *,
    progress: Optional[Callable[[str], None]] = None,
) -> Path:
    source = Path(archive).expanduser()
    if not source.is_file():
        raise DownloadError(f"Файл не найден: {source}")
    if not zipfile.is_zipfile(source):
        raise DownloadError("Выбранный файл не является ZIP-архивом")
    root = Path(models_dir) if models_dir else default_models_dir()
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".import-", dir=str(root)) as temporary:
        unpacked = Path(temporary) / "unpacked"
        if progress is not None:
            progress("Проверка архива…")
        _safe_extract(source, unpacked, progress=progress)
        model_root = _find_model_root(unpacked)
        if model_root is None:
            raise DownloadError(
                "В ZIP не найдена модель Vosk. Нужны am/final.mdl, "
                "conf/model.conf и папка graph/ или ivector/."
            )
        name = model_root.name if model_root != unpacked else source.stem
        target = root / _safe_model_name(name)
        if target.exists():
            if is_vosk_model(target):
                return target
            raise DownloadError(
                f"Папка {target} уже существует, но не является корректной моделью"
            )
        if progress is not None:
            progress("Установка модели…")
        shutil.move(str(model_root), str(target))
        return target
