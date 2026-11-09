from __future__ import annotations

import threading
from pathlib import Path

from PyQt5.QtCore import QThread, pyqtSignal

from .audio import probe
from .engine import TranscriptionCancelled, VoskEngine
from .models import is_vosk_model
from .outputs import render_txt, write_outputs
from .summary import render_summary, write_summary


class TranscriptionWorker(QThread):
    file_started = pyqtSignal(int, float)
    file_progress = pyqtSignal(int, float)
    file_segment = pyqtSignal(int, str)
    file_partial = pyqtSignal(int, str)
    file_finished = pyqtSignal(int, object)
    file_failed = pyqtSignal(int, str)
    fatal = pyqtSignal(str)
    all_finished = pyqtSignal(int, int, bool)

    def __init__(
        self,
        files: list[str | Path],
        model_path: str | Path,
        output_dir: str | Path,
        formats: list[str],
        capitalize: bool,
        overwrite: bool,
        language: str = "ru",
        parent=None,
    ):
        super().__init__(parent)
        self._files = [Path(item) for item in files]
        self._model_path = Path(model_path)
        self._output_dir = Path(output_dir)
        self._formats = list(formats)
        self._capitalize = capitalize
        self._overwrite = overwrite
        self._language = language
        self._cancel = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()
        self.requestInterruption()

    def run(self) -> None:
        if not is_vosk_model(self._model_path):
            self.fatal.emit(f"Модель Vosk не найдена: {self._model_path}")
            self.all_finished.emit(0, 0, False)
            return
        try:
            engine = VoskEngine(self._model_path)
        except Exception as exc:
            self.fatal.emit(str(exc))
            self.all_finished.emit(0, 0, False)
            return
        succeeded = 0
        failed = 0
        cancelled = False
        for index, path in enumerate(self._files):
            if self._cancel.is_set():
                cancelled = True
                break
            try:
                info = probe(path)
                self.file_started.emit(index, info.duration)
                transcript = engine.transcribe(
                    path,
                    language=self._language,
                    duration=info.duration,
                    on_progress=lambda fraction, i=index: self.file_progress.emit(i, fraction),
                    on_segment=lambda text, i=index: self.file_segment.emit(i, text),
                    on_partial=lambda text, i=index: self.file_partial.emit(i, text),
                    cancel=self._cancel,
                )
                outputs = write_outputs(
                    transcript,
                    self._output_dir,
                    self._formats,
                    capitalize=self._capitalize,
                    overwrite=self._overwrite,
                )
                text = render_txt(transcript, capitalize=self._capitalize)
                summary_text = ""
                summary_path = ""
                summary_error = ""
                try:
                    summary_text = render_summary(transcript, capitalize=self._capitalize)
                    summary_path = write_summary(
                        transcript,
                        self._output_dir,
                        capitalize=self._capitalize,
                        overwrite=self._overwrite,
                    )
                except Exception as exc:
                    summary_error = str(exc).strip() or exc.__class__.__name__
                self.file_finished.emit(
                    index,
                    {
                        "outputs": outputs,
                        "text": text,
                        "transcript": transcript,
                        "summary": summary_text,
                        "summary_path": summary_path,
                        "summary_error": summary_error,
                    },
                )
                succeeded += 1
            except TranscriptionCancelled:
                self.file_failed.emit(index, "Остановлено")
                cancelled = True
                break
            except Exception as exc:
                message = str(exc).strip() or exc.__class__.__name__
                self.file_failed.emit(index, message)
                failed += 1
        self.all_finished.emit(succeeded, failed, cancelled)
