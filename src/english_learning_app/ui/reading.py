"""Reading comprehension widget with side-by-side translation workflow."""
import json
import webbrowser
from pathlib import Path
from urllib.parse import quote

from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
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
from .styles import APP_FONT_FAMILY, tab_style

BG_CARD = "#1e2130"
BG_INPUT = "#13151f"
ACCENT = "#5b6af0"
ACCENT2 = "#3dd68c"
TEXT = "#e8eaf0"
DIM = "#8892a4"
BORDER = "#2a2f42"

TOPICS = [
    "Vietnamese culture and traditions",
    "Technology in modern life",
    "Health and wellness",
    "Travel and tourism in Vietnam",
    "Food and cuisine",
    "Career and work-life balance",
    "Social media impact",
    "Climate change",
    "Artificial Intelligence",
    "Urban life vs rural life",
]
LEVELS = ["A1", "A2", "B1", "B2", "C1"]


class ReadingWorker(QThread):
    result = Signal(dict)
    error = Signal(str)

    def __init__(self, api_key: str, topic: str, level: str):
        super().__init__()
        self.api_key = api_key
        self.topic = topic
        self.level = level

    def run(self):
        try:
            self.result.emit(ai_module.generate_reading_passage(self.api_key, self.topic, self.level))
        except Exception as exc:
            self.error.emit(str(exc))


class TranslationCheckWorker(QThread):
    result = Signal(str)
    error = Signal(str)

    def __init__(self, passage: str, translation: str, level: str):
        super().__init__()
        self.passage = passage
        self.translation = translation
        self.level = level

    def run(self):
        try:
            self.result.emit(ai_module.check_reading_translation(self.passage, self.translation, self.level))
        except Exception as exc:
            self.error.emit(str(exc))


class WordExplainWorker(QThread):
    result = Signal(str)
    error = Signal(str)

    def __init__(self, word: str):
        super().__init__()
        self.word = word

    def run(self):
        try:
            self.result.emit(
                ai_module._call_ai(
                    "",
                    f"""Explain the English word "{self.word}" for a Vietnamese learner.
Return concise Vietnamese with:
- part of speech
- Vietnamese meaning
- one short example sentence
- one memory tip""",
                )
            )
        except Exception as exc:
            self.error.emit(str(exc))


def _card() -> QFrame:
    frame = QFrame()
    frame.setObjectName("card")
    frame.setStyleSheet(
        f"QFrame#card{{background:{BG_CARD};border:1.5px solid {BORDER};border-radius:12px;}}"
    )
    return frame


class PassageEdit(QTextEdit):
    word_clicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(QFont(APP_FONT_FAMILY, 15))
        self.setStyleSheet(
            f"""
            QTextEdit{{
                background:{BG_INPUT};color:{TEXT};border:none;border-radius:12px;
                padding:18px 20px;font-size:16px;line-height:1.7;
                selection-background-color:{ACCENT}55;
            }}
            """
        )
        self._highlight_fmt = QTextCharFormat()
        self._highlight_fmt.setBackground(QColor(ACCENT + "44"))

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        cursor = self.textCursor()
        cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        word = cursor.selectedText().strip().lower()
        word = "".join(ch for ch in word if ch.isalpha() or ch in "-'")
        if len(word) < 2:
            return
        self._highlight(cursor)
        self.word_clicked.emit(word)

    def _highlight(self, cursor: QTextCursor):
        full = QTextCursor(self.document())
        full.select(QTextCursor.SelectionType.Document)
        clear_fmt = QTextCharFormat()
        clear_fmt.setBackground(Qt.GlobalColor.transparent)
        full.mergeCharFormat(clear_fmt)
        cursor.mergeCharFormat(self._highlight_fmt)
        self.setTextCursor(cursor)


class ReadingWidget(QWidget):
    def __init__(self, get_api_key_fn, parent=None):
        super().__init__(parent)
        self.get_api_key = get_api_key_fn
        self.worker = None
        self.translation_worker = None
        self.word_worker = None
        self._queue = []
        self._queue_idx = 0
        self._current_data = {}
        self._selected_word = ""
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        tabs = QTabWidget()
        tabs.setFont(QFont("Segoe UI", 11))
        tabs.setStyleSheet(tab_style())

        practice = QWidget()
        practice_lay = QVBoxLayout(practice)
        practice_lay.setContentsMargins(20, 16, 20, 16)
        practice_lay.setSpacing(12)

        title = QLabel("Reading Practice")
        title.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        practice_lay.addWidget(title)

        subtitle = QLabel("Read on the left, translate in the middle, and check feedback on the right.")
        subtitle.setStyleSheet(f"color:{DIM};font-size:13px;")
        practice_lay.addWidget(subtitle)

        cfg = _card()
        cfg_lay = QHBoxLayout(cfg)
        cfg_lay.setContentsMargins(16, 12, 16, 12)
        cfg_lay.setSpacing(12)
        cfg_lay.addWidget(QLabel("Topic:"))
        self.topic_cb = QComboBox()
        self.topic_cb.addItems(TOPICS)
        self.topic_cb.setMinimumWidth(220)
        cfg_lay.addWidget(self.topic_cb)
        cfg_lay.addWidget(QLabel("Level:"))
        self.level_cb = QComboBox()
        self.level_cb.addItems(LEVELS)
        self.level_cb.setCurrentText("B1")
        cfg_lay.addWidget(self.level_cb)
        cfg_lay.addStretch()

        self.gen_btn = QPushButton("Generate")
        self.gen_btn.setObjectName("btnPrimary")
        self.gen_btn.setFixedHeight(40)
        self.gen_btn.clicked.connect(self._generate)
        cfg_lay.addWidget(self.gen_btn)

        self.import_btn = QPushButton("Load JSON")
        self.import_btn.setFixedHeight(40)
        self.import_btn.clicked.connect(self._import_json)
        cfg_lay.addWidget(self.import_btn)

        self.load_db_btn = QPushButton("Load Library")
        self.load_db_btn.setFixedHeight(40)
        self.load_db_btn.clicked.connect(self._load_from_db)
        cfg_lay.addWidget(self.load_db_btn)
        practice_lay.addWidget(cfg)

        meta_row = QHBoxLayout()
        self.meta_lbl = QLabel("")
        self.meta_lbl.setStyleSheet(f"color:{ACCENT};font-size:13px;font-weight:600;")
        meta_row.addWidget(self.meta_lbl)
        self.queue_lbl = QLabel("")
        self.queue_lbl.setStyleSheet(f"color:{ACCENT2};font-size:12px;font-weight:600;")
        meta_row.addWidget(self.queue_lbl)
        meta_row.addStretch()
        self.status_lbl = QLabel("Generate or load a reading set to start.")
        self.status_lbl.setStyleSheet(f"color:{DIM};font-size:12px;")
        meta_row.addWidget(self.status_lbl)
        practice_lay.addLayout(meta_row)

        self.loading_bar = QProgressBar()
        self.loading_bar.setRange(0, 0)
        self.loading_bar.setVisible(False)
        self.loading_bar.setFixedHeight(4)
        practice_lay.addWidget(self.loading_bar)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setStyleSheet(f"QSplitter::handle{{background:{BORDER};width:2px;}}")

        passage_card = _card()
        passage_lay = QVBoxLayout(passage_card)
        passage_lay.setContentsMargins(16, 14, 16, 14)
        passage_lay.setSpacing(10)
        passage_header = QHBoxLayout()
        passage_title = QLabel("Passage")
        passage_title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        passage_header.addWidget(passage_title)
        passage_header.addStretch()
        self.word_count_lbl = QLabel("0 words")
        self.word_count_lbl.setStyleSheet(f"color:{DIM};font-size:12px;")
        passage_header.addWidget(self.word_count_lbl)
        passage_lay.addLayout(passage_header)
        self.passage_text = PassageEdit()
        self.passage_text.word_clicked.connect(self._on_word_click)
        passage_lay.addWidget(self.passage_text)
        splitter.addWidget(passage_card)

        translation_card = _card()
        translation_lay = QVBoxLayout(translation_card)
        translation_lay.setContentsMargins(16, 14, 16, 14)
        translation_lay.setSpacing(10)
        translation_title = QLabel("Your Vietnamese Translation")
        translation_title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        translation_lay.addWidget(translation_title)
        self.translation_input = QTextEdit()
        self.translation_input.setFont(QFont("Segoe UI", 14))
        self.translation_input.setPlaceholderText(
            "Translate while you read. Keep your Vietnamese version here so you can compare meaning sentence by sentence."
        )
        self.translation_input.setStyleSheet(
            f"""
            QTextEdit{{
                background:{BG_INPUT};color:{TEXT};border:none;border-radius:12px;
                padding:16px;font-size:15px;line-height:1.7;
            }}
            """
        )
        translation_lay.addWidget(self.translation_input)
        button_row = QHBoxLayout()
        self.check_btn = QPushButton("Check Translation")
        self.check_btn.setObjectName("btnSuccess")
        self.check_btn.setFixedHeight(42)
        self.check_btn.clicked.connect(self._check_translation)
        button_row.addWidget(self.check_btn)
        clear_btn = QPushButton("Clear")
        clear_btn.setFixedHeight(42)
        clear_btn.clicked.connect(self.translation_input.clear)
        button_row.addWidget(clear_btn)
        button_row.addStretch()
        translation_lay.addLayout(button_row)
        splitter.addWidget(translation_card)

        side_card = _card()
        side_lay = QVBoxLayout(side_card)
        side_lay.setContentsMargins(16, 14, 16, 14)
        side_lay.setSpacing(10)
        feedback_title = QLabel("Feedback & Vocabulary")
        feedback_title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        side_lay.addWidget(feedback_title)

        self.feedback = QTextEdit()
        self.feedback.setReadOnly(True)
        self.feedback.setFont(QFont("Segoe UI", 13))
        self.feedback.setPlaceholderText("Translation feedback will appear here.")
        self.feedback.setStyleSheet(
            f"""
            QTextEdit{{
                background:{BG_INPUT};color:{TEXT};border:none;border-radius:12px;
                padding:16px;font-size:14px;line-height:1.7;
            }}
            """
        )
        side_lay.addWidget(self.feedback, stretch=3)

        vocab_card = QFrame()
        vocab_card.setStyleSheet(f"QFrame{{background:{BG_INPUT};border:1px solid {BORDER};border-radius:12px;}}")
        vocab_lay = QVBoxLayout(vocab_card)
        vocab_lay.setContentsMargins(14, 12, 14, 12)
        vocab_lay.setSpacing(8)
        self.selected_word_lbl = QLabel("Click a word in the passage to explain it.")
        self.selected_word_lbl.setWordWrap(True)
        self.selected_word_lbl.setStyleSheet(f"color:{DIM};font-size:13px;")
        vocab_lay.addWidget(self.selected_word_lbl)
        vocab_btn_row = QHBoxLayout()
        self.gtrans_btn = QPushButton("Google Translate")
        self.gtrans_btn.setEnabled(False)
        self.gtrans_btn.clicked.connect(self._open_google_translate)
        vocab_btn_row.addWidget(self.gtrans_btn)
        self.explain_btn = QPushButton("AI Explain")
        self.explain_btn.setEnabled(False)
        self.explain_btn.clicked.connect(self._ai_explain_word)
        vocab_btn_row.addWidget(self.explain_btn)
        vocab_lay.addLayout(vocab_btn_row)
        self.vocab_result = QTextEdit()
        self.vocab_result.setReadOnly(True)
        self.vocab_result.setMinimumHeight(160)
        self.vocab_result.setFont(QFont("Segoe UI", 12))
        self.vocab_result.setPlaceholderText("Word explanation will appear here.")
        self.vocab_result.setStyleSheet(
            f"QTextEdit{{background:#0f1524;color:{TEXT};border:none;border-radius:10px;padding:14px;font-size:13px;}}"
        )
        vocab_lay.addWidget(self.vocab_result)
        side_lay.addWidget(vocab_card, stretch=2)
        splitter.addWidget(side_card)
        splitter.setSizes([560, 520, 460])
        practice_lay.addWidget(splitter, stretch=1)

        tabs.addTab(practice, "Practice")

        builder_wrap = QWidget()
        builder_lay = QVBoxLayout(builder_wrap)
        builder_lay.setContentsMargins(24, 20, 24, 20)
        builder_lay.setSpacing(10)
        builder_title = QLabel("Reading Builder")
        builder_title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        builder_lay.addWidget(builder_title)
        builder_sub = QLabel("Generate and save batches of reading passages for later practice.")
        builder_sub.setStyleSheet(f"color:{DIM};font-size:13px;")
        builder_lay.addWidget(builder_sub)
        self.builder = ContentBuilderWidget("reading")
        self.builder.imported.connect(self._on_builder_imported)
        builder_lay.addWidget(self.builder, stretch=1)
        tabs.addTab(builder_wrap, "Builder")

        outer.addWidget(tabs)

    def _generate(self):
        from ..modules.ai_module import _use_web

        if not self.get_api_key() and not _use_web():
            self.status_lbl.setText("Gemini Web not connected.")
            return
        self.loading_bar.setVisible(True)
        self.gen_btn.setEnabled(False)
        self.status_lbl.setText("Generating reading passage...")
        self.worker = ReadingWorker(self.get_api_key(), self.topic_cb.currentText(), self.level_cb.currentText())
        self.worker.result.connect(self._on_passage)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_error(self, error: str):
        self.loading_bar.setVisible(False)
        self.gen_btn.setEnabled(True)
        self.status_lbl.setText(f"Error: {error}")

    def _on_passage(self, data: dict):
        self.loading_bar.setVisible(False)
        self.gen_btn.setEnabled(True)
        passage = data.get("passage", "").strip()
        if not passage:
            self.status_lbl.setText("Could not parse passage. Generate again.")
            return
        self._current_data = data
        self.meta_lbl.setText(f"{data.get('_level', self.level_cb.currentText())} · {data.get('_topic', self.topic_cb.currentText())}")
        self.passage_text.setPlainText(passage)
        self.word_count_lbl.setText(f"{len(passage.split())} words")
        self.translation_input.clear()
        self.feedback.clear()
        self.vocab_result.clear()
        self.selected_word_lbl.setText("Click a word in the passage to explain it.")
        self._selected_word = ""
        self.gtrans_btn.setEnabled(False)
        self.explain_btn.setEnabled(False)
        self.status_lbl.setText("Passage ready.")

    def _check_translation(self):
        from ..modules.ai_module import _use_web

        passage = self._current_data.get("passage", "").strip()
        user_translation = self.translation_input.toPlainText().strip()
        if not passage:
            QMessageBox.warning(self, "No passage", "Generate or load a passage first.")
            return
        if not user_translation:
            QMessageBox.warning(self, "No translation", "Write your Vietnamese translation first.")
            return
        if not _use_web():
            QMessageBox.warning(self, "Gemini Web required", "Translation checking currently uses Gemini Web.")
            return
        self.check_btn.setEnabled(False)
        self.feedback.setPlainText("Checking translation...")
        self.translation_worker = TranslationCheckWorker(
            passage,
            user_translation,
            self.level_cb.currentText(),
        )
        self.translation_worker.result.connect(self._on_translation_checked)
        self.translation_worker.error.connect(self._on_translation_error)
        self.translation_worker.start()

    def _on_translation_checked(self, text: str):
        self.check_btn.setEnabled(True)
        self.feedback.setPlainText(text)

    def _on_translation_error(self, error: str):
        self.check_btn.setEnabled(True)
        self.feedback.setPlainText(f"Error: {error}")

    def _on_word_click(self, word: str):
        self._selected_word = word
        self.selected_word_lbl.setText(f"Selected word: {word}")
        self.gtrans_btn.setEnabled(True)
        self.explain_btn.setEnabled(True)

    def _open_google_translate(self):
        if not self._selected_word:
            return
        webbrowser.open(
            f"https://translate.google.com/?sl=en&tl=vi&text={quote(self._selected_word)}&op=translate"
        )

    def _ai_explain_word(self):
        from ..modules.ai_module import _use_web

        if not self._selected_word:
            return
        if not _use_web():
            self.vocab_result.setPlainText("Gemini Web not connected.")
            return
        self.explain_btn.setEnabled(False)
        self.vocab_result.setPlainText(f"Explaining '{self._selected_word}'...")
        self.word_worker = WordExplainWorker(self._selected_word)
        self.word_worker.result.connect(self._on_word_explained)
        self.word_worker.error.connect(self._on_word_error)
        self.word_worker.start()

    def _on_word_explained(self, text: str):
        self.explain_btn.setEnabled(True)
        self.vocab_result.setPlainText(text)

    def _on_word_error(self, error: str):
        self.explain_btn.setEnabled(True)
        self.vocab_result.setPlainText(f"Error: {error}")

    def _import_json(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Reading Library",
            str(Path.home() / "Downloads"),
            "JSON Files (*.json);;All Files (*)",
        )
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text("utf-8"))
            items = data.get("items", data) if isinstance(data, dict) else data
            items = items if isinstance(items, list) else [items]
            valid = [item for item in items if item.get("passage")]
            if not valid:
                QMessageBox.warning(self, "Warning", "No reading passages found.")
                return
            self._queue = valid
            self._queue_idx = 0
            self.queue_lbl.setText(f"{len(valid)} passages loaded from file")
            self._on_passage(valid[0])
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def _load_from_db(self):
        items = db.get_reading_items(limit=50)
        if not items:
            QMessageBox.information(self, "Empty Library", "No passages in the reading library yet.")
            return
        self._queue = items
        self._queue_idx = 0
        self.queue_lbl.setText(f"{len(items)} passages loaded from the database library")
        self._on_passage(items[0])

    def _on_builder_imported(self, items: list):
        valid = [item for item in items if item.get("passage")]
        if not valid:
            return
        self._queue.extend(valid)
        self.queue_lbl.setText(f"{len(self._queue)} passages available in the current session")
