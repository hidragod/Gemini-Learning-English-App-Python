"""
Splash Screen khi khởi động app
"""
from PySide6.QtWidgets import QSplashScreen, QLabel, QVBoxLayout, QWidget, QProgressBar
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont, QLinearGradient, QGradient


def create_splash_pixmap(width=520, height=300) -> QPixmap:
    pixmap = QPixmap(width, height)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    # Background gradient
    grad = QLinearGradient(0, 0, 0, height)
    grad.setColorAt(0, QColor("#0d1b35"))
    grad.setColorAt(1, QColor("#1a0a2e"))
    painter.fillRect(0, 0, width, height, grad)

    # Border
    painter.setPen(QColor("#2a82da"))
    painter.drawRoundedRect(2, 2, width-4, height-4, 12, 12)

    # Title
    painter.setPen(QColor("#4fc3f7"))
    painter.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
    painter.drawText(0, 60, width, 50, Qt.AlignmentFlag.AlignCenter, "🌐 Web Crawler + Gemini AI")

    # Subtitle
    painter.setPen(QColor("#a0c4ff"))
    painter.setFont(QFont("Segoe UI", 12))
    painter.drawText(0, 110, width, 30, Qt.AlignmentFlag.AlignCenter, "Powered by Scrapling · PySide6 · Google Gemini")

    # Features
    painter.setPen(QColor("#888"))
    painter.setFont(QFont("Segoe UI", 10))
    features = ["✅ Web Crawler  ·  🤖 Gemini Chat  ·  📚 English Learning"]
    painter.drawText(0, 155, width, 25, Qt.AlignmentFlag.AlignCenter, features[0])
    painter.drawText(0, 178, width, 25, Qt.AlignmentFlag.AlignCenter, "🃏 Flashcards  ·  ❓ Quiz  ·  🔌 MCP Server")

    # Loading text
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
        self.showMessage(msg, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter, QColor("#4fc3f7"))
