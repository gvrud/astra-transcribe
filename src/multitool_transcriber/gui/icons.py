from __future__ import annotations

from pathlib import Path

from PyQt5.QtCore import QRectF, QSize, Qt
from PyQt5.QtGui import QColor, QIcon, QLinearGradient, QPainter, QPixmap
from PyQt5.QtWidgets import QApplication


def icon_path() -> Path:
    base = Path(__file__).resolve().parent.parent / "assets"
    for name in ("astra-transcribe.svg", "multitool-transcriber.svg"):
        path = base / name
        if path.exists():
            return path
    return base / "astra-transcribe.svg"


def app_icon() -> QIcon:
    path = icon_path()
    if path.exists():
        icon = QIcon(str(path))
        if not icon.isNull():
            return icon
    return _painted_icon()


def icon_pixmap(size: int) -> QPixmap:
    application = QApplication.instance()
    screen = application.primaryScreen() if application is not None else None
    ratio = float(screen.devicePixelRatio()) if screen is not None else 1.0
    pixel_size = max(1, int(round(size * ratio)))
    pixmap = app_icon().pixmap(QSize(pixel_size, pixel_size))
    pixmap.setDevicePixelRatio(ratio)
    return pixmap


def _painted_icon() -> QIcon:
    size = 256
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    gradient = QLinearGradient(0, 0, size, size)
    gradient.setColorAt(0, QColor("#3E70F2"))
    gradient.setColorAt(1, QColor("#2447B8"))
    painter.setBrush(gradient)
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(QRectF(8, 8, size - 16, size - 16), 56, 56)
    painter.setBrush(QColor("#FFFFFF"))
    bars = [
        (64, 108, 16, 40),
        (96, 84, 16, 88),
        (128, 60, 16, 136),
        (160, 92, 16, 72),
        (192, 112, 16, 32),
    ]
    for x, y, width, height in bars:
        painter.drawRoundedRect(QRectF(x, y, width, height), width / 2, width / 2)
    painter.end()
    return QIcon(pixmap)
