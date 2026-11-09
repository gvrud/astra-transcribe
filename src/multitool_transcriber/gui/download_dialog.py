from __future__ import annotations

import threading

from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from ..models import (
    CATALOG,
    DownloadCancelled,
    default_models_dir,
    download_model,
    find_installed,
    human_size,
)


class DownloadWorker(QThread):
    progress = pyqtSignal(int, int)
    succeeded = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, spec, parent=None):
        super().__init__(parent)
        self._spec = spec
        self._cancel = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()

    def run(self) -> None:
        try:
            path = download_model(
                self._spec.name,
                default_models_dir(),
                progress=lambda done, total: self.progress.emit(done, total),
                cancel=self._cancel,
            )
            self.succeeded.emit(str(path))
        except DownloadCancelled:
            self.failed.emit("Загрузка отменена")
        except Exception as exc:
            self.failed.emit(str(exc).strip() or exc.__class__.__name__)


class DownloadDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_path: str | None = None
        self._worker: DownloadWorker | None = None
        self._pending_path: str | None = None
        self.setWindowTitle("Скачать модель")
        self.setModal(True)
        self.resize(560, 350)
        self._build_ui()
        self._refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(11)

        title = QLabel("Офлайн-модель распознавания")
        title.setObjectName("SectionTitle")
        root.addWidget(title)

        description = QLabel(
            "Модель скачивается один раз. После установки распознавание работает "
            "полностью без интернета, аудиофайлы не покидают компьютер."
        )
        description.setObjectName("Muted")
        description.setWordWrap(True)
        root.addWidget(description)

        root.addWidget(QLabel("Модель"))
        self.combo = QComboBox()
        self.combo.setMinimumWidth(320)
        self.combo.currentIndexChanged.connect(self._update_detail)
        root.addWidget(self.combo)

        self.detail = QLabel()
        self.detail.setObjectName("Hint")
        self.detail.setWordWrap(True)
        root.addWidget(self.detail)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        root.addWidget(self.progress)

        self.status = QLabel("Готово к загрузке")
        self.status.setObjectName("Muted")
        self.status.setWordWrap(True)
        self.status.setMinimumHeight(36)
        root.addWidget(self.status)

        root.addStretch(1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.cancel_btn = QPushButton("Закрыть")
        self.cancel_btn.clicked.connect(self._on_cancel_clicked)
        self.download_btn = QPushButton("Скачать")
        self.download_btn.setObjectName("primary")
        self.download_btn.clicked.connect(self._on_download)
        buttons.addWidget(self.cancel_btn)
        buttons.addWidget(self.download_btn)
        root.addLayout(buttons)

    def _refresh(self) -> None:
        self.combo.blockSignals(True)
        self.combo.clear()
        for spec in CATALOG.values():
            installed = find_installed(spec.name) is not None
            suffix = " · уже установлена" if installed else f" · {human_size(spec.size)}"
            self.combo.addItem(f"{spec.title}{suffix}", spec.name)
        self.combo.blockSignals(False)
        self._update_detail()

    def _current_spec(self):
        name = self.combo.currentData()
        return CATALOG.get(str(name)) if name else None

    def _update_detail(self) -> None:
        spec = self._current_spec()
        if spec is None:
            self.detail.setText("")
            return
        installed = find_installed(spec.name)
        if installed is not None:
            self.detail.setText(f"Модель уже установлена: {installed}")
            self.download_btn.setText("Использовать")
        else:
            partial = default_models_dir() / f".download-{spec.name}"
            suffix = " Незавершённая загрузка будет продолжена." if partial.exists() else ""
            self.detail.setText(
                f"Размер: {human_size(spec.size)}. Папка установки: {default_models_dir()}.{suffix}"
            )
            self.download_btn.setText("Продолжить" if partial.exists() else "Скачать")

    def _on_download(self) -> None:
        spec = self._current_spec()
        if spec is None:
            return
        target = find_installed(spec.name)
        if target is not None:
            self.selected_path = str(target)
            self.accept()
            return
        self._set_busy(True)
        self.progress.setRange(0, 0)
        self.status.setStyleSheet("")
        self.status.setText("Подключение к серверу…")
        worker = DownloadWorker(spec, self)
        worker.progress.connect(self._on_progress)
        worker.succeeded.connect(self._on_succeeded)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(self._on_worker_finished)
        self._worker = worker
        worker.start()

    def _set_busy(self, busy: bool) -> None:
        self.combo.setEnabled(not busy)
        self.download_btn.setEnabled(not busy)
        self.cancel_btn.setText("Отменить загрузку" if busy else "Закрыть")
        self.cancel_btn.setEnabled(True)

    def _on_progress(self, downloaded: int, total: int) -> None:
        if total > 0:
            self.progress.setRange(0, 100)
            self.progress.setValue(min(100, int(downloaded * 100 / total)))
            self.status.setText(
                f"Скачано {human_size(downloaded)} из {human_size(total)}"
            )
        else:
            self.progress.setRange(0, 0)
            self.status.setText(f"Скачано {human_size(downloaded)}")

    def _on_succeeded(self, path: str) -> None:
        self._pending_path = path
        self.progress.setRange(0, 100)
        self.progress.setValue(100)
        self.status.setText("Модель установлена")

    def _on_failed(self, message: str) -> None:
        self._pending_path = None
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.status.setStyleSheet("color: #B91C1C;")
        self.status.setText(
            f"Не удалось скачать модель. {message}\n"
            "Повторите загрузку — она продолжится с места остановки. "
            "Можно также выбрать компактную модель."
        )
        self.status.setToolTip(message)

    def _on_worker_finished(self) -> None:
        self._worker = None
        self._set_busy(False)
        if self._pending_path:
            self.selected_path = self._pending_path
            self._pending_path = None
            self.accept()

    def _on_cancel_clicked(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
            self.status.setText("Отмена загрузки…")
            self.cancel_btn.setEnabled(False)
        else:
            self.reject()

    def reject(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            answer = QMessageBox.question(
                self,
                "Прервать загрузку?",
                "Модель ещё не установлена. Прервать загрузку?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return
            self._worker.cancel()
            self.status.setText("Отмена загрузки…")
            if not self._worker.wait(5000):
                QMessageBox.warning(
                    self,
                    "Загрузка",
                    "Не удалось остановить загрузку. Попробуйте ещё раз.",
                )
                return
            self._worker = None
        super().reject()

    def closeEvent(self, event) -> None:
        if self._worker is not None and self._worker.isRunning():
            event.ignore()
            self.reject()
        else:
            super().closeEvent(event)
