"""Listening practice widget with builder and database library loading."""
from __future__ import annotations

import difflib
import json
import random
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..modules import database as db
from ..modules import tts_module
from .content_builder import ContentBuilderWidget
from .styles import (
    ACCENT,
    ACCENT_ALT,
    ACCENT_WARN,
    BORDER,
    TEXT_MAIN,
    TEXT_MUTED,
    card_style,
    display_font,
    tab_style,
)


DEFAULT_SENTENCES = [
    "The weather in Vietnam is hot and humid in the summer.",
    "She studies English every day to improve her communication skills.",
    "Learning a new language takes time, patience, and dedication.",
    "Ho Chi Minh City is the largest city in Vietnam.",
    "Can you tell me how to get to the nearest supermarket?",
    "I would like to apply for the position of marketing manager.",
    "The meeting has been rescheduled to next Thursday at ten o'clock.",
    "Environmental pollution is one of the most serious problems today.",
    "Technology has changed the way we communicate with each other.",
    "Please make sure you submit the report before the deadline.",
]


class AudioWorker(QThread):
    finished = Signal()
    error = Signal(str)

    def __init__(self, text: str, slow: bool = False):
        super().__init__()
        self.text = text
        self.slow = slow

    def run(self):
        try:
            path = tts_module.text_to_speech(self.text, slow=self.slow)
            tts_module.play_audio(path)
            self.finished.emit()
        except Exception as exc:
            self.error.emit(str(exc))


def _card() -> QFrame:
    frame = QFrame()
    frame.setObjectName("card")
    frame.setStyleSheet(f"QFrame#card{{{card_style(12)}}}")
    return frame


class ListeningWidget(QWidget):
    def __init__(self, get_api_key_fn=None, parent=None):
        super().__init__(parent)
        self.get_api_key = get_api_key_fn
        self.worker = None
        self._sentences = list(DEFAULT_SENTENCES)
        self._current = ""
        self._idx = 0
        self._answer_logged = False
        self._build_ui()
        self._pick_sentence()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        tabs = QTabWidget()
        tabs.setStyleSheet(tab_style())
        tabs.setFont(QFont("Segoe UI", 11))

        practice = QWidget()
        practice_layout = QVBoxLayout(practice)
        practice_layout.setContentsMargins(24, 20, 24, 20)
        practice_layout.setSpacing(16)

        title = QLabel("Listening Practice")
        title.setFont(display_font(20))
        practice_layout.addWidget(title)

        subtitle = QLabel("Listen carefully, type exactly what you hear, then compare your version with the original sentence.")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"color:{TEXT_MUTED};")
        practice_layout.addWidget(subtitle)

        status_row = QHBoxLayout()
        self.src_lbl = QLabel(f"{len(self._sentences)} sentences loaded")
        self.src_lbl.setStyleSheet(f"color:{ACCENT_ALT}; font-weight:600;")
        status_row.addWidget(self.src_lbl)
        status_row.addStretch()

        self.import_btn = QPushButton("Load JSON")
        self.import_btn.clicked.connect(self._import_json)
        status_row.addWidget(self.import_btn)

        self.load_db_btn = QPushButton("Load Library")
        self.load_db_btn.setToolTip("Load listening sentences saved in the database library.")
        self.load_db_btn.clicked.connect(self._load_from_db)
        status_row.addWidget(self.load_db_btn)
        practice_layout.addLayout(status_row)

        player_card = _card()
        player_layout = QVBoxLayout(player_card)
        player_layout.setContentsMargins(24, 20, 24, 20)
        player_layout.setSpacing(14)

        counter_row = QHBoxLayout()
        self.cnt_lbl = QLabel("Sentence 1")
        self.cnt_lbl.setStyleSheet(f"color:{TEXT_MUTED};")
        counter_row.addWidget(self.cnt_lbl)
        counter_row.addStretch()
        self.mode_lbl = QLabel("Practice")
        self.mode_lbl.setStyleSheet(f"color:{ACCENT}; font-weight:600;")
        counter_row.addWidget(self.mode_lbl)
        player_layout.addLayout(counter_row)

        self.audio_lbl = QLabel("Press Play to hear the sentence.")
        self.audio_lbl.setFont(QFont("Segoe UI", 16))
        self.audio_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.audio_lbl.setStyleSheet(f"color:{TEXT_MUTED}; padding:8px 0;")
        self.audio_lbl.setWordWrap(True)
        player_layout.addWidget(self.audio_lbl)

        buttons = QHBoxLayout()
        self.play_btn = QPushButton("Play")
        self.play_btn.setObjectName("btnPrimary")
        self.play_btn.clicked.connect(lambda: self._play(False))
        buttons.addWidget(self.play_btn)

        self.slow_btn = QPushButton("Slow")
        self.slow_btn.clicked.connect(lambda: self._play(True))
        buttons.addWidget(self.slow_btn)

        self.replay_btn = QPushButton("Replay")
        self.replay_btn.clicked.connect(lambda: self._play(False))
        buttons.addWidget(self.replay_btn)

        buttons.addStretch()
        self.new_btn = QPushButton("Next")
        self.new_btn.clicked.connect(self._next_sentence)
        buttons.addWidget(self.new_btn)
        player_layout.addLayout(buttons)

        self.play_bar = QProgressBar()
        self.play_bar.setRange(0, 0)
        self.play_bar.setVisible(False)
        self.play_bar.setFixedHeight(6)
        player_layout.addWidget(self.play_bar)
        practice_layout.addWidget(player_card)

        answer_card = _card()
        answer_layout = QVBoxLayout(answer_card)
        answer_layout.setContentsMargins(20, 18, 20, 18)
        answer_layout.setSpacing(12)

        answer_head = QHBoxLayout()
        answer_title = QLabel("Type What You Hear")
        answer_title.setFont(display_font(14))
        answer_head.addWidget(answer_title)
        answer_head.addStretch()
        self.acc_lbl = QLabel("Accuracy: -")
        self.acc_lbl.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.acc_lbl.setStyleSheet(f"color:{TEXT_MUTED};")
        answer_head.addWidget(self.acc_lbl)
        answer_layout.addLayout(answer_head)

        self.ans_input = QTextEdit()
        self.ans_input.setFixedHeight(96)
        self.ans_input.setFont(QFont("Segoe UI", 14))
        self.ans_input.setPlaceholderText("Type the sentence you heard...")
        answer_layout.addWidget(self.ans_input)

        action_row = QHBoxLayout()
        self.check_btn = QPushButton("Check Answer")
        self.check_btn.setObjectName("btnSuccess")
        self.check_btn.clicked.connect(self._check)
        action_row.addWidget(self.check_btn)

        self.show_btn = QPushButton("Show Answer")
        self.show_btn.clicked.connect(self._show_ans)
        action_row.addWidget(self.show_btn)
        action_row.addStretch()
        answer_layout.addLayout(action_row)
        practice_layout.addWidget(answer_card)

        self.res_card = _card()
        result_layout = QVBoxLayout(self.res_card)
        result_layout.setContentsMargins(18, 16, 18, 16)
        result_layout.setSpacing(8)
        self.res_correct = QLabel()
        self.res_correct.setWordWrap(True)
        self.res_correct.setStyleSheet(f"color:{ACCENT_ALT};")
        self.res_correct.setFont(QFont("Segoe UI", 13))
        result_layout.addWidget(self.res_correct)
        self.res_diff = QLabel()
        self.res_diff.setWordWrap(True)
        self.res_diff.setTextFormat(Qt.TextFormat.RichText)
        self.res_diff.setFont(QFont("Segoe UI", 13))
        result_layout.addWidget(self.res_diff)
        self.res_card.setVisible(False)
        practice_layout.addWidget(self.res_card)
        practice_layout.addStretch()

        tabs.addTab(practice, "Practice")

        builder_page = QWidget()
        builder_layout = QVBoxLayout(builder_page)
        builder_layout.setContentsMargins(24, 20, 24, 20)
        builder_layout.setSpacing(12)
        builder_title = QLabel("Listening Builder")
        builder_title.setFont(display_font(16))
        builder_layout.addWidget(builder_title)
        builder_subtitle = QLabel("Generate sentence sets, save them to the database library, then use them in the practice tab.")
        builder_subtitle.setWordWrap(True)
        builder_subtitle.setStyleSheet(f"color:{TEXT_MUTED};")
        builder_layout.addWidget(builder_subtitle)

        self.builder = ContentBuilderWidget("listening")
        self.builder.imported.connect(self._on_builder_imported)
        builder_layout.addWidget(self.builder, 1)

        use_btn = QPushButton("Use Builder Sentences in Practice")
        use_btn.setObjectName("btnPrimary")
        use_btn.clicked.connect(self._use_builder_items)
        builder_layout.addWidget(use_btn)

        tabs.addTab(builder_page, "Builder")
        outer.addWidget(tabs)

    def _pick_sentence(self):
        self._current = self._sentences[self._idx % len(self._sentences)] if self._sentences else random.choice(DEFAULT_SENTENCES)
        self._answer_logged = False
        self.cnt_lbl.setText(f"Sentence {self._idx + 1} / {len(self._sentences)}")
        self.audio_lbl.setText("Press Play to hear the sentence.")
        self.audio_lbl.setStyleSheet(f"color:{TEXT_MUTED}; padding:8px 0;")
        self.ans_input.clear()
        self.acc_lbl.setText("Accuracy: -")
        self.acc_lbl.setStyleSheet(f"color:{TEXT_MUTED};")
        self.res_card.setVisible(False)

    def _next_sentence(self):
        self._idx = (self._idx + 1) % len(self._sentences) if self._sentences else 0
        self._pick_sentence()

    def _play(self, slow: bool):
        if not self._current:
            return
        self.play_btn.setEnabled(False)
        self.slow_btn.setEnabled(False)
        self.play_bar.setVisible(True)
        self.audio_lbl.setText("Playing audio...")
        self.audio_lbl.setStyleSheet(f"color:{ACCENT}; padding:8px 0;")
        self.worker = AudioWorker(self._current, slow)
        self.worker.finished.connect(self._on_done)
        self.worker.error.connect(self._on_audio_err)
        self.worker.start()

    def _on_done(self):
        self.play_btn.setEnabled(True)
        self.slow_btn.setEnabled(True)
        self.play_bar.setVisible(False)
        self.audio_lbl.setText("Done. Type what you heard.")
        self.audio_lbl.setStyleSheet(f"color:{ACCENT_ALT}; padding:8px 0;")

    def _on_audio_err(self, error: str):
        self.play_btn.setEnabled(True)
        self.slow_btn.setEnabled(True)
        self.play_bar.setVisible(False)
        self.audio_lbl.setText(f"Audio error: {error[:80]}")
        self.audio_lbl.setStyleSheet("color:#f87171; padding:8px 0;")

    def _check(self):
        user_text = self.ans_input.toPlainText().strip()
        if not user_text:
            return
        ratio = difflib.SequenceMatcher(None, user_text.lower(), self._current.lower()).ratio()
        accuracy = int(ratio * 100)
        color = ACCENT_ALT if accuracy >= 80 else ACCENT_WARN if accuracy >= 50 else "#f87171"
        self.acc_lbl.setText(f"Accuracy: {accuracy}%")
        self.acc_lbl.setStyleSheet(f"color:{color}; font-weight:700;")

        self.res_card.setVisible(True)
        self.res_correct.setText(f"Correct: {self._current}")
        diff = difflib.ndiff(user_text.lower().split(), self._current.lower().split())
        parts = []
        for token in diff:
            if token.startswith("  "):
                parts.append(f'<span style="color:{TEXT_MAIN}">{token[2:]}</span>')
            elif token.startswith("+ "):
                parts.append(f'<span style="color:{ACCENT_ALT}; font-weight:bold">[{token[2:]}]</span>')
            elif token.startswith("- "):
                parts.append(f'<span style="color:#f87171; text-decoration:line-through">{token[2:]}</span>')
        self.res_diff.setText("Your version: " + " ".join(parts))

        if not self._answer_logged:
            db.save_listening(self._current, user_text, accuracy / 100)
            self._answer_logged = True

    def _show_ans(self):
        self.res_card.setVisible(True)
        self.res_correct.setText(f"Answer: {self._current}")
        self.res_diff.clear()
        self.audio_lbl.setText(self._current)
        self.audio_lbl.setStyleSheet("color:#93c5fd; padding:8px 0; font-size:15px;")

    def _import_json(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Listening Sentences",
            str(Path.home() / "Downloads"),
            "JSON Files (*.json);;All Files (*)",
        )
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            items = data.get("items", data) if isinstance(data, dict) else data
            sentences = self._extract_sentences(items if isinstance(items, list) else [items])
            if not sentences:
                QMessageBox.warning(self, "No sentences", "No listening sentences were found in this file.")
                return
            self._sentences = sentences
            self._idx = 0
            self.src_lbl.setText(f"{len(sentences)} sentences loaded from file")
            self.mode_lbl.setText("Imported file")
            self._pick_sentence()
        except Exception as exc:
            QMessageBox.critical(self, "Import error", str(exc))

    def _load_from_db(self):
        sentences = db.get_listening_sets(limit=200)
        if not sentences:
            QMessageBox.information(self, "Empty library", "No listening sentences are saved yet. Use Builder and save to the library first.")
            return
        self._sentences = sentences
        self._idx = 0
        self.src_lbl.setText(f"{len(sentences)} sentences loaded from the database library")
        self.mode_lbl.setText("Database library")
        self._pick_sentence()

    def _on_builder_imported(self, items: list):
        sentences = self._extract_sentences(items)
        if sentences:
            self._sentences.extend(sentences)
            self.src_lbl.setText(f"{len(self._sentences)} sentences in the current session")
            self.mode_lbl.setText("Builder import")

    def _use_builder_items(self):
        items = self.builder.get_items()
        if not items:
            QMessageBox.information(self, "No items", "Generate or import builder content first.")
            return
        sentences = self._extract_sentences(items)
        if not sentences:
            QMessageBox.warning(self, "No sentences", "The builder currently does not contain valid listening sentences.")
            return
        self._sentences = sentences
        self._idx = 0
        self.src_lbl.setText(f"{len(sentences)} builder sentences loaded")
        self.mode_lbl.setText("Builder session")
        self._pick_sentence()
        QMessageBox.information(self, "Loaded", f"{len(sentences)} sentences are ready in the practice tab.")

    def _extract_sentences(self, items: list) -> list[str]:
        result: list[str] = []
        for item in items:
            if isinstance(item, str):
                result.append(item)
            elif isinstance(item, dict):
                if "sentences" in item:
                    result.extend([sentence for sentence in item["sentences"] if isinstance(sentence, str)])
                elif "text" in item:
                    result.append(item["text"])
                elif "sentence" in item:
                    result.append(item["sentence"])
        return [sentence.strip() for sentence in result if sentence and sentence.strip()]
