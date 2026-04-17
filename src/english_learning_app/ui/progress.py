"""Progress dashboard for daily stats, streaks, and achievements."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..modules import database as db
from .styles import (
    ACCENT,
    ACCENT_ALT,
    ACCENT_DANGER,
    BG_CARD,
    BG_INPUT,
    BORDER,
    TEXT_MAIN,
    TEXT_MUTED,
    card_style,
    display_font,
)


def _card() -> QFrame:
    frame = QFrame()
    frame.setObjectName("card")
    frame.setStyleSheet(f"QFrame#card{{{card_style(12)}}}")
    return frame


class BarChartWidget(QWidget):
    def __init__(self, data: list[dict], value_key: str, label_key: str, bar_color: str, parent=None):
        super().__init__(parent)
        self.data = data
        self.value_key = value_key
        self.label_key = label_key
        self.bar_color = QColor(bar_color)
        self.setMinimumHeight(150)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def paintEvent(self, event):
        if not self.data:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(BG_INPUT))

        width = self.width()
        height = self.height()
        pad_left, pad_right, pad_top, pad_bottom = 12, 12, 12, 30
        chart_height = height - pad_top - pad_bottom
        total_width = width - pad_left - pad_right
        values = [max(0, int(item.get(self.value_key, 0))) for item in self.data]
        max_value = max(values) if max(values) > 0 else 1
        count = len(self.data)
        gap = total_width / max(count, 1)
        bar_width = max(10, int(gap * 0.55))

        painter.setPen(QPen(QColor(BORDER), 1))
        for ratio in [0.25, 0.5, 0.75, 1.0]:
            y = pad_top + int((1 - ratio) * chart_height)
            painter.drawLine(pad_left, y, width - pad_right, y)

        painter.setPen(Qt.PenStyle.NoPen)
        for index, item in enumerate(self.data):
            value = max(0, int(item.get(self.value_key, 0)))
            bar_height = int(chart_height * value / max_value)
            x = int(pad_left + index * gap + (gap - bar_width) / 2)
            y = pad_top + chart_height - bar_height
            painter.setBrush(self.bar_color)
            painter.drawRoundedRect(x, y, bar_width, bar_height, 4, 4)

            painter.setPen(QColor(TEXT_MAIN))
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            if value > 0:
                painter.drawText(x - 4, y - 2, bar_width + 8, 12, Qt.AlignmentFlag.AlignCenter, str(value))

            painter.setPen(QColor(TEXT_MUTED))
            painter.setFont(QFont("Segoe UI", 8))
            label = str(item.get(self.label_key, ""))[-5:]
            painter.drawText(x - 6, height - pad_bottom + 6, bar_width + 12, 18, Qt.AlignmentFlag.AlignCenter, label)

        painter.end()


class StatCard(QFrame):
    def __init__(self, title: str, value: str, accent: str, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setStyleSheet(
            f"""
            QFrame#card {{
                background: {BG_CARD};
                border: 1px solid {BORDER};
                border-radius: 12px;
            }}
            """
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(4)

        title_label = QLabel(title)
        title_label.setStyleSheet(f"color:{TEXT_MUTED}; font-size:12px;")
        layout.addWidget(title_label)

        self.value_label = QLabel(str(value))
        self.value_label.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        self.value_label.setStyleSheet(f"color:{accent};")
        layout.addWidget(self.value_label)

    def set_value(self, value: str):
        self.value_label.setText(str(value))


class AchievementBadge(QFrame):
    def __init__(self, title: str, description: str, unlocked: bool, parent=None):
        super().__init__(parent)
        accent = "#1f6f4a" if unlocked else BG_CARD
        border = "#2d8a5b" if unlocked else BORDER
        title_color = "#d1fae5" if unlocked else TEXT_MAIN
        desc_color = "#9ee7bf" if unlocked else TEXT_MUTED
        self.setStyleSheet(
            f"""
            QFrame {{
                background: {accent};
                border: 1px solid {border};
                border-radius: 12px;
            }}
            """
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(4)
        title_label = QLabel(title)
        title_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        title_label.setStyleSheet(f"color:{title_color};")
        layout.addWidget(title_label)
        desc_label = QLabel(description)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet(f"color:{desc_color}; font-size:11px;")
        layout.addWidget(desc_label)


class ProgressWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        header = QHBoxLayout()
        title = QLabel("Progress Dashboard")
        title.setFont(display_font(22))
        header.addWidget(title)
        header.addStretch()

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        header.addWidget(refresh_btn)

        reset_btn = QPushButton("Reset Progress")
        reset_btn.setStyleSheet(
            f"background:{ACCENT_DANGER}; color:white; border:none; border-radius:10px; padding:8px 18px;"
        )
        reset_btn.clicked.connect(self._reset_progress)
        header.addWidget(reset_btn)
        root.addLayout(header)

        subtitle = QLabel(
            "Track today’s activity, weekly momentum, and database growth across vocabulary, reading, writing, listening, speaking, and grammar."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"color:{TEXT_MUTED};")
        root.addWidget(subtitle)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        inner = QWidget()
        self.content = QVBoxLayout(inner)
        self.content.setSpacing(16)
        scroll.setWidget(inner)
        root.addWidget(scroll, 1)

    def _reset_progress(self):
        reply = QMessageBox.warning(
            self,
            "Reset Progress",
            "Reset daily progress and flashcard scheduling data? Vocabulary and saved practice content will stay in the database.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        db.reset_all_progress()
        self.refresh()
        QMessageBox.information(self, "Done", "Progress data was reset.")

    def refresh(self):
        while self.content.count():
            item = self.content.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        today = db.get_today_progress()
        weekly = list(reversed(db.get_weekly_stats()))
        vocab_stats = db.get_vocab_stats()

        summary = _card()
        summary_layout = QVBoxLayout(summary)
        summary_layout.setContentsMargins(18, 18, 18, 18)
        summary_layout.setSpacing(12)
        summary_title = QLabel("Today")
        summary_title.setFont(display_font(16))
        summary_layout.addWidget(summary_title)

        stat_grid = QGridLayout()
        stat_grid.setSpacing(10)
        stats = [
            ("Streak", today.get("streak_days", 0), "#f59e0b"),
            ("XP", today.get("xp_earned", 0), "#fde68a"),
            ("Words", today.get("words_learned", 0), "#22c55e"),
            ("Reviews", today.get("words_reviewed", 0), ACCENT),
            ("Writing", today.get("writing_sessions", 0), "#c084fc"),
            ("Listening", today.get("listening_sessions", 0), "#f472b6"),
            ("Reading", today.get("reading_sessions", 0), "#38bdf8"),
            ("Speaking", today.get("speaking_sessions", 0), ACCENT_ALT),
        ]
        for index, (label, value, color) in enumerate(stats):
            stat_grid.addWidget(StatCard(label, str(value), color), index // 4, index % 4)
        summary_layout.addLayout(stat_grid)
        self.content.addWidget(summary)

        if weekly:
            charts_row = QHBoxLayout()

            xp_card = _card()
            xp_layout = QVBoxLayout(xp_card)
            xp_layout.setContentsMargins(16, 16, 16, 16)
            xp_title = QLabel("XP in the Last 7 Days")
            xp_title.setFont(display_font(14))
            xp_layout.addWidget(xp_title)
            xp_layout.addWidget(BarChartWidget(weekly, "xp_earned", "date", ACCENT))
            charts_row.addWidget(xp_card, 1)

            words_card = _card()
            words_layout = QVBoxLayout(words_card)
            words_layout.setContentsMargins(16, 16, 16, 16)
            words_title = QLabel("Words Learned in the Last 7 Days")
            words_title.setFont(display_font(14))
            words_layout.addWidget(words_title)
            words_layout.addWidget(BarChartWidget(weekly, "words_learned", "date", ACCENT_ALT))
            charts_row.addWidget(words_card, 1)

            self.content.addLayout(charts_row)

            breakdown = _card()
            breakdown_layout = QVBoxLayout(breakdown)
            breakdown_layout.setContentsMargins(16, 16, 16, 16)
            breakdown_layout.setSpacing(8)
            breakdown_title = QLabel("Weekly Breakdown")
            breakdown_title.setFont(display_font(14))
            breakdown_layout.addWidget(breakdown_title)

            header = QHBoxLayout()
            for label, width in [("Date", 70), ("Words", 60), ("Reading", 70), ("Listening", 80), ("Writing", 70), ("Speaking", 75), ("XP", 50)]:
                item = QLabel(label)
                item.setFixedWidth(width)
                item.setStyleSheet(f"color:{TEXT_MUTED}; font-weight:600;")
                header.addWidget(item)
            header.addStretch()
            breakdown_layout.addLayout(header)

            divider = QFrame()
            divider.setFixedHeight(1)
            divider.setStyleSheet(f"background:{BORDER};")
            breakdown_layout.addWidget(divider)

            for day in weekly:
                row = QHBoxLayout()
                values = [
                    (day.get("date", "")[-5:], 70, TEXT_MAIN),
                    (str(day.get("words_learned", 0)), 60, ACCENT_ALT),
                    (str(day.get("reading_sessions", 0)), 70, "#38bdf8"),
                    (str(day.get("listening_sessions", 0)), 80, "#f472b6"),
                    (str(day.get("writing_sessions", 0)), 70, "#c084fc"),
                    (str(day.get("speaking_sessions", 0)), 75, ACCENT_ALT),
                    (str(day.get("xp_earned", 0)), 50, "#fde68a"),
                ]
                for text, width, color in values:
                    label = QLabel(text)
                    label.setFixedWidth(width)
                    label.setStyleSheet(f"color:{color};")
                    row.addWidget(label)
                row.addStretch()
                breakdown_layout.addLayout(row)
            self.content.addWidget(breakdown)

        vocab_card = _card()
        vocab_layout = QVBoxLayout(vocab_card)
        vocab_layout.setContentsMargins(16, 16, 16, 16)
        vocab_layout.setSpacing(10)
        vocab_title = QLabel("Vocabulary Library")
        vocab_title.setFont(display_font(14))
        vocab_layout.addWidget(vocab_title)

        if vocab_stats:
            grid = QGridLayout()
            grid.setSpacing(10)
            for index, stat in enumerate(vocab_stats):
                topic_card = QFrame()
                topic_card.setStyleSheet(
                    f"background:{BG_INPUT}; border:1px solid {BORDER}; border-radius:10px;"
                )
                topic_layout = QVBoxLayout(topic_card)
                topic_layout.setContentsMargins(12, 12, 12, 12)
                topic_layout.setSpacing(4)
                topic_label = QLabel(stat.get("topic") or "General")
                topic_label.setWordWrap(True)
                topic_label.setStyleSheet(f"color:{TEXT_MUTED};")
                topic_layout.addWidget(topic_label)
                count_label = QLabel(f"{stat.get('count', 0)} words")
                count_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
                count_label.setStyleSheet(f"color:{ACCENT};")
                topic_layout.addWidget(count_label)
                grid.addWidget(topic_card, index // 3, index % 3)
            vocab_layout.addLayout(grid)
        else:
            empty = QLabel("No vocabulary has been added yet.")
            empty.setStyleSheet(f"color:{TEXT_MUTED};")
            vocab_layout.addWidget(empty)
        self.content.addWidget(vocab_card)

        achievements = _card()
        achievements_layout = QVBoxLayout(achievements)
        achievements_layout.setContentsMargins(16, 16, 16, 16)
        achievements_layout.setSpacing(10)
        achievements_title = QLabel("Milestones")
        achievements_title.setFont(display_font(14))
        achievements_layout.addWidget(achievements_title)

        streak = today.get("streak_days", 0)
        weekly_xp = sum(day.get("xp_earned", 0) for day in weekly) if weekly else today.get("xp_earned", 0)
        badges = [
            ("Started", "Complete your first day of learning.", streak >= 1),
            ("Week Streak", "Reach a 7-day streak.", streak >= 7),
            ("Month Streak", "Reach a 30-day streak.", streak >= 30),
            ("Word Builder", "Learn 10 words in a day.", today.get("words_learned", 0) >= 10),
            ("Writer", "Complete 2 writing sessions in one day.", today.get("writing_sessions", 0) >= 2),
            ("Listener", "Complete 3 listening sessions in one day.", today.get("listening_sessions", 0) >= 3),
            ("Speaker", "Complete 2 speaking sessions in one day.", today.get("speaking_sessions", 0) >= 2),
            ("XP Collector", "Earn 50 XP in a week.", weekly_xp >= 50),
        ]
        badge_grid = QGridLayout()
        badge_grid.setSpacing(10)
        for index, (title, desc, unlocked) in enumerate(badges):
            badge_grid.addWidget(AchievementBadge(title, desc, unlocked), index // 4, index % 4)
        achievements_layout.addLayout(badge_grid)
        self.content.addWidget(achievements)
        self.content.addStretch()
