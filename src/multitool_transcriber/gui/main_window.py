from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from PyQt5.QtCore import QSettings, QSignalBlocker, QStandardPaths, Qt, QTime, QUrl
from PyQt5.QtGui import QBrush, QColor, QDesktopServices, QKeySequence
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QAction,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QProgressDialog,
    QPushButton,
    QScrollArea,
    QShortcut,
    QSplitter,
    QStackedWidget,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .. import APP_NAME, __version__
from ..audio import format_duration
from ..engine import Transcript
from ..files import collect_files, dialog_filter, is_supported
from ..models import (
    CATALOG,
    default_models_dir,
    discover_models,
    human_size,
    import_model_zip,
    is_vosk_model,
    model_size,
)
from ..outputs import capitalize_sentences, render_json, render_srt, render_txt, write_docx
from ..worker import TranscriptionWorker
from .download_dialog import DownloadDialog
from .icons import app_icon, icon_pixmap
from .style import apply_theme


@dataclass
class FileEntry:
    path: Path
    duration: float = 0.0
    status: str = "queued"
    progress: float = 0.0
    text: str = ""
    segments_text: str = ""
    partial: str = ""
    summary: str = ""
    summary_path: str = ""
    summary_error: str = ""
    error: str = ""
    outputs: dict[str, str] = field(default_factory=dict)
    transcript: Transcript | None = None
    bar: QProgressBar | None = None


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.entries: list[FileEntry] = []
        self.worker: TranscriptionWorker | None = None
        self._busy = False
        self._finished_count = 0
        self._current_fraction = 0.0
        self._fatal_message = ""
        self._follow_active = False
        self._settings = QSettings("Astra Transcribe", "Astra Transcribe")
        legacy_settings = QSettings("MultiTool", "Transcriber")
        if not self._settings.allKeys():
            for key in legacy_settings.allKeys():
                self._settings.setValue(key, legacy_settings.value(key))
        self.setWindowTitle(APP_NAME)
        screen = QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            initial_width = min(1240, max(760, available.width() - 16))
            initial_height = min(880, max(460, available.height() - 16))
        else:
            initial_width, initial_height = 1240, 880
        self.setMinimumSize(760, 460)
        self.resize(initial_width, initial_height)
        self.setAcceptDrops(True)
        self.setWindowIcon(app_icon())
        self._build_menu()
        self._build_ui()
        self._load_settings()
        self._refresh_models()
        self._update_empty_state()
        self._update_actions()

    def _build_menu(self) -> None:
        menu = self.menuBar()
        file_menu = menu.addMenu("Файл")
        add_action = QAction("Добавить файлы…", self)
        add_action.setShortcut(QKeySequence.Open)
        add_action.triggered.connect(self._choose_files)
        file_menu.addAction(add_action)
        open_output_action = QAction("Открыть папку результатов", self)
        open_output_action.triggered.connect(self._open_output_dir)
        file_menu.addAction(open_output_action)
        file_menu.addSeparator()
        exit_action = QAction("Выход", self)
        exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        models_menu = menu.addMenu("Модели")
        download_action = QAction("Скачать модель…", self)
        download_action.triggered.connect(self._open_download_dialog)
        models_menu.addAction(download_action)
        open_models_action = QAction("Открыть папку моделей", self)
        open_models_action.triggered.connect(self._open_models_folder)
        models_menu.addAction(open_models_action)

        help_menu = menu.addMenu("Справка")
        about_action = QAction("О программе", self)
        about_action.triggered.connect(self._about)
        help_menu.addAction(about_action)

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 14, 16, 12)
        root.setSpacing(12)
        root.addWidget(self._build_header())

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(12)
        self.splitter.addWidget(self._build_files_card())
        self.splitter.addWidget(self._build_settings_card())
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        split_width = max(900, self.width())
        self.splitter.setSizes([int(split_width * 0.64), int(split_width * 0.36)])
        root.addWidget(self.splitter, 1)
        root.addWidget(self._build_tabs())

        self.setCentralWidget(central)
        self._build_status_bar()
        self.subtitle_label.setVisible(self.width() >= 900)

        QShortcut(QKeySequence("Ctrl+Return"), self, activated=self._start)
        QShortcut(QKeySequence("Ctrl+Enter"), self, activated=self._start)
        QShortcut(QKeySequence("Delete"), self.table, activated=self._remove_selected)

    def _build_header(self) -> QWidget:
        header = QFrame()
        header.setObjectName("Header")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(18, 13, 18, 13)
        layout.setSpacing(14)

        logo_size = max(36, self.fontMetrics().height() * 2)
        logo = QLabel()
        logo.setPixmap(icon_pixmap(logo_size))
        logo.setFixedSize(logo_size, logo_size)

        titles = QVBoxLayout()
        titles.setSpacing(1)
        title = QLabel(APP_NAME)
        title.setObjectName("Title")
        self.subtitle_label = QLabel("Офлайн-распознавание речи · Vosk")
        self.subtitle_label.setObjectName("Subtitle")
        titles.addWidget(title)
        titles.addWidget(self.subtitle_label)

        self.theme_check = QCheckBox("Тёмная тема")
        self.theme_check.setObjectName("ThemeSwitch")
        self.theme_check.setToolTip("Переключить светлое и тёмное оформление")
        self.theme_check.toggled.connect(self._toggle_theme)

        self.model_chip = QLabel()
        self.model_chip.setObjectName("Chip")
        self._set_chip("Модель не выбрана", "warn")

        self.start_btn = QPushButton("Начать")
        self.start_btn.setObjectName("primary")
        self.start_btn.setMinimumHeight(max(36, self.fontMetrics().height() + 16))
        self.start_btn.setToolTip("Начать распознавание (Ctrl+Enter)")
        self.start_btn.clicked.connect(self._start)
        self.stop_btn = QPushButton("Стоп")
        self.stop_btn.setObjectName("danger")
        self.stop_btn.setMinimumHeight(max(34, self.fontMetrics().height() + 14))
        self.stop_btn.setToolTip("Остановить обработку")
        self.stop_btn.clicked.connect(self._stop)
        self.stop_btn.hide()

        layout.addWidget(logo)
        layout.addLayout(titles)
        layout.addStretch(1)
        layout.addWidget(self.theme_check, 0, Qt.AlignVCenter)
        layout.addWidget(self.model_chip, 0, Qt.AlignVCenter)
        layout.addWidget(self.start_btn, 0, Qt.AlignVCenter)
        layout.addWidget(self.stop_btn, 0, Qt.AlignVCenter)
        return header

    def _build_files_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(10)

        top = QHBoxLayout()
        top.setSpacing(8)
        section = QLabel("Файлы")
        section.setObjectName("SectionTitle")
        self.count_label = QLabel("0 файлов")
        self.count_label.setObjectName("Muted")
        top.addWidget(section)
        top.addWidget(self.count_label)
        top.addStretch(1)

        self.add_btn = QPushButton("Добавить файлы")
        self.add_btn.clicked.connect(self._choose_files)
        self.remove_btn = QPushButton("Удалить")
        self.remove_btn.clicked.connect(self._remove_selected)
        self.clear_btn = QPushButton("Очистить")
        self.clear_btn.clicked.connect(self._clear_files)
        top.addWidget(self.add_btn)
        top.addWidget(self.remove_btn)
        top.addWidget(self.clear_btn)
        layout.addLayout(top)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Файл", "Длительность", "Статус", "Прогресс"])
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setWordWrap(False)
        self.table.setTextElideMode(Qt.ElideMiddle)
        fm = self.fontMetrics()
        self.table.verticalHeader().setDefaultSectionSize(max(42, fm.height() + 22))
        self.table.setFrameShape(QFrame.NoFrame)
        header_view = self.table.horizontalHeader()
        header_view.setHighlightSections(False)
        header_view.setSectionResizeMode(0, QHeaderView.Stretch)
        header_view.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header_view.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header_view.setSectionResizeMode(3, QHeaderView.Fixed)
        self.table.setColumnWidth(3, 110)
        self.table.itemSelectionChanged.connect(self._show_selected)

        empty = QWidget()
        empty_layout = QVBoxLayout(empty)
        empty_layout.setContentsMargins(24, 24, 24, 24)
        empty_layout.setSpacing(8)
        empty_icon = QLabel()
        empty_icon.setPixmap(icon_pixmap(max(56, fm.height() * 4)))
        empty_icon.setAlignment(Qt.AlignCenter)
        empty_title = QLabel("Перетащите аудиофайлы сюда")
        empty_title.setObjectName("EmptyTitle")
        empty_title.setAlignment(Qt.AlignCenter)
        empty_subtitle = QLabel("MP3, WAV, OGG, FLAC, M4A, MP4 и другие форматы")
        empty_subtitle.setObjectName("Muted")
        empty_subtitle.setAlignment(Qt.AlignCenter)
        empty_button = QPushButton("Выбрать файлы")
        empty_button.setObjectName("primary")
        empty_button.setMinimumWidth(max(170, fm.horizontalAdvance("Выбрать файлы") + 40))
        empty_button.clicked.connect(self._choose_files)
        empty_layout.addStretch(1)
        empty_layout.addWidget(empty_icon, 0, Qt.AlignHCenter)
        empty_layout.addWidget(empty_title)
        empty_layout.addWidget(empty_subtitle)
        empty_layout.addSpacing(6)
        empty_layout.addWidget(empty_button, 0, Qt.AlignHCenter)
        empty_layout.addStretch(1)

        self.stack = QStackedWidget()
        self.stack.addWidget(empty)
        self.stack.addWidget(self.table)
        layout.addWidget(self.stack, 1)
        return card

    def _build_settings_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("Card")
        fm = self.fontMetrics()
        card.setMinimumWidth(330)
        card.setMaximumWidth(520)
        outer = QVBoxLayout(card)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.viewport().setAutoFillBackground(False)
        content = QWidget()
        content.setAutoFillBackground(False)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(14, 10, 14, 8)
        layout.setSpacing(4)

        model_label = QLabel("Модель")
        model_label.setObjectName("FieldLabel")
        layout.addWidget(model_label)
        self.model_combo = QComboBox()
        self.model_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.model_combo.setMinimumContentsLength(12)
        self.model_combo.setToolTip("Модель работает локально. Интернет нужен только для загрузки.")
        self.model_combo.currentIndexChanged.connect(self._on_model_changed)
        layout.addWidget(self.model_combo)
        model_buttons = QHBoxLayout()
        model_buttons.setSpacing(8)
        self.download_btn = QPushButton("Скачать…")
        self.download_btn.clicked.connect(self._open_download_dialog)
        self.browse_model_btn = QPushButton("Обзор…")
        self.browse_model_btn.clicked.connect(self._choose_model_folder)
        model_buttons.addWidget(self.download_btn)
        model_buttons.addWidget(self.browse_model_btn)
        model_buttons.addStretch(1)
        layout.addLayout(model_buttons)
        self.import_btn = QPushButton("Добавить ранее скачанную модель")
        self.import_btn.setToolTip("Импортировать модель Vosk из ZIP-архива")
        self.import_btn.clicked.connect(self._import_model_zip)
        layout.addWidget(self.import_btn)
        layout.addSpacing(4)

        formats_label = QLabel("Формат результата")
        formats_label.setObjectName("FieldLabel")
        layout.addWidget(formats_label)
        formats_row = QHBoxLayout()
        formats_row.setSpacing(6)
        self.format_combo = QComboBox()
        self.format_combo.addItem("TXT — текст", "txt")
        self.format_combo.addItem("DOCX — Word", "docx")
        self.format_combo.addItem("SRT — субтитры", "srt")
        self.format_combo.addItem("JSON — данные", "json")
        self.format_combo.currentIndexChanged.connect(self._update_download_action)
        self.download_result_btn = QPushButton("Скачать")
        self.download_result_btn.setToolTip("Сохранить готовый результат в выбранном формате")
        self.download_result_btn.clicked.connect(self._download_result)
        self.download_result_btn.setEnabled(False)
        formats_row.addWidget(self.format_combo, 1)
        formats_row.addWidget(self.download_result_btn)
        layout.addLayout(formats_row)
        layout.addSpacing(6)

        output_label = QLabel("Папка для файлов")
        output_label.setObjectName("FieldLabel")
        layout.addWidget(output_label)
        output_row = QHBoxLayout()
        output_row.setSpacing(6)
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("Папка для сохранения")
        self.output_browse_btn = QPushButton("…")
        self.output_browse_btn.setFixedWidth(max(34, fm.horizontalAdvance("…") + 24))
        self.output_browse_btn.clicked.connect(self._choose_output_dir)
        output_row.addWidget(self.output_edit, 1)
        output_row.addWidget(self.output_browse_btn)
        layout.addLayout(output_row)
        layout.addSpacing(6)

        self.capitalize_check = QCheckBox("Заглавные буквы в начале фраз")
        self.capitalize_check.setChecked(True)
        self.overwrite_check = QCheckBox("Перезаписывать готовые файлы")
        self.overwrite_check.setChecked(True)
        layout.addWidget(self.capitalize_check)
        layout.addWidget(self.overwrite_check)
        layout.addStretch(1)

        scroll.setWidget(content)
        outer.addWidget(scroll, 1)
        return card

    def _build_tabs(self) -> QWidget:
        self.tabs = QTabWidget()
        self.tabs.setMinimumHeight(112 if self.height() < 620 else 140)
        self.transcript_view = QPlainTextEdit()
        self.transcript_view.setReadOnly(True)
        self.transcript_view.setUndoRedoEnabled(False)
        self.transcript_view.setPlaceholderText("Здесь появится распознанный текст…")
        self.summary_view = QPlainTextEdit()
        self.summary_view.setReadOnly(True)
        self.summary_view.setUndoRedoEnabled(False)
        self.summary_view.setPlaceholderText("Здесь появится краткое содержание…")
        self.log_view = QPlainTextEdit()
        self.log_view.setObjectName("LogView")
        self.log_view.setReadOnly(True)
        self.log_view.setUndoRedoEnabled(False)
        self.log_view.setMaximumBlockCount(1000)
        self.log_view.setPlaceholderText("Журнал событий")
        self.tabs.addTab(self.transcript_view, "Транскрипт")
        self.tabs.addTab(self.summary_view, "Саммари")
        self.tabs.addTab(self.log_view, "Журнал")
        return self.tabs

    def _build_status_bar(self) -> None:
        bar = self.statusBar()
        bar.setSizeGripEnabled(False)
        self.status_label = QLabel("Готов к работе")
        bar.addWidget(self.status_label, 1)
        self.overall = QProgressBar()
        self.overall.setObjectName("OverallProgress")
        self.overall.setRange(0, 100)
        self.overall.setValue(0)
        self.overall.setTextVisible(True)
        fm = self.fontMetrics()
        self.overall.setMinimumWidth(max(150, fm.horizontalAdvance("100%") + 80))
        self.overall.setMaximumWidth(240)
        bar.addPermanentWidget(self.overall)

    def _load_settings(self) -> None:
        geometry = self._settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        output = self._settings.value("output_dir", "")
        if not output:
            documents = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
            base = Path(documents) if documents else Path.home() / "Documents"
            output = str(base / "Транскрипты")
        self.output_edit.setText(str(output))
        self.output_edit.setToolTip(str(output))
        self.output_edit.setCursorPosition(0)
        formats_value = str(self._settings.value("formats_v2", "txt,docx"))
        formats = [item.strip().lower() for item in formats_value.split(",") if item.strip()]
        selected = next(
            (item for item in formats if item in {"txt", "docx", "srt", "json"}),
            "txt",
        )
        index = self.format_combo.findData(selected)
        if index >= 0:
            self.format_combo.setCurrentIndex(index)
        self.capitalize_check.setChecked(self._as_bool(self._settings.value("capitalize", True), True))
        self.overwrite_check.setChecked(self._as_bool(self._settings.value("overwrite", True), True))
        self._saved_model = str(self._settings.value("model_path", "") or "")
        dark = self._as_bool(self._settings.value("dark_theme", False), False)
        self.theme_check.blockSignals(True)
        self.theme_check.setChecked(dark)
        self.theme_check.blockSignals(False)
        if dark:
            application = QApplication.instance()
            if application is not None:
                apply_theme(application, True)

    def _save_settings(self) -> None:
        self._settings.setValue("geometry", self.saveGeometry())
        self._settings.setValue("output_dir", self.output_edit.text().strip())
        self._settings.setValue("formats_v2", str(self.format_combo.currentData() or "txt"))
        self._settings.setValue("capitalize", self.capitalize_check.isChecked())
        self._settings.setValue("overwrite", self.overwrite_check.isChecked())
        self._settings.setValue("dark_theme", self.theme_check.isChecked())
        data = self.model_combo.currentData()
        if data:
            self._settings.setValue("model_path", str(data))

    def _toggle_theme(self, checked: bool) -> None:
        self._settings.setValue("dark_theme", checked)
        application = QApplication.instance()
        if application is not None:
            apply_theme(application, checked)

    @staticmethod
    def _as_bool(value, default: bool) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return default
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def _refresh_models(self, preferred: str | None = None, extra_dirs=()) -> None:
        current = preferred or self._saved_model or self.model_combo.currentData()
        models = discover_models(extra_dirs)
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        for info in models:
            try:
                path = str(info.path.resolve())
            except OSError:
                path = str(info.path)
            size = CATALOG[info.name].size if info.name in CATALOG else info.size
            index = self.model_combo.count()
            self.model_combo.addItem(info.title, path)
            self.model_combo.setItemData(
                index,
                f"{info.title} · {human_size(size)}",
                Qt.ToolTipRole,
            )
        for candidate in (preferred, self._saved_model):
            if not candidate:
                continue
            path = Path(str(candidate)).expanduser()
            if not is_vosk_model(path):
                continue
            try:
                resolved = str(path.resolve())
            except OSError:
                resolved = str(path)
            if self.model_combo.findData(resolved) < 0:
                index = self.model_combo.count()
                self.model_combo.addItem(path.name, resolved)
                self.model_combo.setItemData(
                    index,
                    f"{path.name} · {human_size(model_size(path))}",
                    Qt.ToolTipRole,
                )
        if self.model_combo.count() == 0:
            self.model_combo.addItem("Модель не найдена — скачайте русскую модель", "")
        target = str(current) if current else ""
        index = self.model_combo.findData(target) if target else -1
        if index < 0:
            index = 0
        self.model_combo.setCurrentIndex(index)
        self.model_combo.blockSignals(False)
        self._on_model_changed()

    def _on_model_changed(self) -> None:
        data = self.model_combo.currentData()
        if data:
            self._settings.setValue("model_path", str(data))
            self._saved_model = str(data)
            self.model_combo.setToolTip(str(data))
        else:
            self.model_combo.setToolTip("")
        self._update_model_chip()
        self._update_actions()

    def _selected_model(self) -> Path | None:
        data = self.model_combo.currentData()
        if not data:
            return None
        path = Path(str(data))
        return path if is_vosk_model(path) else None

    def _update_model_chip(self) -> None:
        if self._selected_model() is not None:
            self._set_chip("Модель готова", "ok")
        else:
            self._set_chip("Модель не найдена", "warn")

    def _set_chip(self, text: str, state: str) -> None:
        self.model_chip.setText(text)
        self.model_chip.setProperty("state", state)
        style = self.model_chip.style()
        style.unpolish(self.model_chip)
        style.polish(self.model_chip)
        self.model_chip.update()

    def _update_actions(self) -> None:
        has_files = bool(self.entries)
        model_ready = self._selected_model() is not None
        self.start_btn.setEnabled(not self._busy and has_files and model_ready)
        self.add_btn.setEnabled(not self._busy)
        self.remove_btn.setEnabled(not self._busy and has_files)
        self.clear_btn.setEnabled(not self._busy and has_files)
        if not has_files:
            tip = "Сначала добавьте аудиофайлы"
        elif not model_ready:
            tip = "Выберите или скачайте модель"
        else:
            tip = "Ctrl+Enter"
        self.start_btn.setToolTip(tip)
        self._update_download_action()

    def _update_download_action(self) -> None:
        row = self.table.currentRow()
        entry = self.entries[row] if 0 <= row < len(self.entries) else None
        fmt = str(self.format_combo.currentData() or "")
        ready = bool(
            not self._busy
            and entry is not None
            and entry.status == "done"
            and entry.transcript is not None
            and fmt
        )
        self.download_result_btn.setEnabled(ready)
        if ready:
            tip = f"Сохранить результат в {fmt.upper()}"
        elif self._busy:
            tip = "Дождитесь завершения обработки"
        elif entry is None:
            tip = "Выберите готовый файл"
        elif entry.status != "done":
            tip = "Результат ещё не готов"
        else:
            tip = "Нет данных для сохранения"
        self.download_result_btn.setToolTip(tip)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        controls = [
            self.add_btn,
            self.remove_btn,
            self.clear_btn,
            self.model_combo,
            self.download_btn,
            self.browse_model_btn,
            self.import_btn,
            self.output_edit,
            self.output_browse_btn,
            self.format_combo,
            self.download_result_btn,
            self.capitalize_check,
            self.overwrite_check,
        ]
        for widget in controls:
            widget.setEnabled(not busy)
        self.start_btn.setVisible(not busy)
        self.stop_btn.setVisible(busy)
        self.stop_btn.setEnabled(busy)
        self._update_actions()

    def _choose_files(self) -> None:
        start_dir = str(self._settings.value("last_input_dir", str(Path.home())))
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Добавить аудиофайлы",
            start_dir,
            dialog_filter(),
        )
        if paths:
            self._settings.setValue("last_input_dir", str(Path(paths[0]).parent))
            self.add_files(paths)

    def add_files(self, paths) -> None:
        if self._busy:
            return
        files = collect_files(paths)
        if not files:
            self._set_status("Поддерживаемые файлы не найдены")
            return
        existing: set[Path] = set()
        for entry in self.entries:
            try:
                existing.add(entry.path.resolve())
            except OSError:
                existing.add(entry.path)
        added = 0
        for path in files:
            try:
                resolved = path.resolve()
            except OSError:
                resolved = path
            if resolved in existing:
                continue
            existing.add(resolved)
            entry = FileEntry(path=path)
            self.entries.append(entry)
            self._append_row(entry)
            added += 1
        if not added:
            self._set_status("Эти файлы уже в очереди")
            return
        self._update_empty_state()
        self.table.selectRow(len(self.entries) - 1)
        self._update_actions()
        self._set_status(f"Добавлено файлов: {added}")
        self._log(f"Добавлено файлов: {added}")

    def _append_row(self, entry: FileEntry) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)

        name_item = QTableWidgetItem(entry.path.name)
        name_item.setData(Qt.UserRole, str(entry.path))
        name_item.setToolTip(str(entry.path))
        name_item.setIcon(self.style().standardIcon(QStyle.SP_FileIcon))
        duration_item = QTableWidgetItem("—")
        duration_item.setTextAlignment(Qt.AlignCenter)
        status_item = QTableWidgetItem("В очереди")
        status_item.setForeground(QBrush(QColor("#6B7280")))
        status_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)

        holder = QWidget()
        holder_layout = QHBoxLayout(holder)
        holder_layout.setContentsMargins(8, 0, 10, 0)
        bar = QProgressBar()
        bar.setObjectName("RowProgress")
        bar.setRange(0, 1000)
        bar.setValue(0)
        bar.setTextVisible(False)
        bar.setFixedHeight(max(6, self.fontMetrics().height() // 2))
        holder_layout.addWidget(bar)
        entry.bar = bar

        self.table.setItem(row, 0, name_item)
        self.table.setItem(row, 1, duration_item)
        self.table.setItem(row, 2, status_item)
        self.table.setCellWidget(row, 3, holder)

    def _update_empty_state(self) -> None:
        self.stack.setCurrentIndex(1 if self.entries else 0)
        count = len(self.entries)
        self.count_label.setText(f"{count} {self._plural_files(count)}")

    @staticmethod
    def _plural_files(count: int) -> str:
        if count % 10 == 1 and count % 100 != 11:
            return "файл"
        if 2 <= count % 10 <= 4 and not 12 <= count % 100 <= 14:
            return "файла"
        return "файлов"

    def _remove_selected(self) -> None:
        if self._busy:
            return
        rows = sorted(
            {index.row() for index in self.table.selectionModel().selectedRows()},
            reverse=True,
        )
        if not rows:
            return
        for row in rows:
            if 0 <= row < len(self.entries):
                self.table.removeRow(row)
                del self.entries[row]
        self._update_empty_state()
        if self.entries and self.table.currentRow() < 0:
            self.table.selectRow(0)
        elif not self.entries:
            self._set_transcript_text("")
        self._update_actions()
        self._set_status(f"Удалено файлов: {len(rows)}")

    def _clear_files(self) -> None:
        if self._busy or not self.entries:
            return
        self.table.setRowCount(0)
        self.entries.clear()
        self._set_transcript_text("")
        self._update_empty_state()
        self._update_actions()
        self._set_status("Очередь очищена")

    def _selected_formats(self) -> list[str]:
        value = str(self.format_combo.currentData() or "")
        return [value] if value in {"txt", "docx", "srt", "json"} else []

    def _download_result(self) -> None:
        row = self.table.currentRow()
        if not 0 <= row < len(self.entries):
            return
        entry = self.entries[row]
        fmt = str(self.format_combo.currentData() or "")
        transcript = entry.transcript
        if entry.status != "done" or transcript is None or not fmt:
            QMessageBox.information(
                self,
                "Скачать результат",
                "Сначала завершите распознавание файла.",
            )
            return
        output_text = self.output_edit.text().strip()
        if output_text:
            base = Path(output_text).expanduser()
        else:
            documents = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
            base = Path(documents) if documents else Path.home() / "Documents"
        filters = {
            "txt": "Текст (*.txt)",
            "docx": "Документ Word (*.docx)",
            "srt": "Субтитры (*.srt)",
            "json": "JSON (*.json)",
        }
        target, _ = QFileDialog.getSaveFileName(
            self,
            "Скачать результат",
            str(base / f"{entry.path.stem}.{fmt}"),
            filters[fmt],
        )
        if not target:
            return
        path = Path(target)
        if path.suffix.lower() != f".{fmt}":
            path = path.with_suffix(f".{fmt}")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            capitalize = self.capitalize_check.isChecked()
            if fmt == "docx":
                write_docx(transcript, path, capitalize=capitalize)
            elif fmt == "txt":
                path.write_text(
                    render_txt(transcript, capitalize=capitalize),
                    encoding="utf-8",
                )
            elif fmt == "srt":
                path.write_text(
                    render_srt(transcript, capitalize=capitalize),
                    encoding="utf-8",
                )
            else:
                path.write_text(
                    render_json(transcript, capitalize=capitalize),
                    encoding="utf-8",
                )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Скачать результат",
                f"Не удалось сохранить файл.\n\n{exc}",
            )
            return
        self._set_status(f"Сохранено: {path.name}")
        self._log(f"Результат сохранён: {path}")

    def _choose_output_dir(self) -> None:
        start = self.output_edit.text().strip() or str(Path.home())
        folder = QFileDialog.getExistingDirectory(self, "Папка для результатов", start)
        if folder:
            self.output_edit.setText(folder)
            self.output_edit.setToolTip(folder)
            self.output_edit.setCursorPosition(0)
            self._settings.setValue("output_dir", folder)

    def _open_output_dir(self) -> None:
        text = self.output_edit.text().strip()
        if text:
            path = Path(text).expanduser()
        else:
            documents = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
            base = Path(documents) if documents else Path.home() / "Documents"
            path = base / "Транскрипты"
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            QMessageBox.warning(self, "Папка результатов", f"Не удалось создать папку: {exc}")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _open_models_folder(self) -> None:
        path = default_models_dir()
        path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _open_download_dialog(self) -> None:
        dialog = DownloadDialog(self)
        if dialog.exec_() == QDialog.Accepted and dialog.selected_path:
            self._refresh_models(preferred=dialog.selected_path)
            self._log(f"Модель установлена: {Path(dialog.selected_path).name}")

    def _choose_model_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self,
            "Папка с моделью Vosk",
            str(default_models_dir()),
        )
        if not folder:
            return
        path = Path(folder)
        if not is_vosk_model(path):
            QMessageBox.warning(
                self,
                "Не модель Vosk",
                "В выбранной папке нет модели Vosk. Ожидаются файлы am/final.mdl и conf/model.conf.",
            )
            return
        self._refresh_models(preferred=str(path), extra_dirs=[path.parent])
        self._log(f"Выбрана модель: {path.name}")

    def _import_model_zip(self) -> None:
        if self._busy:
            return
        archive, _ = QFileDialog.getOpenFileName(
            self,
            "Добавить ранее скачанную модель",
            str(Path.home()),
            "Модель Vosk (*.zip);;Все файлы (*)",
        )
        if not archive:
            return
        progress = QProgressDialog("Проверка архива…", None, 0, 0, self)
        progress.setWindowTitle("Импорт модели")
        progress.setWindowModality(Qt.WindowModal)
        progress.setCancelButton(None)
        progress.setMinimumDuration(0)
        progress.show()
        QApplication.processEvents()

        def report(text: str) -> None:
            progress.setLabelText(f"Импорт модели: {text}")
            QApplication.processEvents()

        try:
            path = import_model_zip(archive, progress=report)
        except Exception as exc:
            progress.close()
            self._log(f"Импорт модели не выполнен: {exc}")
            QMessageBox.critical(
                self,
                "Импорт модели",
                f"Не удалось добавить модель.\n\n{exc}",
            )
            return
        progress.close()
        self._refresh_models(preferred=str(path))
        self._set_status(f"Модель добавлена: {path.name}")
        self._log(f"Модель добавлена из ZIP: {path}")

    def _start(self) -> None:
        if self._busy:
            return
        if self.worker is not None and self.worker.isRunning():
            return
        if not self.entries:
            QMessageBox.information(
                self,
                "Нет файлов",
                "Добавьте аудиофайлы для распознавания.",
            )
            return
        model = self._selected_model()
        if model is None:
            answer = QMessageBox.question(
                self,
                "Модель не найдена",
                "Скачать компактную русскую модель (около 45 МБ) сейчас?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if answer == QMessageBox.Yes:
                self._open_download_dialog()
            return
        formats = self._selected_formats()
        if not formats:
            QMessageBox.warning(
                self,
                "Форматы",
                "Выберите хотя бы один формат результата.",
            )
            return
        output_text = self.output_edit.text().strip()
        if not output_text:
            QMessageBox.warning(
                self,
                "Папка результатов",
                "Укажите папку для сохранения результатов.",
            )
            return
        output_dir = Path(output_text).expanduser()
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            QMessageBox.critical(
                self,
                "Папка результатов",
                f"Не удалось создать папку: {exc}",
            )
            return
        if not os.access(str(output_dir), os.W_OK):
            QMessageBox.critical(
                self,
                "Папка результатов",
                "Нет прав на запись в выбранную папку.",
            )
            return
        self._settings.setValue("output_dir", str(output_dir))
        self._save_settings()
        self._reset_entries()
        self._finished_count = 0
        self._current_fraction = 0.0
        self._fatal_message = ""
        self._follow_active = True
        self.overall.setRange(0, 100)
        self.overall.setValue(0)
        lowercase = model.name.lower()
        language = "en" if "-en" in lowercase else "ru"
        worker = TranscriptionWorker(
            files=[entry.path for entry in self.entries],
            model_path=model,
            output_dir=output_dir,
            formats=formats,
            capitalize=self.capitalize_check.isChecked(),
            overwrite=self.overwrite_check.isChecked(),
            language=language,
        )
        worker.file_started.connect(self._on_file_started)
        worker.file_progress.connect(self._on_progress)
        worker.file_segment.connect(self._on_segment)
        worker.file_partial.connect(self._on_partial)
        worker.file_finished.connect(self._on_file_finished)
        worker.file_failed.connect(self._on_file_failed)
        worker.fatal.connect(self._on_fatal)
        worker.all_finished.connect(self._on_all_finished)
        worker.finished.connect(self._on_worker_finished)
        self.worker = worker
        self._set_busy(True)
        self._set_status("Загрузка модели…")
        self._log(f"Модель: {model.name}")
        self._log(f"Файлов в очереди: {len(self.entries)}")
        worker.start()

    def _reset_entries(self) -> None:
        self._set_transcript_text("")
        self._set_summary_text("")
        for row, entry in enumerate(self.entries):
            entry.duration = 0.0
            entry.status = "queued"
            entry.progress = 0.0
            entry.text = ""
            entry.segments_text = ""
            entry.partial = ""
            entry.summary = ""
            entry.summary_path = ""
            entry.summary_error = ""
            entry.error = ""
            entry.outputs = {}
            entry.transcript = None
            duration_item = self.table.item(row, 1)
            if duration_item is not None:
                duration_item.setText("—")
            status_item = self.table.item(row, 2)
            if status_item is not None:
                status_item.setText("В очереди")
                status_item.setForeground(QBrush(QColor("#6B7280")))
                status_item.setToolTip("")
            if entry.bar is not None:
                entry.bar.setStyleSheet("")
                entry.bar.setRange(0, 1000)
                entry.bar.setValue(0)

    def _stop(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            self.worker.cancel()
            self.stop_btn.setEnabled(False)
            self._set_status("Останавливаю…")

    def _on_file_started(self, index: int, duration: float) -> None:
        if not 0 <= index < len(self.entries):
            return
        if self._follow_active and self.table.currentRow() != index:
            blocker = QSignalBlocker(self.table)
            self.table.selectRow(index)
            del blocker
            self._display_entry(index)
            self._update_download_action()
        entry = self.entries[index]
        entry.status = "running"
        entry.duration = duration
        duration_item = self.table.item(index, 1)
        if duration_item is not None:
            duration_item.setText(format_duration(duration) if duration else "—")
        self._set_row_status(index, "В работе", "#2F5FE0")
        if entry.bar is not None:
            entry.bar.setRange(0, 1000)
            entry.bar.setValue(0)
        self._current_fraction = 0.0
        self._set_status(f"Распознавание: {entry.path.name}")
        self._log(f"Старт: {entry.path.name}")

    def _on_progress(self, index: int, fraction: float) -> None:
        if not 0 <= index < len(self.entries):
            return
        entry = self.entries[index]
        if fraction < 0:
            if entry.bar is not None:
                entry.bar.setRange(0, 0)
            self._set_row_status(index, "В работе", "#2F5FE0")
            self._current_fraction = 0.0
        else:
            value = max(0.0, min(1.0, fraction))
            entry.progress = value
            if entry.bar is not None:
                entry.bar.setRange(0, 1000)
                entry.bar.setValue(int(value * 1000))
            self._set_row_status(index, f"{int(value * 100)}%", "#2F5FE0")
            self._current_fraction = value
        self._update_overall()

    def _update_overall(self) -> None:
        total = len(self.entries)
        if total == 0:
            return
        value = int(((self._finished_count + self._current_fraction) / total) * 100)
        self.overall.setValue(max(0, min(100, value)))

    def _on_segment(self, index: int, text: str) -> None:
        if not 0 <= index < len(self.entries):
            return
        entry = self.entries[index]
        if entry.segments_text:
            entry.segments_text = (entry.segments_text + "\n\n" + text).strip()
        else:
            entry.segments_text = text.strip()
        entry.partial = ""
        if self.table.currentRow() == index:
            self._render_live(index)

    def _on_partial(self, index: int, text: str) -> None:
        if not 0 <= index < len(self.entries):
            return
        entry = self.entries[index]
        entry.partial = text.strip()
        if self.table.currentRow() == index:
            self._render_live(index)

    def _render_live(self, index: int) -> None:
        if not 0 <= index < len(self.entries):
            return
        entry = self.entries[index]
        text = entry.segments_text
        if entry.partial:
            text = (text + "\n\n" + entry.partial).strip() if text else entry.partial
        if self.capitalize_check.isChecked():
            text = capitalize_sentences(text)
        self._set_transcript_text(text)

    def _on_file_finished(self, index: int, result) -> None:
        if not 0 <= index < len(self.entries):
            return
        entry = self.entries[index]
        entry.status = "done"
        entry.progress = 1.0
        entry.text = str(result.get("text", ""))
        entry.transcript = result.get("transcript")
        entry.outputs = result.get("outputs", {}) or {}
        entry.summary = str(result.get("summary", ""))
        entry.summary_path = str(result.get("summary_path", "") or "")
        entry.summary_error = str(result.get("summary_error", "") or "")
        if entry.bar is not None:
            entry.bar.setStyleSheet("")
            entry.bar.setRange(0, 1000)
            entry.bar.setValue(1000)
        saved = list(entry.outputs.values())
        if entry.summary_path:
            saved.append(entry.summary_path)
        names = ", ".join(Path(item).name for item in saved)
        self._set_row_status(index, "Готово", "#15803D", names)
        self._finished_count += 1
        self._current_fraction = 0.0
        self._update_overall()
        if self.table.currentRow() == index:
            self._display_entry(index)
        self._update_download_action()
        suffix = f" → {names}" if names else ""
        self._log(f"{entry.path.name}: готово{suffix}")
        if entry.summary_error:
            self._log(f"{entry.path.name}: саммари не создано — {entry.summary_error}")

    def _on_file_failed(self, index: int, message: str) -> None:
        if not 0 <= index < len(self.entries):
            return
        entry = self.entries[index]
        entry.status = "error"
        entry.error = message
        entry.progress = 0.0
        if entry.bar is not None:
            entry.bar.setStyleSheet(
                "QProgressBar::chunk { background: #D64545; border-radius: 4px; }"
            )
            entry.bar.setRange(0, 1000)
            entry.bar.setValue(0)
        self._set_row_status(index, "Ошибка", "#B91C1C", message)
        self._finished_count += 1
        self._current_fraction = 0.0
        self._update_overall()
        if self.table.currentRow() == index:
            self._display_entry(index)
        self._update_download_action()
        self._log(f"{entry.path.name}: ошибка — {message}")

    def _on_all_finished(self, succeeded: int, failed: int, cancelled: bool) -> None:
        self._follow_active = False
        self._set_busy(False)
        if self._fatal_message:
            self._fatal_message = ""
            self.overall.setValue(0)
            return
        total = succeeded + failed
        if cancelled:
            self._set_status("Остановлено")
            self._log("Работа остановлена")
            return
        message = f"Готово: {succeeded} из {total}"
        if failed:
            message += f", ошибок: {failed}"
        if total > 1:
            message += ". Выберите файл в очереди, чтобы посмотреть результат."
        self._set_status(message)
        self.overall.setValue(100 if total else 0)
        self._log(f"Завершено: успешно {succeeded}, ошибок {failed}")

    def _on_fatal(self, message: str) -> None:
        self._fatal_message = message
        self._set_status("Ошибка модели")
        self._log(f"Ошибка: {message}")
        QMessageBox.critical(self, "Ошибка модели", message)

    def _on_worker_finished(self) -> None:
        self.worker = None
        self._update_actions()

    def _show_selected(self) -> None:
        if self._busy:
            self._follow_active = False
        row = self.table.currentRow()
        if 0 <= row < len(self.entries):
            self._display_entry(row)
        else:
            self._set_transcript_text("")
        self._update_download_action()

    def _display_entry(self, index: int) -> None:
        if not 0 <= index < len(self.entries):
            return
        entry = self.entries[index]
        if entry.text:
            self._set_transcript_text(entry.text)
        elif entry.error:
            self._set_transcript_text("Не удалось распознать файл.\n\n" + entry.error)
        elif entry.status == "done":
            self._set_transcript_text("Речь не распознана.")
        elif entry.segments_text or entry.partial:
            self._render_live(index)
        else:
            self._set_transcript_text("")
        summary = entry.summary
        if entry.summary_error:
            summary = "Не удалось сформировать саммари.\n\n" + entry.summary_error
        elif entry.status == "done" and not summary:
            summary = "Речь не распознана."
        self._set_summary_text(summary)

    def _set_transcript_text(self, text: str) -> None:
        scroll = self.transcript_view.verticalScrollBar()
        at_bottom = scroll.value() >= scroll.maximum() - 4
        position = scroll.value()
        self.transcript_view.setPlainText(text)
        scroll.setValue(scroll.maximum() if at_bottom else min(position, scroll.maximum()))

    def _set_summary_text(self, text: str) -> None:
        scroll = self.summary_view.verticalScrollBar()
        at_bottom = scroll.value() >= scroll.maximum() - 4
        position = scroll.value()
        self.summary_view.setPlainText(text)
        scroll.setValue(scroll.maximum() if at_bottom else min(position, scroll.maximum()))

    def _set_row_status(self, index: int, text: str, color: str, tooltip: str = "") -> None:
        item = self.table.item(index, 2)
        if item is None:
            return
        item.setText(text)
        item.setForeground(QBrush(QColor(color)))
        item.setToolTip(tooltip)

    def _set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def _log(self, text: str) -> None:
        timestamp = QTime.currentTime().toString("HH:mm:ss")
        self.log_view.appendPlainText(f"{timestamp}  {text}")

    def _about(self) -> None:
        model = self._selected_model()
        model_name = model.name if model else "не выбрана"
        QMessageBox.about(
            self,
            "О программе",
            (
                f"<b>{APP_NAME}</b> {__version__}<br><br>"
                "Офлайн-распознавание речи на базе Vosk.<br>"
                "Аудиофайлы обрабатываются только на этом компьютере.<br><br>"
                f"Модель: {model_name}"
            ),
        )

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if not url.isLocalFile():
                    continue
                path = Path(url.toLocalFile())
                if path.is_dir() or is_supported(path):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event) -> None:
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        if paths:
            self.add_files(paths)
            event.acceptProposedAction()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "subtitle_label"):
            self.subtitle_label.setVisible(self.width() >= 900)
        if hasattr(self, "tabs"):
            self.tabs.setMinimumHeight(112 if self.height() < 620 else 140)

    def closeEvent(self, event) -> None:
        self._save_settings()
        if self.worker is not None and self.worker.isRunning():
            answer = QMessageBox.question(
                self,
                "Остановить распознавание?",
                "Идёт обработка файлов. Остановить и выйти?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                event.ignore()
                return
            self.worker.cancel()
            if not self.worker.wait(8000):
                QMessageBox.warning(
                    self,
                    "Остановка",
                    "Не удалось корректно остановить обработку. Попробуйте ещё раз.",
                )
                event.ignore()
                return
        event.accept()
