"""Writing widget with plan, draft, and improve workflow."""
from __future__ import annotations

import random

from PySide6.QtCore import QThread, Signal, Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..modules import ai_module
from ..modules import database as db
from .content_builder import ContentBuilderWidget
from .styles import ACCENT, ACCENT_ALT, BG_INPUT, BORDER, TEXT_MUTED, app_font, card_style, tab_style

TOPICS = [
    "Introduce yourself",
    "Describe your hometown",
    "The importance of learning English",
    "Environmental problems in Vietnam",
    "Advantages of technology",
    "My dream job",
    "A formal email to a company",
    "An informal email to a friend",
    "Describe a memorable trip",
    "Healthy lifestyle habits",
    "Social media: benefits and drawbacks",
    "A person you admire",
]
LEVELS = ["A1", "A2", "B1", "B2", "C1"]
MODES = ["Paragraph", "Email", "Opinion", "Journal"]


class WritingPlanWorker(QThread):
    result = Signal(dict)
    error = Signal(str)

    def __init__(self, api_key: str, topic: str, level: str, mode: str):
        super().__init__()
        self.api_key = api_key
        self.topic = topic
        self.level = level
        self.mode = mode

    def run(self):
        try:
            self.result.emit(ai_module.generate_writing_support(self.api_key, self.topic, self.level, self.mode.lower()))
        except Exception as exc:
            self.error.emit(str(exc))


class WritingFeedbackWorker(QThread):
    result = Signal(dict)
    error = Signal(str)

    def __init__(self, api_key: str, topic: str, content: str):
        super().__init__()
        self.api_key = api_key
        self.topic = topic
        self.content = content

    def run(self):
        try:
            self.result.emit(ai_module.check_writing(self.api_key, self.topic, self.content))
        except Exception as exc:
            self.error.emit(str(exc))


def _card(radius: int = 12) -> QFrame:
    frame = QFrame()
    frame.setObjectName("card")
    frame.setStyleSheet(f"QFrame#card{{{card_style(radius)}}}")
    return frame


class WritingWidget(QWidget):
    def __init__(self, get_api_key_fn, parent=None):
        super().__init__(parent)
        self.get_api_key = get_api_key_fn
        self.plan_worker = None
        self.feedback_worker = None
        self._build_ui()
        self._ai_timer = QTimer(self)
        self._ai_timer.timeout.connect(self._refresh_ai_buttons)
        self._ai_timer.start(1500)
        self._refresh_ai_buttons()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        tabs = QTabWidget()
        tabs.setFont(app_font(11))
        tabs.setStyleSheet(tab_style())

        practice = QWidget()
        layout = QVBoxLayout(practice)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        title = QLabel("Writing Studio")
        title.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        layout.addWidget(title)

        subtitle = QLabel("Work in three steps: understand the task, plan ideas, write a draft, then improve it with AI feedback.")
        subtitle.setStyleSheet(f"color:{TEXT_MUTED};font-size:13px;")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        cfg = _card()
        cfg_lay = QHBoxLayout(cfg)
        cfg_lay.setContentsMargins(18, 14, 18, 14)
        cfg_lay.setSpacing(12)
        cfg_lay.addWidget(QLabel("Topic"))
        self.topic_cb = QComboBox()
        self.topic_cb.addItems(TOPICS)
        self.topic_cb.setMinimumWidth(240)
        cfg_lay.addWidget(self.topic_cb)
        cfg_lay.addWidget(QLabel("Level"))
        self.level_cb = QComboBox()
        self.level_cb.addItems(LEVELS)
        self.level_cb.setCurrentText("B1")
        cfg_lay.addWidget(self.level_cb)
        cfg_lay.addWidget(QLabel("Mode"))
        self.mode_cb = QComboBox()
        self.mode_cb.addItems(MODES)
        cfg_lay.addWidget(self.mode_cb)
        self.random_btn = QPushButton("Random")
        self.random_btn.clicked.connect(self._random_topic)
        cfg_lay.addWidget(self.random_btn)
        cfg_lay.addStretch()
        self.plan_btn = QPushButton("Build Plan")
        self.plan_btn.setObjectName("btnPrimary")
        self.plan_btn.setFixedHeight(42)
        self.plan_btn.clicked.connect(self._build_plan)
        cfg_lay.addWidget(self.plan_btn)
        layout.addWidget(cfg)

        status_card = _card(10)
        status_lay = QHBoxLayout(status_card)
        status_lay.setContentsMargins(16, 10, 16, 10)
        status_lay.setSpacing(12)
        self.status_lbl = QLabel("Build a writing plan first, then draft your answer.")
        self.status_lbl.setStyleSheet(f"color:{TEXT_MUTED};font-size:12px;")
        status_lay.addWidget(self.status_lbl)
        status_lay.addStretch()
        self.goal_lbl = QLabel("Suggested flow: Plan -> Draft -> Improve")
        self.goal_lbl.setStyleSheet(f"color:{ACCENT};font-size:12px;font-weight:700;")
        status_lay.addWidget(self.goal_lbl)
        layout.addWidget(status_card)

        self.loading = QProgressBar()
        self.loading.setRange(0, 0)
        self.loading.setVisible(False)
        self.loading.setFixedHeight(5)
        layout.addWidget(self.loading)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setStyleSheet(f"QSplitter::handle{{background:{BORDER};width:2px;}}")

        task_card = _card()
        task_lay = QVBoxLayout(task_card)
        task_lay.setContentsMargins(18, 16, 18, 16)
        task_lay.setSpacing(10)
        task_title = QLabel("Task & Plan")
        task_title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        task_lay.addWidget(task_title)
        task_hint = QLabel("Start here. Use the plan as a checklist while you write.")
        task_hint.setWordWrap(True)
        task_hint.setStyleSheet(f"color:{TEXT_MUTED};font-size:12px;")
        task_lay.addWidget(task_hint)
        self.plan_view = QTextEdit()
        self.plan_view.setReadOnly(True)
        self.plan_view.setFont(app_font(12))
        self.plan_view.setMinimumHeight(260)
        self.plan_view.setPlaceholderText("AI will build your task breakdown, outline, vocabulary, sentence starters, and checklist here.")
        task_lay.addWidget(self.plan_view)
        splitter.addWidget(task_card)

        draft_card = _card()
        draft_lay = QVBoxLayout(draft_card)
        draft_lay.setContentsMargins(18, 16, 18, 16)
        draft_lay.setSpacing(10)
        draft_header = QHBoxLayout()
        draft_title = QLabel("Draft")
        draft_title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        draft_header.addWidget(draft_title)
        draft_header.addStretch()
        self.word_count_lbl = QLabel("0 words")
        self.word_count_lbl.setStyleSheet(f"color:{TEXT_MUTED};font-size:12px;")
        draft_header.addWidget(self.word_count_lbl)
        draft_lay.addLayout(draft_header)
        draft_hint = QLabel("Write naturally first. Clean up structure and accuracy after you have a full draft.")
        draft_hint.setWordWrap(True)
        draft_hint.setStyleSheet(f"color:{TEXT_MUTED};font-size:12px;")
        draft_lay.addWidget(draft_hint)
        self.editor = QTextEdit()
        self.editor.setFont(app_font(14))
        self.editor.setPlaceholderText("Write your answer here. Follow the outline on the left and keep the checklist in mind.")
        self.editor.setMinimumHeight(320)
        self.editor.textChanged.connect(self._update_word_count)
        self.editor.setStyleSheet(
            f"""
            QTextEdit{{
                background:{BG_INPUT};border:none;border-radius:10px;
                padding:16px;font-size:15px;line-height:1.7;
            }}
            """
        )
        draft_lay.addWidget(self.editor)
        draft_btns = QHBoxLayout()
        self.feedback_btn = QPushButton("Get Feedback")
        self.feedback_btn.setObjectName("btnSuccess")
        self.feedback_btn.setFixedHeight(42)
        self.feedback_btn.clicked.connect(self._get_feedback)
        draft_btns.addWidget(self.feedback_btn)
        clear_btn = QPushButton("Clear Draft")
        clear_btn.setFixedHeight(42)
        clear_btn.clicked.connect(self.editor.clear)
        draft_btns.addWidget(clear_btn)
        draft_btns.addStretch()
        draft_lay.addLayout(draft_btns)
        splitter.addWidget(draft_card)

        feedback_card = _card()
        feedback_lay = QVBoxLayout(feedback_card)
        feedback_lay.setContentsMargins(18, 16, 18, 16)
        feedback_lay.setSpacing(10)
        feedback_header = QHBoxLayout()
        feedback_title = QLabel("Improve")
        feedback_title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        feedback_header.addWidget(feedback_title)
        feedback_header.addStretch()
        self.score_lbl = QLabel("Score: -")
        self.score_lbl.setStyleSheet(f"color:{ACCENT};font-size:14px;font-weight:700;")
        feedback_header.addWidget(self.score_lbl)
        feedback_lay.addLayout(feedback_header)
        feedback_hint = QLabel("Use this panel to spot weak sentences, then revise your draft with the best suggestions.")
        feedback_hint.setWordWrap(True)
        feedback_hint.setStyleSheet(f"color:{TEXT_MUTED};font-size:12px;")
        feedback_lay.addWidget(feedback_hint)
        self.feedback_view = QTextEdit()
        self.feedback_view.setReadOnly(True)
        self.feedback_view.setFont(app_font(12))
        self.feedback_view.setMinimumHeight(320)
        self.feedback_view.setPlaceholderText("Detailed feedback, corrections, and a better version will appear here.")
        feedback_lay.addWidget(self.feedback_view)
        splitter.addWidget(feedback_card)

        splitter.setSizes([420, 520, 420])
        layout.addWidget(splitter, stretch=1)
        tabs.addTab(practice, "Practice")

        builder_wrap = QWidget()
        builder_lay = QVBoxLayout(builder_wrap)
        builder_lay.setContentsMargins(24, 20, 24, 20)
        builder_lay.setSpacing(10)
        builder_title = QLabel("Writing Resources")
        builder_title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        builder_lay.addWidget(builder_title)
        builder_sub = QLabel("Use this tab only to build extra writing materials for future lessons. The main study flow stays in Practice.")
        builder_sub.setStyleSheet(f"color:{TEXT_MUTED};font-size:13px;")
        builder_lay.addWidget(builder_sub)
        self.builder = ContentBuilderWidget("writing")
        builder_lay.addWidget(self.builder, stretch=1)
        tabs.addTab(builder_wrap, "Resources")

        outer.addWidget(tabs)

    def _random_topic(self):
        self.topic_cb.setCurrentIndex(random.randint(0, len(TOPICS) - 1))

    def _update_word_count(self):
        words = len(self.editor.toPlainText().split()) if self.editor.toPlainText().strip() else 0
        self.word_count_lbl.setText(f"{words} words")

    def _build_plan(self):
        from ..modules.ai_module import _use_web, get_web_job_status

        if not self.get_api_key() and not _use_web():
            self.plan_view.setPlainText("Gemini Web is not connected.")
            self.status_lbl.setText("Open Gemini Web to build a writing plan.")
            return
        busy_job = get_web_job_status()
        if busy_job:
            self.status_lbl.setText(f"Gemini Web is busy: {busy_job}")
            return
        self.loading.setVisible(True)
        self.plan_btn.setEnabled(False)
        self.status_lbl.setText("Building writing plan...")
        self.plan_view.setPlainText("Creating task, outline, vocabulary, and checklist...")
        self.plan_worker = WritingPlanWorker(
            self.get_api_key(),
            self.topic_cb.currentText(),
            self.level_cb.currentText(),
            self.mode_cb.currentText(),
        )
        self.plan_worker.result.connect(self._on_plan_ready)
        self.plan_worker.error.connect(self._on_plan_error)
        self.plan_worker.start()

    def _on_plan_ready(self, result: dict):
        self.loading.setVisible(False)
        self.plan_btn.setEnabled(True)
        self.status_lbl.setText("Plan ready. Start drafting when you are ready.")
        self.plan_view.setPlainText(result.get("pack", ""))
        self._refresh_ai_buttons()

    def _on_plan_error(self, error: str):
        self.loading.setVisible(False)
        self.plan_btn.setEnabled(True)
        self.status_lbl.setText(f"Could not build plan: {error}")
        self.plan_view.setPlainText(f"Error: {error}")
        self._refresh_ai_buttons()

    def _get_feedback(self):
        from ..modules.ai_module import _use_web, get_web_job_status

        if not self.get_api_key() and not _use_web():
            self.feedback_view.setPlainText("Gemini Web is not connected.")
            self.status_lbl.setText("Open Gemini Web to review this draft.")
            return
        busy_job = get_web_job_status()
        if busy_job:
            self.status_lbl.setText(f"Gemini Web is busy: {busy_job}")
            return
        content = self.editor.toPlainText().strip()
        if len(content) < 30:
            self.feedback_view.setPlainText("Write a longer draft first.")
            return
        self.loading.setVisible(True)
        self.feedback_btn.setEnabled(False)
        self.status_lbl.setText("Reviewing your draft...")
        self.feedback_view.setPlainText("Checking grammar, structure, vocabulary, and overall quality...")
        self.feedback_worker = WritingFeedbackWorker(self.get_api_key(), self.topic_cb.currentText(), content)
        self.feedback_worker.result.connect(self._on_feedback_ready)
        self.feedback_worker.error.connect(self._on_feedback_error)
        self.feedback_worker.start()

    def _on_feedback_ready(self, result: dict):
        self.loading.setVisible(False)
        self.feedback_btn.setEnabled(True)
        score = result.get("score", 0)
        self.score_lbl.setText(f"Score: {score}/10")
        self.score_lbl.setStyleSheet(
            f"color:{ACCENT_ALT if score >= 7 else '#f59e0b' if score >= 5 else '#f87171'};font-size:14px;font-weight:700;"
        )
        self.feedback_view.setPlainText(result.get("feedback", ""))
        self.status_lbl.setText("Feedback ready. Review the suggestions on the right.")
        db.save_writing(self.topic_cb.currentText(), self.editor.toPlainText(), result.get("feedback", ""), score)
        self._refresh_ai_buttons()

    def _on_feedback_error(self, error: str):
        self.loading.setVisible(False)
        self.feedback_btn.setEnabled(True)
        self.status_lbl.setText(f"Could not review draft: {error}")
        self.feedback_view.setPlainText(f"Error: {error}")
        self._refresh_ai_buttons()

    def _refresh_ai_buttons(self):
        busy_job = ai_module.get_web_job_status()
        plan_running = bool(self.plan_worker and self.plan_worker.isRunning())
        feedback_running = bool(self.feedback_worker and self.feedback_worker.isRunning())
        self.plan_btn.setEnabled(not plan_running and not feedback_running and not busy_job)
        self.feedback_btn.setEnabled(not plan_running and not feedback_running and not busy_job)
        if busy_job and not (plan_running or feedback_running):
            self.status_lbl.setText(f"Gemini Web is busy: {busy_job}")
            self.plan_btn.setToolTip(f"Gemini Web is busy: {busy_job}")
            self.feedback_btn.setToolTip(f"Gemini Web is busy: {busy_job}")
        else:
            self.plan_btn.setToolTip("")
            self.feedback_btn.setToolTip("")
