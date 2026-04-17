"""Main entry point for the Gemini English Learning desktop app."""
import sys
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon


APP_ICON_PATH = Path(__file__).resolve().parent / "assets" / "app_icon.ico"


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Gemini English Learning")
    app.setOrganizationName("EnglishLearning")
    app.setStyle("Fusion")
    if APP_ICON_PATH.exists():
        app.setWindowIcon(QIcon(str(APP_ICON_PATH)))

    # Splash screen
    from src.ui.splash_screen import AppSplashScreen
    splash = AppSplashScreen()
    if APP_ICON_PATH.exists():
        splash.setWindowIcon(QIcon(str(APP_ICON_PATH)))
    splash.show()
    app.processEvents()

    # Load components
    splash.update_message("Loading modules...")
    app.processEvents()

    from src.ui.main_window import MainWindow
    splash.update_message("Initializing UI...")
    app.processEvents()

    window = MainWindow()
    if APP_ICON_PATH.exists():
        window.setWindowIcon(QIcon(str(APP_ICON_PATH)))

    splash.update_message("Ready!")
    app.processEvents()

    # Close splash after 1.5s
    QTimer.singleShot(1500, splash.close)
    QTimer.singleShot(1500, window.show)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
