"""Dashboard with daily study plan and lesson path."""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..modules import database as db
from .styles import ACCENT, ACCENT_ALT, ACCENT_WARN, BORDER, TEXT_MUTED, card_style


def _card() -> QFrame:
    frame = QFrame()
    frame.setObjectName("card")
    frame.setStyleSheet(f"QFrame#card{{{card_style(14)}}}")
    return frame


class StatCard(QFrame):
    def __init__(self, title: str, value: str, hint: str, color: str):
        super().__init__()
        self.setObjectName("card")
        self.setStyleSheet(f"QFrame#card{{{card_style(14)}}}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(6)

        title_label = QLabel(title)
        title_label.setStyleSheet(f"color:{TEXT_MUTED}; font-size:12px;")
        layout.addWidget(title_label)

        self.value_label = QLabel(value)
        self.value_label.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        self.value_label.setStyleSheet(f"color:{color};")
        layout.addWidget(self.value_label)

        self.hint_label = QLabel(hint)
        self.hint_label.setStyleSheet(f"color:{TEXT_MUTED}; font-size:12px;")
        self.hint_label.setWordWrap(True)
        layout.addWidget(self.hint_label)

    def set_value(self, value: str, hint: str):
        self.value_label.setText(value)
        self.hint_label.setText(hint)


class DashboardWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self.refresh()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(30000)

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.setSpacing(18)

        header = QHBoxLayout()
        title = QLabel("Learning Dashboard")
        title.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        header.addWidget(title)
        header.addStretch()
        self.date_label = QLabel("")
        self.date_label.setStyleSheet(f"color:{TEXT_MUTED}; font-size:13px;")
        header.addWidget(self.date_label)
        outer.addLayout(header)

        self.hero = QFrame()
        self.hero.setStyleSheet(
            """
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1d4ed8, stop:1 #4f46e5);
                border-radius: 16px;
            }
            """
        )
        hero_layout = QHBoxLayout(self.hero)
        hero_layout.setContentsMargins(20, 16, 20, 16)
        hero_layout.setSpacing(16)
        self.streak_label = QLabel("")
        self.streak_label.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        self.streak_label.setStyleSheet("color:white;")
        hero_layout.addWidget(self.streak_label)
        hero_layout.addStretch()
        self.xp_label = QLabel("")
        self.xp_label.setStyleSheet("color:#fde68a; font-size:13px; font-weight:700;")
        hero_layout.addWidget(self.xp_label)
        outer.addWidget(self.hero)

        stats = QGridLayout()
        stats.setSpacing(12)
        self.words_card = StatCard("Words Learned", "0", "Add or save new vocabulary today.", ACCENT_ALT)
        self.review_card = StatCard("Words Reviewed", "0", "Flashcards and quiz practice.", ACCENT)
        self.reading_card = StatCard("Reading Sessions", "0", "Passages, translation and vocab lookup.", "#60a5fa")
        self.output_card = StatCard("Output Sessions", "0", "Writing, image description and speaking.", "#c084fc")
        stats.addWidget(self.words_card, 0, 0)
        stats.addWidget(self.review_card, 0, 1)
        stats.addWidget(self.reading_card, 1, 0)
        stats.addWidget(self.output_card, 1, 1)
        outer.addLayout(stats)

        plan_card = _card()
        plan_layout = QVBoxLayout(plan_card)
        plan_layout.setContentsMargins(18, 18, 18, 18)
        plan_layout.setSpacing(10)
        plan_title = QLabel("Daily Study Plan")
        plan_title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        plan_layout.addWidget(plan_title)
        self.plan_items: list[tuple[QLabel, QProgressBar, QLabel]] = []
        for label in ["Vocabulary", "Reading", "Listening", "Output"]:
            row = QHBoxLayout()
            name = QLabel(label)
            name.setFixedWidth(92)
            bar = QProgressBar()
            bar.setTextVisible(False)
            status = QLabel("")
            status.setFixedWidth(90)
            status.setStyleSheet(f"color:{TEXT_MUTED}; font-size:12px;")
            row.addWidget(name)
            row.addWidget(bar, 1)
            row.addWidget(status)
            plan_layout.addLayout(row)
            self.plan_items.append((name, bar, status))
        outer.addWidget(plan_card)

        target_card = _card()
        target_layout = QVBoxLayout(target_card)
        target_layout.setContentsMargins(18, 18, 18, 18)
        target_layout.setSpacing(10)
        target_title = QLabel("Saved Study Targets")
        target_title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        target_layout.addWidget(target_title)
        target_row = QHBoxLayout()
        self.target_inputs = {}
        for key, label in [("words", "Words"), ("review", "Review"), ("reading", "Reading"), ("listening", "Listening"), ("output", "Output"), ("speaking", "Speaking")]:
            col = QVBoxLayout()
            cap = QLabel(label)
            spin = QSpinBox()
            spin.setRange(1, 50)
            spin.setFixedWidth(78)
            col.addWidget(cap)
            col.addWidget(spin)
            target_row.addLayout(col)
            self.target_inputs[key] = spin
        target_row.addStretch()
        save_btn = QPushButton("Save Targets")
        save_btn.setObjectName("btnPrimary")
        save_btn.clicked.connect(self._save_targets)
        target_row.addWidget(save_btn)
        target_layout.addLayout(target_row)
        outer.addWidget(target_card)

        lesson_card = _card()
        lesson_layout = QVBoxLayout(lesson_card)
        lesson_layout.setContentsMargins(18, 18, 18, 18)
        lesson_layout.setSpacing(10)
        lesson_title = QLabel("Lesson Path")
        lesson_title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        lesson_layout.addWidget(lesson_title)
        self.lesson_summary = QLabel("")
        self.lesson_summary.setWordWrap(True)
        self.lesson_summary.setStyleSheet(f"color:{TEXT_MUTED}; font-size:13px;")
        lesson_layout.addWidget(self.lesson_summary)
        self.lesson_steps: list[QLabel] = []
        for _ in range(4):
            step = QLabel("")
            step.setWordWrap(True)
            step.setStyleSheet(f"padding:8px 10px; border:1px solid {BORDER}; border-radius:10px;")
            lesson_layout.addWidget(step)
            self.lesson_steps.append(step)
        outer.addWidget(lesson_card)

        tip_card = _card()
        tip_layout = QVBoxLayout(tip_card)
        tip_layout.setContentsMargins(18, 18, 18, 18)
        tip_layout.setSpacing(8)
        tip_title = QLabel("Focus Tip")
        tip_title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        tip_layout.addWidget(tip_title)
        self.tip_label = QLabel("")
        self.tip_label.setWordWrap(True)
        self.tip_label.setStyleSheet(f"color:{TEXT_MUTED}; font-size:13px;")
        tip_layout.addWidget(self.tip_label)
        outer.addWidget(tip_card)
        outer.addStretch()

    def refresh(self):
        progress = db.get_today_progress()
        self.date_label.setText(date.today().strftime("%A, %B %d, %Y"))
        streak = progress.get("streak_days", 1)
        xp = progress.get("xp_earned", 0)
        self.streak_label.setText(f"{streak}-day streak  |  Build momentum with one focused session at a time.")
        self.xp_label.setText(f"{xp} XP today")

        words_learned = progress.get("words_learned", 0)
        words_reviewed = progress.get("words_reviewed", 0)
        reading_sessions = progress.get("reading_sessions", 0)
        listening_sessions = progress.get("listening_sessions", 0)
        writing_sessions = progress.get("writing_sessions", 0)
        speaking_sessions = progress.get("speaking_sessions", 0)
        targets = db.get_daily_plan_targets()

        self.words_card.set_value(str(words_learned), "Target: 8-10 new words.")
        self.review_card.set_value(str(words_reviewed), "Target: review 15 words.")
        self.reading_card.set_value(str(reading_sessions), "Target: 1-2 reading blocks.")
        self.output_card.set_value(str(writing_sessions + speaking_sessions), "Writing + speaking + image description.")

        plan_values = [
            ("Vocabulary", words_learned + words_reviewed, targets.get("words", 10) + targets.get("review", 15)),
            ("Reading", reading_sessions, targets.get("reading", 2)),
            ("Listening", listening_sessions, targets.get("listening", 2)),
            ("Output", writing_sessions + speaking_sessions, targets.get("output", 2) + targets.get("speaking", 1)),
        ]
        for (label, current, target), (_, bar, status) in zip(plan_values, self.plan_items):
            bar.setMaximum(target)
            bar.setValue(min(current, target))
            if current >= target:
                status.setText("Done")
                status.setStyleSheet(f"color:{ACCENT_ALT}; font-size:12px; font-weight:700;")
            else:
                status.setText(f"{current}/{target}")
                status.setStyleSheet(f"color:{TEXT_MUTED}; font-size:12px;")

        total_sessions = words_learned + words_reviewed + reading_sessions + listening_sessions + writing_sessions + speaking_sessions
        current_stage = 0
        if total_sessions >= 10:
            current_stage = 1
        if total_sessions >= 25:
            current_stage = 2
        if total_sessions >= 45:
            current_stage = 3

        self.lesson_summary.setText(
            "A balanced path helps the learner move from input to active output: build vocabulary, read with support, shadow natural English, then create their own sentences."
        )

        steps = [
            ("1. Foundation", "Flashcards, core vocabulary, short listening."),
            ("2. Guided Input", "Reading with lookup, translation check, grammar support."),
            ("3. Active Output", "Writing practice, image description, speaking shadowing."),
            ("4. Confidence Loop", "Conversation coaching, review mistakes, repeat weak areas."),
        ]
        for idx, (title, desc) in enumerate(steps):
            active = idx <= current_stage
            color = ACCENT_ALT if idx < current_stage else ACCENT_WARN if idx == current_stage else TEXT_MUTED
            self.lesson_steps[idx].setStyleSheet(
                f"padding:8px 10px; border:1px solid {BORDER}; border-radius:10px; color:{color};"
            )
            prefix = "Current" if idx == current_stage else "Ready" if idx < current_stage else "Next"
            self.lesson_steps[idx].setText(f"{prefix}: {title}\n{desc}")

        if speaking_sessions == 0:
            self.tip_label.setText("Best next step: open Speaking Lab and do one shadowing round plus one coached response. Spoken output is the missing bridge between recognition and fluency.")
        elif writing_sessions == 0:
            self.tip_label.setText("Best next step: open Image Lab or Writing and produce 4-6 original sentences. Output practice is the fastest way to turn passive knowledge into usable English.")
        elif reading_sessions == 0:
            self.tip_label.setText("Best next step: open Reading and complete one passage. Use word click-lookup to convert unknown vocabulary into active notes.")
        elif listening_sessions == 0:
            self.tip_label.setText("Best next step: do one short dictation in Listening, then repeat it aloud once for shadowing.")
        else:
            self.tip_label.setText("Your plan is balanced today. Use Speaking Lab for one final shadowing round and one coached response to lock the language in memory.")

        for key, spin in self.target_inputs.items():
            spin.blockSignals(True)
            spin.setValue(targets.get(key, 1))
            spin.blockSignals(False)

    def _save_targets(self):
        db.set_json_setting("daily_plan_targets", {key: spin.value() for key, spin in self.target_inputs.items()})
        self.refresh()
