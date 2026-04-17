"""Shared UI theme for the English learning app."""
from __future__ import annotations

from PySide6.QtGui import QFont


APP_FONT_FAMILY = "Segoe UI"
DISPLAY_FONT_FAMILY = "Segoe UI Semibold"

BG_MAIN = "#0f1117"
BG_SIDEBAR = "#16181f"
BG_CARD = "#1e2130"
BG_PANEL = "#151927"
BG_INPUT = "#13151f"
BG_HOVER = "#252a3a"
ACCENT = "#5b6af0"
ACCENT_ALT = "#3dd68c"
ACCENT_WARN = "#f59e0b"
ACCENT_DANGER = "#f87171"
TEXT_MAIN = "#e8eaf0"
TEXT_MUTED = "#8892a4"
BORDER = "#2a2f42"


def app_font(point_size: int = 11, weight: int = QFont.Weight.Normal) -> QFont:
    return QFont(APP_FONT_FAMILY, point_size, weight)


def display_font(point_size: int = 16, weight: int = QFont.Weight.Bold) -> QFont:
    return QFont(DISPLAY_FONT_FAMILY, point_size, weight)


def tab_style() -> str:
    return f"""
        QTabWidget::pane {{
            border: none;
            background: {BG_MAIN};
        }}
        QTabBar::tab {{
            background: #1a1d27;
            color: {TEXT_MUTED};
            padding: 11px 22px;
            border-radius: 6px 6px 0 0;
            margin-right: 2px;
            font-size: 13px;
        }}
        QTabBar::tab:selected {{
            background: {BG_CARD};
            color: white;
            border-bottom: 2px solid {ACCENT};
            font-weight: 600;
        }}
        QTabBar::tab:hover {{
            background: {BG_HOVER};
            color: {TEXT_MAIN};
        }}
    """


def card_style(radius: int = 12, bg: str = BG_CARD) -> str:
    return (
        f"background:{bg};"
        f"border:1.5px solid {BORDER};"
        f"border-radius:{radius}px;"
    )


def build_app_stylesheet() -> str:
    return f"""
        * {{
            font-family: "{APP_FONT_FAMILY}";
        }}

        QMainWindow, QDialog {{
            background: {BG_MAIN};
        }}

        QWidget {{
            color: {TEXT_MAIN};
            background: transparent;
            font-size: 13px;
        }}

        QLabel {{
            color: {TEXT_MAIN};
            background: transparent;
        }}

        QFrame#card {{
            background: {BG_CARD};
            border: 1.5px solid {BORDER};
            border-radius: 12px;
        }}

        QScrollArea {{
            border: none;
            background: transparent;
        }}

        QScrollBar:vertical {{
            background: {BG_CARD};
            width: 8px;
            border-radius: 4px;
            margin: 0;
        }}

        QScrollBar::handle:vertical {{
            background: #3a3f55;
            border-radius: 4px;
            min-height: 24px;
        }}

        QScrollBar::handle:vertical:hover {{
            background: {ACCENT};
        }}

        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical,
        QScrollBar::add-line:horizontal,
        QScrollBar::sub-line:horizontal {{
            width: 0;
            height: 0;
        }}

        QScrollBar:horizontal {{
            background: {BG_CARD};
            height: 8px;
            border-radius: 4px;
        }}

        QScrollBar::handle:horizontal {{
            background: #3a3f55;
            border-radius: 4px;
        }}

        QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QListWidget {{
            background: {BG_INPUT};
            color: {TEXT_MAIN};
            border: 1.5px solid {BORDER};
            border-radius: 10px;
            padding: 8px 12px;
            selection-background-color: {ACCENT};
        }}

        QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{
            border-color: {ACCENT};
        }}

        QComboBox::drop-down {{
            border: none;
            width: 28px;
        }}

        QComboBox::down-arrow {{
            image: none;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 6px solid {TEXT_MUTED};
            margin-right: 8px;
        }}

        QComboBox QAbstractItemView {{
            background: {BG_CARD};
            color: {TEXT_MAIN};
            border: 1px solid {BORDER};
            selection-background-color: {ACCENT};
            outline: none;
        }}

        QPushButton {{
            background: {BG_PANEL};
            color: {TEXT_MAIN};
            border: 1.5px solid {BORDER};
            border-radius: 10px;
            padding: 8px 18px;
            font-size: 13px;
            font-weight: 500;
        }}

        QPushButton:hover {{
            background: {BG_HOVER};
            border-color: {ACCENT};
        }}

        QPushButton:pressed {{
            background: {ACCENT};
            color: white;
            border-color: {ACCENT};
        }}

        QPushButton:disabled {{
            color: #4b5568;
            background: #1a1d27;
            border-color: #252a3a;
        }}

        QPushButton#btnPrimary {{
            background: {ACCENT};
            color: white;
            border: none;
            font-weight: 700;
        }}

        QPushButton#btnPrimary:hover {{
            background: #6b7af8;
        }}

        QPushButton#btnSuccess {{
            background: #184a31;
            color: #d1fae5;
            border-color: #2d7a50;
            font-weight: 700;
        }}

        QPushButton#btnSuccess:hover {{
            background: #215f3e;
        }}

        QPushButton#btnWarning {{
            background: #4a3511;
            color: #fcd34d;
            border-color: #9a6700;
        }}

        QPushButton#btnDanger {{
            background: #3d1a1a;
            color: #fecaca;
            border-color: #7a2d2d;
        }}

        QPushButton#btnGhost {{
            background: transparent;
            color: {TEXT_MUTED};
        }}

        QListWidget::item {{
            padding: 8px;
            border-bottom: 1px solid #171a23;
        }}

        QListWidget::item:selected {{
            background: {ACCENT};
            color: white;
        }}

        QListWidget::item:hover {{
            background: {BG_HOVER};
        }}

        QProgressBar {{
            background: #1a1d27;
            border: none;
            border-radius: 6px;
            height: 8px;
            text-align: center;
        }}

        QProgressBar::chunk {{
            background: qlineargradient(
                x1: 0, y1: 0, x2: 1, y2: 0,
                stop: 0 {ACCENT},
                stop: 1 {ACCENT_ALT}
            );
            border-radius: 6px;
        }}

        QGroupBox {{
            border: 1px solid {BORDER};
            border-radius: 12px;
            margin-top: 14px;
            padding-top: 14px;
            color: {TEXT_MUTED};
            font-size: 12px;
            font-weight: 600;
        }}

        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 12px;
            padding: 0 8px;
        }}

        QStatusBar {{
            background: {BG_SIDEBAR};
            color: {TEXT_MUTED};
            border-top: 1px solid {BORDER};
        }}

        QMenuBar {{
            background: {BG_SIDEBAR};
            color: {TEXT_MUTED};
            border-bottom: 1px solid {BORDER};
        }}

        QMenuBar::item:selected {{
            background: {BG_HOVER};
            color: white;
            border-radius: 4px;
        }}

        QMenu {{
            background: {BG_CARD};
            color: {TEXT_MAIN};
            border: 1px solid {BORDER};
            border-radius: 8px;
            padding: 4px;
        }}

        QMenu::item {{
            padding: 6px 20px;
            border-radius: 4px;
        }}

        QMenu::item:selected {{
            background: {ACCENT};
            color: white;
        }}
    """
