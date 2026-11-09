from __future__ import annotations

import argparse
import signal
import sys
import threading
from pathlib import Path

from . import APP_NAME, __version__
from .audio import probe
from .engine import TranscriptionCancelled, VoskEngine
from .files import collect_files
from .models import (
    CATALOG,
    default_models_dir,
    discover_models,
    download_model,
    human_size,
    is_vosk_model,
)
from .outputs import render_txt, write_outputs
from .summary import write_summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="astra-transcribe-cli",
        description=f"{APP_NAME}: офлайн-распознавание речи в аудиофайлах с помощью Vosk.",
    )
    parser.add_argument("inputs", nargs="*", help="аудиофайлы или папки с файлами")
    parser.add_argument("-m", "--model", help="путь к папке модели Vosk")
    parser.add_argument("-o", "--out", default=".", help="папка для результатов")
    parser.add_argument("-f", "--formats", default="txt,docx", help="txt, docx, srt, json или all")
    parser.add_argument("--language", choices=["ru", "en"], help="язык распознавания")
    parser.add_argument("--model-dir", help="каталог, в котором установлены модели")
    parser.add_argument("--no-capitalize", action="store_true", help="не делать заглавные буквы")
    parser.add_argument("--no-overwrite", action="store_true", help="не перезаписывать результаты")
    parser.add_argument("--no-summary", action="store_true", help="не создавать краткое содержание")
    parser.add_argument("--print", dest="print_text", action="store_true", help="печатать текст в stdout")
    parser.add_argument("--quiet", action="store_true", help="не показывать прогресс")
    parser.add_argument("--list-models", action="store_true", help="показать модели и выйти")
    parser.add_argument("--download-model", metavar="NAME", help="скачать модель по имени")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.list_models:
        return _list_models()
    if args.download_model:
        return _download(args.download_model)
    if not args.inputs:
        parser.error("укажите аудиофайлы, папки или используйте --list-models")
    files = collect_files(args.inputs)
    if not files:
        print("Файлы не найдены.", file=sys.stderr)
        return 2
    try:
        model_path = _resolve_model(args)
        formats = _parse_formats(args.formats)
    except SystemExit as exc:
        if exc.code:
            print(str(exc), file=sys.stderr)
        return int(exc.code) if isinstance(exc.code, int) else 2
    output_dir = Path(args.out).expanduser()
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"Не удалось создать папку результатов: {exc}", file=sys.stderr)
        return 2
    cancel = threading.Event()

    def stop_handler(signum, frame):
        cancel.set()
        print("\nОстанавливаю…", file=sys.stderr)

    previous_handler = signal.signal(signal.SIGINT, stop_handler)
    try:
        engine = VoskEngine(model_path)
    except Exception as exc:
        print(f"Не удалось загрузить модель: {exc}", file=sys.stderr)
        signal.signal(signal.SIGINT, previous_handler)
        return 2
    language = args.language or _language_for(model_path.name)
    failed = 0
    cancelled = False
    try:
        for index, path in enumerate(files, start=1):
            if cancel.is_set():
                cancelled = True
                break
            print(f"[{index}/{len(files)}] {path.name}", file=sys.stderr)
            try:
                info = probe(path)
                callback = None if args.quiet else _progress_printer()
                transcript = engine.transcribe(
                    path,
                    language=language,
                    duration=info.duration,
                    on_progress=callback,
                    cancel=cancel,
                )
                if callback is not None:
                    print("", file=sys.stderr)
                outputs = write_outputs(
                    transcript,
                    output_dir,
                    formats,
                    capitalize=not args.no_capitalize,
                    overwrite=not args.no_overwrite,
                )
                summary_path = ""
                if not args.no_summary:
                    try:
                        summary_path = write_summary(
                            transcript,
                            output_dir,
                            capitalize=not args.no_capitalize,
                            overwrite=not args.no_overwrite,
                        )
                    except Exception as exc:
                        print(
                            f"  саммари не создано: {str(exc).strip() or exc.__class__.__name__}",
                            file=sys.stderr,
                        )
                if args.print_text:
                    text = render_txt(transcript, capitalize=not args.no_capitalize)
                    print(text, end="" if text.endswith("\n") else "\n")
                saved = list(outputs.values())
                if summary_path:
                    saved.append(summary_path)
                names = ", ".join(str(Path(item).name) for item in saved)
                print(f"  готово: {names}", file=sys.stderr)
            except TranscriptionCancelled:
                print("  остановлено", file=sys.stderr)
                cancelled = True
                break
            except Exception as exc:
                failed += 1
                print(f"  ошибка: {str(exc).strip() or exc.__class__.__name__}", file=sys.stderr)
    finally:
        signal.signal(signal.SIGINT, previous_handler)
    if cancelled:
        print("Работа остановлена.", file=sys.stderr)
        return 130
    return 1 if failed else 0


def _progress_printer():
    state = {"last": -1}

    def report(fraction: float) -> None:
        if fraction < 0:
            return
        percent = int(fraction * 100)
        if percent != state["last"]:
            print(f"\r  распознано: {percent:3d}%", end="", file=sys.stderr, flush=True)
            state["last"] = percent

    return report


def _download(name: str) -> int:
    if name not in CATALOG:
        print(f"Неизвестная модель: {name}", file=sys.stderr)
        print("Доступные модели: " + ", ".join(CATALOG), file=sys.stderr)
        return 2
    print(f"Скачивание {name}…", file=sys.stderr)
    state = {"last": -1}

    def report(downloaded: int, total: int) -> None:
        if total > 0:
            percent = int(downloaded * 100 / total)
            if percent != state["last"]:
                print(
                    f"\r  {percent:3d}%  {human_size(downloaded)} из {human_size(total)}",
                    end="",
                    file=sys.stderr,
                    flush=True,
                )
                state["last"] = percent
        else:
            print(f"\r  {human_size(downloaded)}", end="", file=sys.stderr, flush=True)

    try:
        path = download_model(name, default_models_dir(), progress=report)
    except KeyboardInterrupt:
        print("\nЗагрузка отменена.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"\nОшибка загрузки: {exc}", file=sys.stderr)
        return 1
    print("", file=sys.stderr)
    print(f"Модель установлена: {path}")
    return 0


def _list_models() -> int:
    print("Модели для загрузки:")
    for spec in CATALOG.values():
        print(f"  {spec.name}  —  {spec.title}, {human_size(spec.size)}")
    installed = discover_models()
    print("\nУстановленные модели:")
    if not installed:
        print("  нет")
    for info in installed:
        print(f"  {info.path}  ({human_size(info.size)})")
    return 0


def _resolve_model(args) -> Path:
    if args.model:
        path = Path(args.model).expanduser()
        if is_vosk_model(path):
            return path
        raise SystemExit(f"Модель Vosk не найдена: {path}")
    extra = [Path(args.model_dir)] if args.model_dir else []
    models = discover_models(extra)
    if not models:
        raise SystemExit(
            "Модель не найдена. Скачайте её: "
            "astra-transcribe-cli --download-model vosk-model-small-ru-0.22"
        )
    language = args.language or "ru"
    matching = [item for item in models if item.language == language]
    if matching:
        return matching[0].path
    if args.language:
        raise SystemExit(f"Модель для языка {language} не найдена")
    return models[0].path


def _parse_formats(value: str) -> list[str]:
    normalized = value.strip().lower()
    if normalized in {"all", "все"}:
        return ["txt", "srt", "docx", "json"]
    items = [item.strip().lower().lstrip(".") for item in normalized.split(",") if item.strip()]
    allowed = {"txt", "srt", "docx", "json"}
    unknown = [item for item in items if item not in allowed]
    if unknown:
        raise SystemExit(f"Неизвестные форматы: {', '.join(unknown)}")
    if not items:
        raise SystemExit("Укажите хотя бы один формат: txt, docx, srt или json")
    return list(dict.fromkeys(items))


def _language_for(name: str) -> str:
    lowered = name.lower()
    if "-en" in lowered:
        return "en"
    return "ru"


if __name__ == "__main__":
    raise SystemExit(main())
