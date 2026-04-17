"""Splash screen khi khởi động app."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPixmap
from PySide6.QtWidgets import QSplashScreen


def create_splash_pixmap(width: int = 520, height: int = 300) -> QPixmap:
    pixmap = QPixmap(width, height)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    gradient = QLinearGradient(0, 0, 0, height)
    gradient.setColorAt(0, QColor("#0d1b35"))
    gradient.setColorAt(1, QColor("#1a0a2e"))
    painter.fillRect(0, 0, width, height, gradient)

    painter.setPen(QColor("#2a82da"))
    painter.drawRoundedRect(2, 2, width - 4, height - 4, 12, 12)

    painter.setPen(QColor("#4fc3f7"))
    painter.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
    painter.drawText(0, 60, width, 50, Qt.AlignmentFlag.AlignCenter, "Gemini English Learning")

    painter.setPen(QColor("#a0c4ff"))
    painter.setFont(QFont("Segoe UI", 12))
    painter.drawText(
        0,
        110,
        width,
        30,
        Qt.AlignmentFlag.AlignCenter,
        "Powered by PySide6 · Playwright · Gemini Web",
    )

    painter.setPen(QColor("#888"))
    painter.setFont(QFont("Segoe UI", 10))
    painter.drawText(
        0,
        155,
        width,
        25,
        Qt.AlignmentFlag.AlignCenter,
        "Gemini Chat  ·  Vocabulary  ·  English Practice",
    )
    painter.drawText(
        0,
        178,
        width,
        25,
        Qt.AlignmentFlag.AlignCenter,
        "Flashcards  ·  Quiz  ·  Writing  ·  Speaking",
    )

    painter.setPen(QColor("#555"))
    painter.setFont(QFont("Segoe UI", 9))
    painter.drawText(0, 260, width, 25, Qt.AlignmentFlag.AlignCenter, "Loading...")

    painter.end()
    return pixmap


class AppSplashScreen(QSplashScreen):
    def __init__(self):
        pixmap = create_splash_pixmap()
        super().__init__(pixmap, Qt.WindowType.WindowStaysOnTopHint)
        self.setMask(pixmap.mask())

    def update_message(self, msg: str):
        self.showMessage(
            msg,
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
            QColor("#4fc3f7"),
        )
