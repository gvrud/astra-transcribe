from __future__ import annotations

from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtWidgets import QApplication

APP_QSS = """
QWidget {
    color: #1B2333;
}
QMainWindow, QDialog {
    background: #F3F5FA;
}
QFrame#Header {
    background: #FFFFFF;
    border: 1px solid #E1E7F0;
    border-radius: 12px;
}
QFrame#Card {
    background: #FFFFFF;
    border: 1px solid #E1E7F0;
    border-radius: 12px;
}
QLabel#Title {
    font-size: 17pt;
    font-weight: 600;
    color: #16213A;
}
QLabel#Subtitle {
    color: #6B7280;
    font-size: 9.5pt;
}
QLabel#SectionTitle {
    font-size: 11.5pt;
    font-weight: 600;
    color: #16213A;
}
QLabel#FieldLabel {
    color: #6B7280;
    font-size: 9.5pt;
    font-weight: 600;
}
QLabel#Muted {
    color: #6B7280;
}
QLabel#Hint {
    color: #8A93A6;
    font-size: 9pt;
}
QLabel#EmptyTitle {
    font-size: 13pt;
    font-weight: 600;
    color: #27324A;
}
QLabel#Chip {
    border-radius: 11px;
    padding: 5px 11px;
    font-size: 9pt;
    font-weight: 600;
}
QLabel#Chip[state="ok"] {
    background: #E8F5EC;
    color: #15803D;
}
QLabel#Chip[state="warn"] {
    background: #FFF3E0;
    color: #B45309;
}
QGroupBox {
    background: #F8FAFD;
    border: 1px solid #E6EBF4;
    border-radius: 10px;
    margin-top: 14px;
    padding: 15px 12px 12px 12px;
    font-weight: 600;
    color: #27324A;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    top: 2px;
    padding: 0 4px;
    background: #F8FAFD;
    color: #6B7280;
    font-size: 9pt;
    font-weight: 600;
}
QPushButton {
    background: #FFFFFF;
    border: 1px solid #D6DEEC;
    border-radius: 8px;
    padding: 7px 13px;
    color: #1B2333;
}
QPushButton:hover {
    background: #F3F7FE;
    border-color: #B9C8E4;
}
QPushButton:pressed {
    background: #E8EFFB;
}
QPushButton:disabled {
    color: #A2AABC;
    background: #F7F9FC;
    border-color: #E7ECF5;
}
QPushButton#primary {
    background: #2F5FE0;
    border: 1px solid #2F5FE0;
    color: #FFFFFF;
    font-weight: 600;
}
QPushButton#primary:hover {
    background: #2854C9;
    border-color: #2854C9;
}
QPushButton#primary:pressed {
    background: #2147AE;
}
QPushButton#primary:disabled {
    background: #B9C8EE;
    border-color: #B9C8EE;
    color: #F4F6FF;
}
QPushButton#danger {
    color: #B91C1C;
    border-color: #EFCACA;
    background: #FFFFFF;
}
QPushButton#danger:hover {
    background: #FDF3F3;
}
QPushButton#link {
    border: none;
    background: transparent;
    color: #2F5FE0;
    padding: 4px 6px;
    text-align: left;
}
QPushButton#link:hover {
    color: #2147AE;
    text-decoration: underline;
}
QLineEdit, QComboBox {
    background: #FFFFFF;
    border: 1px solid #D6DEEC;
    border-radius: 8px;
    padding: 6px 9px;
    selection-background-color: #CFE0FF;
}
QLineEdit:focus, QComboBox:focus {
    border-color: #2F5FE0;
}
QLineEdit:disabled, QComboBox:disabled {
    background: #F7F9FC;
    color: #A2AABC;
}
QComboBox::drop-down {
    border: none;
    width: 22px;
}
QComboBox QAbstractItemView {
    background: #FFFFFF;
    border: 1px solid #D6DEEC;
    border-radius: 8px;
    padding: 4px;
    selection-background-color: #EAF0FD;
    selection-color: #1B2333;
    outline: none;
}
QCheckBox {
    spacing: 7px;
    color: #27324A;
}
QCheckBox:disabled {
    color: #A2AABC;
}
QCheckBox#ThemeSwitch {
    color: #6B7280;
    font-size: 9pt;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #C9D3E3;
    border-radius: 4px;
    background: #FFFFFF;
}
QCheckBox::indicator:hover {
    border-color: #2F5FE0;
}
QCheckBox::indicator:checked {
    background: #2F5FE0;
    border-color: #2F5FE0;
}
QCheckBox::indicator:disabled {
    background: #F2F5FA;
    border-color: #E1E7F0;
}
QTableWidget {
    background: #FFFFFF;
    border: none;
    outline: 0;
    gridline-color: transparent;
    alternate-background-color: #FAFBFE;
    selection-background-color: #EAF0FD;
    selection-color: #1B2333;
}
QTableWidget::item {
    padding: 8px;
    border: none;
}
QTableWidget::item:selected {
    background: #EAF0FD;
    color: #1B2333;
}
QTableWidget::item:focus {
    border: none;
}
QHeaderView::section {
    background: #F8FAFD;
    color: #7A8497;
    border: none;
    border-bottom: 1px solid #E1E7F0;
    padding: 9px 8px;
    font-size: 9pt;
    font-weight: 600;
}
QProgressBar {
    background: #E8EDF6;
    border: none;
    border-radius: 4px;
    text-align: center;
    color: #4A5568;
    font-size: 8pt;
}
QProgressBar::chunk {
    background: #2F5FE0;
    border-radius: 4px;
}
QProgressBar#RowProgress {
    background: #E8EDF6;
    border-radius: 4px;
}
QProgressBar#OverallProgress {
    background: #E8EDF6;
    border-radius: 7px;
    min-height: 16px;
    font-size: 8pt;
}
QScrollArea, QScrollArea > QWidget, QScrollArea > QWidget > QWidget {
    background: transparent;
    border: none;
}
QTabWidget::pane {
    border: 1px solid #E1E7F0;
    border-radius: 10px;
    background: #FFFFFF;
    top: -1px;
}
QTabBar::tab {
    background: transparent;
    color: #6B7280;
    padding: 8px 14px;
    margin-right: 4px;
    border: none;
}
QTabBar::tab:selected {
    color: #2F5FE0;
    font-weight: 600;
    border-bottom: 2px solid #2F5FE0;
}
QTabBar::tab:hover:!selected {
    color: #27324A;
}
QPlainTextEdit {
    background: #FFFFFF;
    border: none;
    padding: 8px;
    selection-background-color: #CFE0FF;
}
QPlainTextEdit#LogView {
    font-family: "DejaVu Sans Mono", monospace;
    font-size: 9pt;
    color: #4A5568;
}
QStatusBar {
    background: #FFFFFF;
    border-top: 1px solid #E1E7F0;
    color: #6B7280;
}
QStatusBar::item {
    border: none;
}
QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 2px 2px 2px 0;
}
QScrollBar::handle:vertical {
    background: #C9D3E3;
    border-radius: 4px;
    min-height: 28px;
}
QScrollBar::handle:vertical:hover {
    background: #AEBBD0;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}
QScrollBar:horizontal {
    background: transparent;
    height: 10px;
    margin: 0 2px 2px 2px;
}
QScrollBar::handle:horizontal {
    background: #C9D3E3;
    border-radius: 4px;
    min-width: 28px;
}
QScrollBar::handle:horizontal:hover {
    background: #AEBBD0;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: transparent;
}
QSplitter::handle {
    background: transparent;
}
QMenu {
    background: #FFFFFF;
    border: 1px solid #E1E7F0;
    border-radius: 8px;
    padding: 6px;
}
QMenu::item {
    padding: 7px 18px;
    border-radius: 6px;
}
QMenu::item:selected {
    background: #EAF0FD;
}
QMenu::separator {
    height: 1px;
    background: #EDF1F7;
    margin: 5px 8px;
}
QToolTip {
    background: #1B2333;
    color: #FFFFFF;
    border: none;
    padding: 6px 8px;
    border-radius: 6px;
}
"""


DARK_REPLACEMENTS = {
    "#F3F5FA": "#0F1218",
    "#FFFFFF": "#1A1F2B",
    "#1B2333": "#E6EAF3",
    "#E1E7F0": "#2A3242",
    "#16213A": "#F2F5FC",
    "#6B7280": "#9AA4B8",
    "#8A93A6": "#7F8A9E",
    "#27324A": "#D3DAE8",
    "#E8F5EC": "#173A24",
    "#15803D": "#6FD695",
    "#FFF3E0": "#3A2A14",
    "#B45309": "#F0B35E",
    "#F8FAFD": "#161B25",
    "#E6EBF4": "#2A3242",
    "#D6DEEC": "#364054",
    "#F3F7FE": "#232B3C",
    "#B9C8E4": "#4A5874",
    "#E8EFFB": "#2A3448",
    "#A2AABC": "#5F687B",
    "#F7F9FC": "#151A23",
    "#E7ECF5": "#242B39",
    "#2F5FE0": "#5B8CFF",
    "#2854C9": "#4A7BF0",
    "#2147AE": "#3C66D0",
    "#B9C8EE": "#33466F",
    "#F4F6FF": "#C9D6F5",
    "#B91C1C": "#FF7A7A",
    "#EFCACA": "#5C2B2B",
    "#FDF3F3": "#2B1A1D",
    "#CFE0FF": "#2B3B5E",
    "#EAF0FD": "#24314C",
    "#FAFBFE": "#1E2430",
    "#7A8497": "#98A3B8",
    "#E8EDF6": "#2A3242",
    "#4A5568": "#B8C1D4",
    "#C9D3E3": "#414C61",
    "#AEBBD0": "#56637B",
    "#EDF1F7": "#2A3242",
    "#F2F5FA": "#181D27",
}

DARK_OVERRIDES = """
QToolTip {
    background: #262E3D;
    color: #F5F7FC;
}
QPushButton#primary {
    color: #FFFFFF;
}
QPushButton#primary:disabled {
    color: #C9D6F5;
}
QMenu::item:selected {
    color: #F2F5FC;
}
QTableWidget::item:selected {
    color: #F2F5FC;
}
QComboBox QAbstractItemView {
    color: #E6EAF3;
}
"""

_DARK_QSS: str | None = None


def _dark_stylesheet() -> str:
    global _DARK_QSS
    if _DARK_QSS is None:
        qss = APP_QSS.replace("color: #FFFFFF", "color: __WHITE__")
        for light, dark in DARK_REPLACEMENTS.items():
            qss = qss.replace(light, dark)
        qss = qss.replace("__WHITE__", "#FFFFFF")
        _DARK_QSS = qss + DARK_OVERRIDES
    return _DARK_QSS


def apply_theme(app: QApplication, dark: bool = False) -> None:
    app.setStyle("Fusion")
    palette = QPalette()
    if dark:
        palette.setColor(QPalette.Window, QColor("#0F1218"))
        palette.setColor(QPalette.WindowText, QColor("#E6EAF3"))
        palette.setColor(QPalette.Base, QColor("#1A1F2B"))
        palette.setColor(QPalette.AlternateBase, QColor("#1E2430"))
        palette.setColor(QPalette.ToolTipBase, QColor("#262E3D"))
        palette.setColor(QPalette.ToolTipText, QColor("#F5F7FC"))
        palette.setColor(QPalette.Text, QColor("#E6EAF3"))
        palette.setColor(QPalette.Button, QColor("#1A1F2B"))
        palette.setColor(QPalette.ButtonText, QColor("#E6EAF3"))
        palette.setColor(QPalette.BrightText, QColor("#FFFFFF"))
        palette.setColor(QPalette.Highlight, QColor("#5B8CFF"))
        palette.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))
        palette.setColor(QPalette.Disabled, QPalette.Text, QColor("#5F687B"))
        palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor("#5F687B"))
        palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor("#5F687B"))
        if hasattr(QPalette, "PlaceholderText"):
            palette.setColor(QPalette.PlaceholderText, QColor("#6F7A8D"))
        stylesheet = _dark_stylesheet()
    else:
        palette.setColor(QPalette.Window, QColor("#F3F5FA"))
        palette.setColor(QPalette.WindowText, QColor("#1B2333"))
        palette.setColor(QPalette.Base, QColor("#FFFFFF"))
        palette.setColor(QPalette.AlternateBase, QColor("#FAFBFE"))
        palette.setColor(QPalette.ToolTipBase, QColor("#1B2333"))
        palette.setColor(QPalette.ToolTipText, QColor("#FFFFFF"))
        palette.setColor(QPalette.Text, QColor("#1B2333"))
        palette.setColor(QPalette.Button, QColor("#FFFFFF"))
        palette.setColor(QPalette.ButtonText, QColor("#1B2333"))
        palette.setColor(QPalette.BrightText, QColor("#FFFFFF"))
        palette.setColor(QPalette.Highlight, QColor("#2F5FE0"))
        palette.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))
        palette.setColor(QPalette.Disabled, QPalette.Text, QColor("#A2AABC"))
        palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor("#A2AABC"))
        palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor("#A2AABC"))
        if hasattr(QPalette, "PlaceholderText"):
            palette.setColor(QPalette.PlaceholderText, QColor("#8A93A6"))
        stylesheet = APP_QSS
    app.setPalette(palette)
    font = app.font()
    if 0 < font.pointSizeF() < 10:
        font.setPointSizeF(10)
    app.setFont(font)
    app.setStyleSheet(stylesheet)
