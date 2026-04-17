"""Image description practice widget."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
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

from ..modules import ai_module, database as db
from .styles import ACCENT, ACCENT_ALT, BG_INPUT, BORDER, TEXT_MAIN, TEXT_MUTED, app_font, card_style


LEVELS = ["A1", "A2", "B1", "B2", "C1"]
FOCUS_OPTIONS = [
    ("General scene", "general"),
    ("People and actions", "people"),
    ("Storytelling", "story"),
    ("Vocabulary building", "vocabulary"),
]


def _card(radius: int = 12) -> QFrame:
    frame = QFrame()
    frame.setObjectName("card")
    frame.setStyleSheet(f"QFrame#card{{{card_style(radius)}}}")
    return frame


class ImageAnalysisWorker(QThread):
    done = Signal(str)
    error = Signal(str)

    def __init__(self, api_key: str, image_path: str, level: str, focus: str):
        super().__init__()
        self.api_key = api_key
        self.image_path = image_path
        self.level = level
        self.focus = focus

    def run(self):
        try:
            result = ai_module.describe_image(
                self.api_key,
                self.image_path,
                level=self.level,
                focus=self.focus,
            )
            self.done.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))


class ImageFeedbackWorker(QThread):
    done = Signal(dict)
    error = Signal(str)

    def __init__(self, api_key: str, image_notes: str, user_description: str, level: str):
        super().__init__()
        self.api_key = api_key
        self.image_notes = image_notes
        self.user_description = user_description
        self.level = level

    def run(self):
        try:
            result = ai_module.review_image_description(
                self.api_key,
                self.image_notes,
                self.user_description,
                level=self.level,
            )
            self.done.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))


class ImageDescriptionWidget(QWidget):
    def __init__(self, get_api_key_fn, parent=None):
        super().__init__(parent)
        self.get_api_key = get_api_key_fn
        self._image_path = ""
        self._image_notes = ""
        self._analysis_worker = None
        self._feedback_worker = None
        self._build_ui()
        self._load_history()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(14)

        title = QLabel("Image Description Lab")
        title.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        outer.addWidget(title)

        subtitle = QLabel(
            "Pick a photo, learn scene vocabulary, then write your own English description and get feedback."
        )
        subtitle.setStyleSheet(f"color:{TEXT_MUTED}; font-size:13px;")
        subtitle.setWordWrap(True)
        outer.addWidget(subtitle)

        top = QHBoxLayout()
        top.setSpacing(14)

        left = _card()
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(18, 18, 18, 18)
        left_lay.setSpacing(12)

        controls = QHBoxLayout()
        self.pick_btn = QPushButton("Pick Image")
        self.pick_btn.setObjectName("btnPrimary")
        self.pick_btn.clicked.connect(self._pick_image)
        controls.addWidget(self.pick_btn)

        self.level_cb = QComboBox()
        self.level_cb.addItems(LEVELS)
        self.level_cb.setCurrentText("B1")
        self.level_cb.setFixedWidth(90)
        controls.addWidget(self.level_cb)

        self.focus_cb = QComboBox()
        for label, value in FOCUS_OPTIONS:
            self.focus_cb.addItem(label, value)
        self.focus_cb.setMinimumWidth(180)
        controls.addWidget(self.focus_cb)

        self.analyze_btn = QPushButton("Analyze")
        self.analyze_btn.setObjectName("btnSuccess")
        self.analyze_btn.clicked.connect(self._analyze_image)
        controls.addWidget(self.analyze_btn)
        controls.addStretch()
        left_lay.addLayout(controls)

        self.image_meta = QLabel("Image analysis ưu tiên Gemini Web đã đăng nhập, sau đó mới fallback sang Gemini API.")
        self.image_meta.setStyleSheet(f"color:{TEXT_MUTED}; font-size:12px;")
        self.image_meta.setWordWrap(True)
        left_lay.addWidget(self.image_meta)

        self.preview = QLabel("No image selected")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(280)
        self.preview.setStyleSheet(
            f"background:{BG_INPUT}; border:1.5px dashed {BORDER}; border-radius:12px; color:{TEXT_MUTED};"
        )
        left_lay.addWidget(self.preview)

        self.notes = QTextEdit()
        self.notes.setReadOnly(True)
        self.notes.setFont(app_font(11))
        self.notes.setPlaceholderText("AI notes will appear here after image analysis.")
        self.notes.setMinimumHeight(260)
        left_lay.addWidget(self.notes)

        phrase_hint = QLabel(
            "Useful starters: In this picture..., I can see..., It looks like..., The person seems to..., In the background..."
        )
        phrase_hint.setWordWrap(True)
        phrase_hint.setStyleSheet(f"color:{TEXT_MUTED}; font-size:12px;")
        left_lay.addWidget(phrase_hint)

        right = _card()
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(18, 18, 18, 18)
        right_lay.setSpacing(12)

        desc_title = QLabel("Your English Description")
        desc_title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        right_lay.addWidget(desc_title)

        self.user_text = QTextEdit()
        self.user_text.setFont(app_font(12))
        self.user_text.setPlaceholderText(
            "Write 4-8 sentences about the image. Focus on people, objects, actions, and mood."
        )
        self.user_text.setMinimumHeight(220)
        right_lay.addWidget(self.user_text)

        checklist = QLabel(
            "Checklist: 1) say what you see, 2) describe actions, 3) mention details/background, 4) give one opinion or guess."
        )
        checklist.setWordWrap(True)
        checklist.setStyleSheet(f"color:{TEXT_MUTED}; font-size:12px;")
        right_lay.addWidget(checklist)

        action_row = QHBoxLayout()
        self.feedback_btn = QPushButton("Get Feedback")
        self.feedback_btn.setObjectName("btnPrimary")
        self.feedback_btn.clicked.connect(self._review_description)
        action_row.addWidget(self.feedback_btn)

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self._clear_current_session)
        action_row.addWidget(self.clear_btn)
        action_row.addStretch()
        right_lay.addLayout(action_row)

        self.feedback = QTextEdit()
        self.feedback.setReadOnly(True)
        self.feedback.setFont(app_font(11))
        self.feedback.setPlaceholderText("Feedback will appear here.")
        self.feedback.setMinimumHeight(220)
        right_lay.addWidget(self.feedback)

        history_title = QLabel("Recent Practice")
        history_title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        right_lay.addWidget(history_title)

        self.history_list = QListWidget()
        self.history_list.setMaximumHeight(160)
        self.history_list.itemSelectionChanged.connect(self._show_history_item)
        right_lay.addWidget(self.history_list)

        top.addWidget(left, 7)
        top.addWidget(right, 6)
        outer.addLayout(top)

    def _pick_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose an image",
            str(Path.home() / "Pictures"),
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)",
        )
        if not path:
            return
        self._image_path = path
        self._image_notes = ""
        self.notes.clear()
        self.feedback.clear()
        self._set_preview(path)
        self.image_meta.setText(Path(path).name)

    def _set_preview(self, path: str):
        pixmap = QPixmap(path)
        if pixmap.isNull():
            self.preview.setPixmap(QPixmap())
            self.preview.setText("Cannot preview this image")
            return
        scaled = pixmap.scaled(
            520,
            320,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.preview.setPixmap(scaled)

    def _analyze_image(self):
        api_key = self.get_api_key()
        if not self._image_path:
            QMessageBox.warning(self, "No image", "Choose an image first.")
            return
        from ..modules.ai_module import _use_web

        if not api_key and not _use_web():
            QMessageBox.warning(
                self,
                "Gemini required",
                "Hãy kết nối Gemini Web hoặc thêm `GEMINI_API_KEY` / `GOOGLE_API_KEY`.",
            )
            return

        self.analyze_btn.setEnabled(False)
        self.notes.setPlainText("Analyzing image...")
        self._analysis_worker = ImageAnalysisWorker(
            api_key,
            self._image_path,
            self.level_cb.currentText(),
            self.focus_cb.currentData(),
        )
        self._analysis_worker.done.connect(self._on_analysis_done)
        self._analysis_worker.error.connect(self._on_analysis_error)
        self._analysis_worker.start()

    def _on_analysis_done(self, text: str):
        self.analyze_btn.setEnabled(True)
        self._image_notes = text
        self.notes.setPlainText(text)

    def _on_analysis_error(self, error: str):
        self.analyze_btn.setEnabled(True)
        self.notes.setPlainText(f"Error: {error}")

    def _review_description(self):
        if not self.user_text.toPlainText().strip():
            QMessageBox.warning(self, "No description", "Write your own description first.")
            return
        if not self._image_notes:
            QMessageBox.warning(self, "No image notes", "Analyze the image first so feedback has context.")
            return

        self.feedback_btn.setEnabled(False)
        self.feedback.setPlainText("Reviewing your description...")
        self._feedback_worker = ImageFeedbackWorker(
            self.get_api_key(),
            self._image_notes,
            self.user_text.toPlainText().strip(),
            self.level_cb.currentText(),
        )
        self._feedback_worker.done.connect(self._on_feedback_done)
        self._feedback_worker.error.connect(self._on_feedback_error)
        self._feedback_worker.start()

    def _on_feedback_done(self, result: dict):
        self.feedback_btn.setEnabled(True)
        self.feedback.setPlainText(result.get("feedback", ""))
        db.save_image_description_session(
            self._image_path,
            self.level_cb.currentText(),
            self.focus_cb.currentData(),
            self._image_notes,
            self.user_text.toPlainText().strip(),
            result.get("feedback", ""),
            result.get("score", 0),
        )
        self._load_history()

    def _on_feedback_error(self, error: str):
        self.feedback_btn.setEnabled(True)
        self.feedback.setPlainText(f"Error: {error}")

    def _load_history(self):
        self._history = db.get_image_description_history(limit=20)
        self.history_list.clear()
        for item in self._history:
            score = item.get("score", 0)
            image_name = Path(item.get("image_path") or "image").name
            self.history_list.addItem(f"{image_name}  |  {item.get('level', 'B1')}  |  {score}/10")

    def _show_history_item(self):
        if not self.history_list.selectedIndexes():
            return
        item = self._history[self.history_list.selectedIndexes()[0].row()]
        self.feedback.setPlainText(item.get("feedback", ""))
        self.user_text.setPlainText(item.get("user_description", ""))
        self.notes.setPlainText(item.get("ai_notes", ""))
        self._image_path = item.get("image_path", "")
        self._image_notes = item.get("ai_notes", "")
        if self._image_path and Path(self._image_path).exists():
            self._set_preview(self._image_path)
            self.image_meta.setText(Path(self._image_path).name)

    def _clear_current_session(self):
        self.user_text.clear()
        self.feedback.clear()
