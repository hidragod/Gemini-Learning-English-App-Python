"""Speaking and shadowing practice widget."""
from __future__ import annotations

from PySide6.QtCore import QThread, Signal, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..modules import ai_module, database as db, tts_module
from .styles import card_style


LEVELS = ["A1", "A2", "B1", "B2", "C1"]


def _card() -> QFrame:
    frame = QFrame()
    frame.setObjectName("card")
    frame.setStyleSheet(f"QFrame#card{{{card_style(12)}}}")
    return frame


class TopicWorker(QThread):
    done = Signal(str)
    error = Signal(str)

    def __init__(self, api_key: str, level: str):
        super().__init__()
        self.api_key = api_key
        self.level = level

    def run(self):
        try:
            self.done.emit(ai_module.get_speaking_topic(self.api_key, self.level))
        except Exception as exc:
            self.error.emit(str(exc))


class CoachWorker(QThread):
    done = Signal(str)
    error = Signal(str)

    def __init__(self, api_key: str, history: list, user_message: str):
        super().__init__()
        self.api_key = api_key
        self.history = history
        self.user_message = user_message

    def run(self):
        try:
            self.done.emit(ai_module.chat_practice(self.api_key, self.history, self.user_message))
        except Exception as exc:
            self.error.emit(str(exc))


class AudioWorker(QThread):
    error = Signal(str)

    def __init__(self, text: str, slow: bool = False):
        super().__init__()
        self.text = text
        self.slow = slow

    def run(self):
        try:
            tts_module.speak_sentence(self.text, slow=self.slow)
        except Exception as exc:
            self.error.emit(str(exc))


class SpeakingWidget(QWidget):
    def __init__(self, get_api_key_fn, parent=None):
        super().__init__(parent)
        self.get_api_key = get_api_key_fn
        self._history: list[dict] = []
        self._topic_worker = None
        self._coach_worker = None
        self._audio_worker = None
        self._build_ui()
        self._load_history_list()
        self._ai_timer = QTimer(self)
        self._ai_timer.timeout.connect(self._refresh_ai_buttons)
        self._ai_timer.start(1500)
        self._refresh_ai_buttons()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(14)

        title = QLabel("Speaking Lab")
        title.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        outer.addWidget(title)

        subtitle = QLabel("Daily speaking topic, shadowing audio, and AI conversation coaching in one place.")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color:#98a2b3; font-size:13px;")
        outer.addWidget(subtitle)

        top_card = _card()
        top_layout = QHBoxLayout(top_card)
        top_layout.setContentsMargins(18, 18, 18, 18)
        top_layout.setSpacing(12)

        self.level_cb = QComboBox()
        self.level_cb.addItems(LEVELS)
        self.level_cb.setCurrentText("B1")
        self.level_cb.setFixedWidth(90)
        top_layout.addWidget(self.level_cb)

        self.topic_btn = QPushButton("New Topic")
        self.topic_btn.setObjectName("btnPrimary")
        self.topic_btn.clicked.connect(self._generate_topic)
        top_layout.addWidget(self.topic_btn)

        self.reload_btn = QPushButton("Reload Saved")
        self.reload_btn.clicked.connect(self._load_history_list)
        top_layout.addWidget(self.reload_btn)

        self.play_btn = QPushButton("Play Topic")
        self.play_btn.clicked.connect(lambda: self._speak(self.topic_text.toPlainText(), False))
        top_layout.addWidget(self.play_btn)

        self.slow_btn = QPushButton("Slow")
        self.slow_btn.clicked.connect(lambda: self._speak(self.topic_text.toPlainText(), True))
        top_layout.addWidget(self.slow_btn)
        top_layout.addStretch()
        outer.addWidget(top_card)

        self.status_lbl = QLabel("Create a topic, speak aloud, then ask the coach for feedback.")
        self.status_lbl.setStyleSheet("color:#98a2b3; font-size:12px;")
        outer.addWidget(self.status_lbl)

        self.topic_text = QTextEdit()
        self.topic_text.setReadOnly(True)
        self.topic_text.setMinimumHeight(220)
        self.topic_text.setFont(QFont("Segoe UI", 12))
        self.topic_text.setPlaceholderText("Generate a daily speaking topic first.")
        outer.addWidget(self.topic_text)

        split = QHBoxLayout()
        split.setSpacing(14)

        left = _card()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(18, 18, 18, 18)
        left_layout.setSpacing(10)
        left_title = QLabel("Your Practice")
        left_title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        left_layout.addWidget(left_title)
        left_subtitle = QLabel("Use this panel as your speaking journal or quick speaking script.")
        left_subtitle.setWordWrap(True)
        left_subtitle.setStyleSheet("color:#98a2b3; font-size:12px;")
        left_layout.addWidget(left_subtitle)

        self.user_input = QTextEdit()
        self.user_input.setMinimumHeight(220)
        self.user_input.setFont(QFont("Segoe UI", 13))
        self.user_input.setPlaceholderText("Answer the topic or describe what you want to practice speaking.")
        left_layout.addWidget(self.user_input)

        self.send_btn = QPushButton("Get Coach Feedback")
        self.send_btn.setObjectName("btnSuccess")
        self.send_btn.clicked.connect(self._send_to_coach)
        left_layout.addWidget(self.send_btn)

        self.shadowing_hint = QLabel("Tip: listen once, repeat aloud, then type your answer from memory.")
        self.shadowing_hint.setWordWrap(True)
        left_layout.addWidget(self.shadowing_hint)

        right = _card()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(18, 18, 18, 18)
        right_layout.setSpacing(10)
        right_title = QLabel("AI Coach")
        right_title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        right_layout.addWidget(right_title)
        right_subtitle = QLabel("The coach highlights stronger wording, clearer grammar, and useful follow-up ideas.")
        right_subtitle.setWordWrap(True)
        right_subtitle.setStyleSheet("color:#98a2b3; font-size:12px;")
        right_layout.addWidget(right_subtitle)

        self.feedback_text = QTextEdit()
        self.feedback_text.setReadOnly(True)
        self.feedback_text.setMinimumHeight(280)
        self.feedback_text.setFont(QFont("Segoe UI", 12))
        self.feedback_text.setPlaceholderText("The AI coach will suggest better sentences and conversation follow-ups.")
        right_layout.addWidget(self.feedback_text)

        history_title = QLabel("Recent Speaking Sessions")
        history_title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        right_layout.addWidget(history_title)
        self.history_list = QListWidget()
        self.history_list.setMaximumHeight(150)
        self.history_list.itemSelectionChanged.connect(self._load_selected_session)
        right_layout.addWidget(self.history_list)

        split.addWidget(left, 1)
        split.addWidget(right, 1)
        outer.addLayout(split)

    def _generate_topic(self):
        busy_job = ai_module.get_web_job_status()
        if busy_job:
            self.feedback_text.setPlainText(f"Gemini Web is busy: {busy_job}")
            self.status_lbl.setText(f"Gemini Web is busy: {busy_job}")
            return
        self.topic_btn.setEnabled(False)
        self.status_lbl.setText("Creating a fresh speaking topic...")
        self.topic_text.setPlainText("Creating a new speaking topic...")
        self._topic_worker = TopicWorker(self.get_api_key(), self.level_cb.currentText())
        self._topic_worker.done.connect(self._on_topic_done)
        self._topic_worker.error.connect(self._on_topic_error)
        self._topic_worker.start()

    def _on_topic_done(self, text: str):
        self.topic_btn.setEnabled(True)
        self.topic_text.setPlainText(text)
        self.feedback_text.clear()
        self.status_lbl.setText("Topic ready. Listen once, speak, then type your response.")
        self._history.clear()
        self._refresh_ai_buttons()

    def _on_topic_error(self, error: str):
        self.topic_btn.setEnabled(True)
        self.topic_text.setPlainText(f"Could not create topic: {error}")
        self.status_lbl.setText(f"Could not create topic: {error}")
        self._refresh_ai_buttons()

    def _send_to_coach(self):
        message = self.user_input.toPlainText().strip()
        if not message:
            QMessageBox.warning(self, "No practice text", "Write something first.")
            return
        busy_job = ai_module.get_web_job_status()
        if busy_job:
            self.feedback_text.setPlainText(f"Gemini Web is busy: {busy_job}")
            self.status_lbl.setText(f"Gemini Web is busy: {busy_job}")
            return

        self.send_btn.setEnabled(False)
        self.status_lbl.setText("Reviewing your response...")
        self.feedback_text.setPlainText("Reviewing your response...")
        self._coach_worker = CoachWorker(self.get_api_key(), self._history, message)
        self._coach_worker.done.connect(self._on_coach_done)
        self._coach_worker.error.connect(self._on_coach_error)
        self._coach_worker.start()

    def _on_coach_done(self, text: str):
        user_message = self.user_input.toPlainText().strip()
        self._history.append({"role": "user", "content": user_message})
        self._history.append({"role": "assistant", "content": text})
        self.send_btn.setEnabled(True)
        self.feedback_text.setPlainText(text)
        self.status_lbl.setText("Coach feedback ready.")
        db.save_speaking_session(
            self.level_cb.currentText(),
            self.topic_text.toPlainText().strip(),
            user_message,
            text,
        )
        self._load_history_list()
        self._refresh_ai_buttons()

    def _on_coach_error(self, error: str):
        self.send_btn.setEnabled(True)
        self.feedback_text.setPlainText(f"Could not review response: {error}")
        self.status_lbl.setText(f"Could not review response: {error}")
        self._refresh_ai_buttons()

    def _speak(self, text: str, slow: bool):
        text = text.strip()
        if not text:
            return
        self._audio_worker = AudioWorker(text, slow=slow)
        self._audio_worker.error.connect(
            lambda error: QMessageBox.warning(self, "Audio error", error)
        )
        self._audio_worker.start()

    def _load_history_list(self):
        self._saved_sessions = db.get_all_speaking(limit=20)
        self.history_list.clear()
        for item in self._saved_sessions:
            topic = (item.get("topic_text") or "Speaking session").splitlines()[0][:36]
            self.history_list.addItem(f"{item.get('level', 'B1')}  |  {topic}")

    def _load_selected_session(self):
        if not self.history_list.selectedIndexes():
            return
        item = self._saved_sessions[self.history_list.selectedIndexes()[0].row()]
        self.topic_text.setPlainText(item.get("topic_text", ""))
        self.user_input.setPlainText(item.get("user_text", ""))
        self.feedback_text.setPlainText(item.get("coach_feedback", ""))
        level = item.get("level", "B1")
        idx = self.level_cb.findText(level)
        if idx >= 0:
            self.level_cb.setCurrentIndex(idx)

    def _refresh_ai_buttons(self):
        busy_job = ai_module.get_web_job_status()
        topic_running = bool(self._topic_worker and self._topic_worker.isRunning())
        coach_running = bool(self._coach_worker and self._coach_worker.isRunning())
        allow = not topic_running and not coach_running and not busy_job
        self.topic_btn.setEnabled(allow)
        self.send_btn.setEnabled(allow)
        if busy_job and not (topic_running or coach_running):
            self.topic_btn.setToolTip(f"Gemini Web is busy: {busy_job}")
            self.send_btn.setToolTip(f"Gemini Web is busy: {busy_job}")
        else:
            self.topic_btn.setToolTip("")
            self.send_btn.setToolTip("")
