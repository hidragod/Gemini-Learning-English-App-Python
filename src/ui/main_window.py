"""Main application window."""
from __future__ import annotations

import os

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .gemini_web_tab import GeminiWebTab
from src.english_learning_app.modules import database as eng_db
from src.english_learning_app.ui.dashboard import DashboardWidget
from src.english_learning_app.ui.db_manager import DBManagerWidget
from src.english_learning_app.ui.grammar import GrammarWidget
from src.english_learning_app.ui.listening import ListeningWidget
from src.english_learning_app.ui.progress import ProgressWidget
from src.english_learning_app.ui.reading import ReadingWidget
from src.english_learning_app.ui.speaking import SpeakingWidget
from src.english_learning_app.ui.styles import (
    ACCENT,
    ACCENT_ALT,
    BG_HOVER,
    BG_MAIN,
    BG_SIDEBAR,
    BORDER,
    TEXT_MAIN,
    TEXT_MUTED,
    build_app_stylesheet,
)
from src.english_learning_app.ui.vocabulary import VocabularyWidget
from src.english_learning_app.ui.writing import WritingWidget


def _shared_api_key() -> str:
    return (
        os.getenv("GEMINI_API_KEY")
        or os.getenv("GOOGLE_API_KEY")
        or os.getenv("API_KEY")
        or ""
    )


class Signals(QObject):
    status_changed = Signal(str)


class SidebarButton(QPushButton):
    def __init__(self, icon: str, label: str, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedHeight(48)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setText(f"  {icon}  {label}")
        self.setFont(QFont("Segoe UI", 12))
        self.toggled.connect(self._set_style)
        self._set_style(False)

    def _set_style(self, checked: bool):
        if checked:
            self.setStyleSheet(
                f"""
                QPushButton {{
                    background: {ACCENT}22;
                    color: white;
                    border: none;
                    border-left: 3px solid {ACCENT};
                    border-radius: 0;
                    text-align: left;
                    padding-left: 18px;
                    font-weight: 700;
                }}
                """
            )
        else:
            self.setStyleSheet(
                f"""
                QPushButton {{
                    background: transparent;
                    color: {TEXT_MUTED};
                    border: none;
                    border-left: 3px solid transparent;
                    border-radius: 0;
                    text-align: left;
                    padding-left: 18px;
                    font-weight: 400;
                }}
                QPushButton:hover {{
                    background: {BG_HOVER};
                    color: {TEXT_MAIN};
                    border-left: 3px solid {BORDER};
                }}
                """
            )


class Sidebar(QFrame):
    page_changed = Signal(int)

    ITEMS = [
        ("G", "Gemini Web"),
        ("D", "Dashboard"),
        ("V", "Vocabulary"),
        ("R", "Reading"),
        ("S", "Speaking"),
        ("W", "Writing"),
        ("Gr", "Grammar"),
        ("L", "Listening"),
        ("P", "Progress"),
        ("DB", "DB Manager"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(220)
        self.setStyleSheet(
            f"QFrame{{background:{BG_SIDEBAR}; border-right:1px solid {BORDER};}}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        logo_frame = QFrame()
        logo_frame.setFixedHeight(72)
        logo_frame.setStyleSheet(
            f"background:{BG_SIDEBAR}; border-bottom:1px solid {BORDER};"
        )
        logo_layout = QHBoxLayout(logo_frame)
        logo_layout.setContentsMargins(18, 0, 18, 0)
        logo = QLabel("EduGemini Studio")
        logo.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        logo.setStyleSheet(f"color:{ACCENT};")
        logo_layout.addWidget(logo)
        layout.addWidget(logo_frame)

        layout.addSpacing(8)

        self._buttons: list[SidebarButton] = []
        self._add_section(layout, "MAIN")
        for idx, item in enumerate(self.ITEMS[:2]):
            self._add_button(layout, idx, *item)

        layout.addSpacing(8)
        self._add_section(layout, "ENGLISH LAB")
        for idx, item in enumerate(self.ITEMS[2:], start=2):
            self._add_button(layout, idx, *item)

        layout.addStretch()

        self._ai_badge = QLabel("  AI: Not connected")
        self._ai_badge.setFixedHeight(40)
        self._ai_badge.setFont(QFont("Segoe UI", 11))
        self._ai_badge.setStyleSheet(
            f"color:#fca5a5; background:#2a1a1a; border-top:1px solid {BORDER}; padding-left:14px;"
        )
        layout.addWidget(self._ai_badge)
        self._select(0)

    def _add_section(self, layout: QVBoxLayout, text: str):
        label = QLabel(f"  {text}")
        label.setFixedHeight(28)
        label.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        label.setStyleSheet(f"color:{TEXT_MUTED}; letter-spacing:1px; padding-left:14px;")
        layout.addWidget(label)

    def _add_button(self, layout: QVBoxLayout, idx: int, icon: str, label: str):
        button = SidebarButton(icon, label)
        button.clicked.connect(lambda _, page_idx=idx: self._select(page_idx))
        self._buttons.append(button)
        layout.addWidget(button)

    def _select(self, idx: int):
        for i, button in enumerate(self._buttons):
            button.setChecked(i == idx)
        self.page_changed.emit(idx)

    def set_ai_status(self, connected: bool, busy_job: str = ""):
        if busy_job:
            self._ai_badge.setText("  Gemini Web: Busy")
            self._ai_badge.setStyleSheet(
                f"color:#fde68a; background:#2e2414; border-top:1px solid {BORDER}; padding-left:14px; font-weight:700;"
            )
        elif connected:
            self._ai_badge.setText("  Gemini Web: Ready")
            self._ai_badge.setStyleSheet(
                f"color:{ACCENT_ALT}; background:#0f2a1a; border-top:1px solid {BORDER}; padding-left:14px; font-weight:700;"
            )
        else:
            self._ai_badge.setText("  AI: Not connected")
            self._ai_badge.setStyleSheet(
                f"color:#fca5a5; background:#2a1a1a; border-top:1px solid {BORDER}; padding-left:14px;"
            )


def _wrap(widget: QWidget) -> QScrollArea:
    scroll = QScrollArea()
    scroll.setWidget(widget)
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    return scroll


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EduGemini Studio")
        self.setMinimumSize(1180, 760)
        self.resize(1450, 920)

        app = QApplication.instance()
        app.setStyleSheet(build_app_stylesheet())

        self.signals = Signals()
        eng_db.init_db()

        self._setup_menu()
        self._setup_ui()
        self._setup_status_bar()
        self.signals.status_changed.connect(self.statusBar().showMessage)

        timer = QTimer(self)
        timer.timeout.connect(self._refresh_ai_status)
        timer.start(5000)

    def _setup_menu(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("File")
        file_menu.addAction("Quit", self.close)

        help_menu = menu_bar.addMenu("Help")
        help_menu.addAction("About", self._show_about)

    def _setup_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.sidebar = Sidebar()
        self.sidebar.page_changed.connect(self._switch_page)
        root_layout.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        self.stack.setStyleSheet(f"background:{BG_MAIN};")
        root_layout.addWidget(self.stack, stretch=1)

        self.gemini_web_tab = GeminiWebTab(self.signals)
        self.stack.addWidget(self.gemini_web_tab)

        self.dashboard_widget = DashboardWidget()
        self.stack.addWidget(_wrap(self.dashboard_widget))

        self.vocabulary_widget = VocabularyWidget(_shared_api_key)
        self.stack.addWidget(_wrap(self.vocabulary_widget))

        self.reading_widget = ReadingWidget(_shared_api_key)
        self.stack.addWidget(_wrap(self.reading_widget))

        self.speaking_widget = SpeakingWidget(_shared_api_key)
        self.stack.addWidget(_wrap(self.speaking_widget))

        self.writing_widget = WritingWidget(_shared_api_key)
        self.stack.addWidget(_wrap(self.writing_widget))

        self.grammar_widget = GrammarWidget(_shared_api_key)
        self.stack.addWidget(_wrap(self.grammar_widget))

        self.listening_widget = ListeningWidget(_shared_api_key)
        self.stack.addWidget(_wrap(self.listening_widget))

        self.progress_widget = ProgressWidget()
        self.stack.addWidget(_wrap(self.progress_widget))

        self.db_manager_widget = DBManagerWidget()
        self.stack.addWidget(self.db_manager_widget)

        self.gemini_web_tab._worker.login_ok.connect(self._on_gemini_login_ok)

    def _setup_status_bar(self):
        self.statusBar().showMessage(
            "Ready  |  Open Gemini Web to unlock reading, writing, grammar, and speaking AI features."
        )

    def _switch_page(self, idx: int):
        self.stack.setCurrentIndex(idx)

    def _refresh_ai_status(self):
        from src.english_learning_app.modules.ai_module import _use_web, get_web_job_status

        busy_job = get_web_job_status()
        connected = _use_web()
        self.sidebar.set_ai_status(connected, busy_job)
        if busy_job:
            self.statusBar().showMessage(f"Gemini Web busy: {busy_job}")
        elif connected:
            self.statusBar().showMessage("Gemini Web connected. AI study features are ready.")

    def _on_gemini_login_ok(self):
        self._refresh_ai_status()
        self.signals.status_changed.emit(
            "Gemini Web connected. Text coaching features are now active."
        )

    def _show_about(self):
        QMessageBox.about(
            self,
            "EduGemini Studio",
            "<b>EduGemini Studio</b><br><br>"
            "A unified English learning workspace with Gemini Web chat, reading, writing, listening, grammar, speaking, and vocabulary practice.",
        )

    def closeEvent(self, event):
        event.accept()
