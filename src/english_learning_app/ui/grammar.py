"""Grammar practice widget with single-question generation for stable output."""
from __future__ import annotations

import json
import re
from pathlib import Path

from PySide6.QtCore import QThread, Signal, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..modules import ai_module
from ..modules import database as db
from .content_builder import ContentBuilderWidget
from .styles import ACCENT, ACCENT_ALT, BG_INPUT, BORDER, TEXT_MAIN, TEXT_MUTED, app_font, card_style, tab_style

TOPICS = [
    "Present Simple vs Present Continuous",
    "Past Simple vs Past Continuous",
    "Present Perfect",
    "Conditional sentences (Type 1 & 2)",
    "Modal verbs (can, could, should, must)",
    "Passive voice",
    "Reported speech",
    "Articles (a, an, the)",
    "Prepositions of time and place",
    "Comparative and superlative adjectives",
    "Question tags",
    "Phrasal verbs",
    "Gerunds and infinitives",
    "Relative clauses",
    "Countable and uncountable nouns",
    "Future tenses (will/going to)",
    "Zero conditional",
    "Used to / would",
    "Quantifiers",
    "Linking words",
]


class GrammarWorker(QThread):
    result = Signal(list)
    error = Signal(str)

    def __init__(self, api_key: str, topic: str):
        super().__init__()
        self.api_key = api_key
        self.topic = topic

    def run(self):
        try:
            self.result.emit(ai_module.generate_grammar_exercise(self.api_key, self.topic))
        except Exception as exc:
            self.error.emit(str(exc))


def _card(radius: int = 12) -> QFrame:
    frame = QFrame()
    frame.setObjectName("card")
    frame.setStyleSheet(f"QFrame#card{{{card_style(radius)}}}")
    return frame


def _normalize_answer(value: str) -> str:
    text = value.strip().lower()
    text = re.sub(r"^\s*(?:answer|dap an)\s*[:\-]?\s*", "", text)
    text = re.sub(r"^\s*[a-d]\s*[\).:\-]\s*", "", text)
    text = re.sub(r"\(.*?\)", "", text)
    text = text.replace('"', "").replace("'", "")
    text = re.sub(r"[^a-z0-9/\-,' ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" ,")
    return text


def _answer_variants(value: str) -> set[str]:
    normalized = _normalize_answer(value)
    if not normalized:
        return set()
    parts = re.split(r"\s*(?:/|,| or )\s*", normalized)
    variants = {normalized}
    variants.update(part.strip() for part in parts if part.strip())
    return variants


class GrammarWidget(QWidget):
    def __init__(self, get_api_key_fn, parent=None):
        super().__init__(parent)
        self.get_api_key = get_api_key_fn
        self.worker = None
        self.exercises: list[dict] = []
        self.current_idx = 0
        self.correct = 0
        self.wrong = 0
        self.streak = 0
        self._queue: list[dict] = []
        self.current_topic = ""
        self._busy_hint = ""
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

        title = QLabel("Grammar Practice")
        title.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        layout.addWidget(title)

        subtitle = QLabel("Generate one stable Gemini Web question at a time, then review saved questions in a clean study flow.")
        subtitle.setStyleSheet(f"color:{TEXT_MUTED};font-size:13px;")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        top_card = _card()
        top_lay = QHBoxLayout(top_card)
        top_lay.setContentsMargins(18, 14, 18, 14)
        top_lay.setSpacing(12)
        top_lay.addWidget(QLabel("Grammar point"))
        self.topic_cb = QComboBox()
        self.topic_cb.addItems(TOPICS)
        self.topic_cb.setMinimumWidth(320)
        self.topic_cb.currentTextChanged.connect(self._refresh_library_status)
        top_lay.addWidget(self.topic_cb)
        top_lay.addStretch()

        self.gen_btn = QPushButton("Generate 1 Question")
        self.gen_btn.setObjectName("btnPrimary")
        self.gen_btn.setFixedHeight(42)
        self.gen_btn.clicked.connect(self._generate)
        top_lay.addWidget(self.gen_btn)

        self.load_btn = QPushButton("Load Topic DB")
        self.load_btn.setFixedHeight(42)
        self.load_btn.clicked.connect(self._load_from_db)
        top_lay.addWidget(self.load_btn)

        self.load_all_btn = QPushButton("Load All Saved")
        self.load_all_btn.setFixedHeight(42)
        self.load_all_btn.clicked.connect(self._load_all_from_db)
        top_lay.addWidget(self.load_all_btn)

        self.import_btn = QPushButton("Import File")
        self.import_btn.setFixedHeight(42)
        self.import_btn.clicked.connect(self._import_json)
        top_lay.addWidget(self.import_btn)
        layout.addWidget(top_card)

        meta_row = QHBoxLayout()
        self.queue_lbl = QLabel("")
        self.queue_lbl.setStyleSheet(f"color:{ACCENT_ALT};font-size:12px;font-weight:700;padding:4px 0;")
        meta_row.addWidget(self.queue_lbl)
        self.saved_lbl = QLabel("")
        self.saved_lbl.setStyleSheet(f"color:{TEXT_MUTED};font-size:12px;padding:4px 0;")
        meta_row.addWidget(self.saved_lbl)
        meta_row.addStretch()
        self.helper_lbl = QLabel("Generate 1 live question or load saved questions from the grammar library.")
        self.helper_lbl.setStyleSheet(f"color:{TEXT_MUTED};font-size:12px;padding:4px 0;")
        meta_row.addWidget(self.helper_lbl)
        layout.addLayout(meta_row)

        self.loading = QProgressBar()
        self.loading.setRange(0, 0)
        self.loading.setVisible(False)
        self.loading.setFixedHeight(5)
        layout.addWidget(self.loading)

        body = QHBoxLayout()
        body.setSpacing(14)

        quiz_card = _card()
        quiz_lay = QVBoxLayout(quiz_card)
        quiz_lay.setContentsMargins(24, 20, 24, 20)
        quiz_lay.setSpacing(14)

        prog = QHBoxLayout()
        self.progress_lbl = QLabel("Question 0 / 0")
        self.progress_lbl.setStyleSheet(f"color:{TEXT_MUTED};font-size:12px;")
        prog.addWidget(self.progress_lbl)
        prog.addStretch()
        self.topic_lbl = QLabel("")
        self.topic_lbl.setStyleSheet(f"color:{ACCENT};font-size:12px;font-weight:700;")
        prog.addWidget(self.topic_lbl)
        quiz_lay.addLayout(prog)

        self.question_lbl = QLabel("Generate a grammar question to start.")
        self.question_lbl.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        self.question_lbl.setMinimumHeight(92)
        self.question_lbl.setWordWrap(True)
        self.question_lbl.setStyleSheet(f"color:{TEXT_MAIN};line-height:1.6;")
        quiz_lay.addWidget(self.question_lbl)

        answer_row = QHBoxLayout()
        self.answer_input = QLineEdit()
        self.answer_input.setPlaceholderText("Type the missing word or structure...")
        self.answer_input.setFont(app_font(15))
        self.answer_input.setFixedHeight(50)
        self.answer_input.setStyleSheet(
            f"QLineEdit{{background:{BG_INPUT};border:1.5px solid {BORDER};border-radius:10px;padding:10px 16px;font-size:15px;}}"
        )
        self.answer_input.returnPressed.connect(self._check)
        answer_row.addWidget(self.answer_input, stretch=1)
        self.check_btn = QPushButton("Check")
        self.check_btn.setObjectName("btnSuccess")
        self.check_btn.setFixedSize(120, 50)
        self.check_btn.clicked.connect(self._check)
        answer_row.addWidget(self.check_btn)
        quiz_lay.addLayout(answer_row)

        self.result_lbl = QLabel("")
        self.result_lbl.setFont(app_font(14, QFont.Weight.Bold))
        self.result_lbl.setWordWrap(True)
        self.result_lbl.setMinimumHeight(32)
        quiz_lay.addWidget(self.result_lbl)

        self.explanation_view = QTextEdit()
        self.explanation_view.setReadOnly(True)
        self.explanation_view.setMinimumHeight(160)
        self.explanation_view.setFont(app_font(12))
        self.explanation_view.setPlaceholderText("Grammar explanation, model form, and review notes will appear here after checking.")
        self.explanation_view.setStyleSheet(
            f"QTextEdit{{background:{BG_INPUT};border:1.5px solid {BORDER};border-radius:10px;padding:12px;line-height:1.5;}}"
        )
        quiz_lay.addWidget(self.explanation_view)

        nav = QHBoxLayout()
        self.hint_btn = QPushButton("Hint")
        self.hint_btn.setFixedHeight(38)
        self.hint_btn.clicked.connect(self._hint)
        nav.addWidget(self.hint_btn)
        nav.addStretch()
        self.next_btn = QPushButton("Next")
        self.next_btn.setFixedHeight(38)
        self.next_btn.setEnabled(False)
        self.next_btn.clicked.connect(self._next)
        nav.addWidget(self.next_btn)
        quiz_lay.addLayout(nav)
        body.addWidget(quiz_card, 7)

        side = _card()
        side_lay = QVBoxLayout(side)
        side_lay.setContentsMargins(18, 18, 18, 18)
        side_lay.setSpacing(12)
        stats_title = QLabel("Session Status")
        stats_title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        side_lay.addWidget(stats_title)
        stats_subtitle = QLabel("Use saved questions as a small review deck after each live generation.")
        stats_subtitle.setWordWrap(True)
        stats_subtitle.setStyleSheet(f"color:{TEXT_MUTED};font-size:12px;line-height:1.5;")
        side_lay.addWidget(stats_subtitle)

        self.correct_lbl = QLabel("Correct: 0")
        self.correct_lbl.setStyleSheet(f"color:{ACCENT_ALT};font-size:13px;font-weight:700;")
        side_lay.addWidget(self.correct_lbl)
        self.wrong_lbl = QLabel("Wrong: 0")
        self.wrong_lbl.setStyleSheet("color:#f87171;font-size:13px;font-weight:700;")
        side_lay.addWidget(self.wrong_lbl)
        self.streak_lbl = QLabel("Streak: 0")
        self.streak_lbl.setStyleSheet("color:#f59e0b;font-size:13px;font-weight:700;")
        side_lay.addWidget(self.streak_lbl)
        side_lay.addSpacing(6)

        library_help = QLabel(
            "Each generated question is saved into the grammar library with duplicate protection, so repeated generations only add new items."
        )
        library_help.setWordWrap(True)
        library_help.setStyleSheet(f"color:{TEXT_MUTED};font-size:12px;line-height:1.6;")
        side_lay.addWidget(library_help)
        side_lay.addStretch()
        body.addWidget(side, 3)
        layout.addLayout(body, stretch=1)
        tabs.addTab(practice, "Practice")

        builder_page = QWidget()
        builder_lay = QVBoxLayout(builder_page)
        builder_lay.setContentsMargins(24, 20, 24, 20)
        builder_lay.setSpacing(10)
        builder_title = QLabel("Grammar Resources")
        builder_title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        builder_lay.addWidget(builder_title)
        builder_sub = QLabel("Build or import extra grammar content here, then review saved questions in the Practice tab.")
        builder_sub.setStyleSheet(f"color:{TEXT_MUTED};font-size:13px;")
        builder_lay.addWidget(builder_sub)
        self.builder = ContentBuilderWidget("grammar")
        self.builder.imported.connect(self._on_builder_imported)
        builder_lay.addWidget(self.builder, stretch=1)
        tabs.addTab(builder_page, "Resources")

        outer.addWidget(tabs)
        self._refresh_library_status()

    def _generate(self):
        from ..modules.ai_module import _use_web, get_web_job_status

        if not self.get_api_key() and not _use_web():
            self.question_lbl.setText("Gemini Web is not connected.")
            self.helper_lbl.setText("Open Gemini Web to generate a live question.")
            return
        busy_job = get_web_job_status()
        if busy_job:
            self.helper_lbl.setText(f"Gemini Web is busy: {busy_job}")
            return
        self.loading.setVisible(True)
        self.gen_btn.setEnabled(False)
        self.saved_lbl.clear()
        self.helper_lbl.setText("Sending request to Gemini Web...")
        self.question_lbl.setText("Generating one grammar question...")
        self.worker = GrammarWorker(self.get_api_key(), self.topic_cb.currentText())
        self.worker.result.connect(self._on_exercises)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_error(self, error: str):
        self.loading.setVisible(False)
        self.gen_btn.setEnabled(True)
        self.question_lbl.setText(f"Error: {error}")
        self.helper_lbl.setText("Try again or load a saved question from the library.")
        self._refresh_ai_buttons()

    def _on_exercises(self, exercises: list):
        self.loading.setVisible(False)
        self.gen_btn.setEnabled(True)
        if not exercises:
            self.question_lbl.setText("Gemini returned no valid questions. Generate again.")
            self.helper_lbl.setText("No valid question was parsed. Generate again.")
            return
        topic = self.topic_cb.currentText()
        selected = exercises[:1]
        inserted = db.save_grammar_library_set(topic, selected)
        total_for_topic = db.get_grammar_library_count(topic)
        self.saved_lbl.setText(f"Library: {total_for_topic} in topic  (+{inserted} unique)")
        self.queue_lbl.setText("Session: 1 live question")
        self.helper_lbl.setText("Live question loaded.")
        self._load_exercise_batch(topic, selected)
        self._refresh_library_status()
        self._refresh_ai_buttons()

    def _load_exercise_batch(self, topic: str, exercises: list[dict]):
        self.current_topic = topic
        self.exercises = [ex for ex in exercises if ex.get("question") and ex.get("answer")]
        self.current_idx = 0
        self.correct = 0
        self.wrong = 0
        self.streak = 0
        self.topic_lbl.setText(topic)
        self._update_stats()
        self._show_current()

    def _show_current(self):
        if not self.exercises or self.current_idx >= len(self.exercises):
            self.progress_lbl.setText("Done")
            self.question_lbl.setText(f"Completed: {self.correct}/{len(self.exercises)} correct")
            self.helper_lbl.setText("Session completed.")
            self.answer_input.setEnabled(False)
            self.check_btn.setEnabled(False)
            self.next_btn.setEnabled(False)
            return
        exercise = self.exercises[self.current_idx]
        self.progress_lbl.setText(f"Question {self.current_idx + 1} / {len(self.exercises)}")
        self.question_lbl.setText(exercise.get("question", ""))
        self.answer_input.clear()
        self.answer_input.setEnabled(True)
        self.check_btn.setEnabled(True)
        self.next_btn.setEnabled(False)
        self.result_lbl.clear()
        self.explanation_view.clear()
        self.helper_lbl.setText("Read the sentence, type the missing form, then press Check.")
        self.answer_input.setFocus()

    def _refresh_ai_buttons(self):
        busy_job = ai_module.get_web_job_status()
        running = bool(self.worker and self.worker.isRunning())
        can_generate = not running and not busy_job
        self.gen_btn.setEnabled(can_generate)
        if busy_job and not running:
            self.gen_btn.setToolTip(f"Gemini Web is busy: {busy_job}")
            if not self.loading.isVisible():
                self.helper_lbl.setText(f"Gemini Web is busy: {busy_job}")
        else:
            self.gen_btn.setToolTip("")
            if not running and not self.exercises:
                self.helper_lbl.setText("Generate 1 live question or load saved questions from the grammar library.")

    def _check(self):
        if not self.exercises or self.current_idx >= len(self.exercises):
            return
        exercise = self.exercises[self.current_idx]
        user_variants = _answer_variants(self.answer_input.text())
        correct_variants = _answer_variants(exercise.get("answer", ""))
        ok = bool(user_variants & correct_variants)
        if ok:
            self.correct += 1
            self.streak += 1
            self.result_lbl.setText("Correct")
            self.result_lbl.setStyleSheet(f"color:{ACCENT_ALT};font-size:14px;font-weight:700;")
            db.update_today_progress(xp_earned=2)
        else:
            self.wrong += 1
            self.streak = 0
            self.result_lbl.setText(f"Correct answer: {exercise.get('answer', '')}")
            self.result_lbl.setStyleSheet("color:#f87171;font-size:14px;font-weight:700;")
        self.explanation_view.setPlainText(exercise.get("explanation", ""))
        db.save_grammar_attempt(
            self.current_topic or self.topic_cb.currentText(),
            exercise.get("question", ""),
            self.answer_input.text().strip(),
            exercise.get("answer", ""),
            exercise.get("explanation", ""),
            ok,
        )
        self.answer_input.setEnabled(False)
        self.check_btn.setEnabled(False)
        self.next_btn.setEnabled(self.current_idx < len(self.exercises) - 1)
        self.helper_lbl.setText("Check the explanation, then move to the next saved question if available.")
        db.update_today_progress(grammar_sessions=1)
        self._update_stats()

    def _next(self):
        self.current_idx += 1
        self._show_current()

    def _hint(self):
        if not self.exercises or self.current_idx >= len(self.exercises):
            return
        answer = self.exercises[self.current_idx].get("answer", "").strip()
        if not answer:
            self.explanation_view.setPlainText("No hint available.")
            return
        self.explanation_view.setPlainText(f"Hint: {answer[0]}{'_' * max(len(answer) - 1, 0)}")

    def _update_stats(self):
        self.correct_lbl.setText(f"Correct: {self.correct}")
        self.wrong_lbl.setText(f"Wrong: {self.wrong}")
        self.streak_lbl.setText(f"Streak: {self.streak}")

    def _import_json(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Grammar Exercises",
            str(Path.home() / "Downloads"),
            "JSON Files (*.json);;All Files (*)",
        )
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text("utf-8"))
            items = data.get("items", data) if isinstance(data, dict) else data
            items = items if isinstance(items, list) else [items]
            valid = []
            for item in items:
                if "exercises" in item:
                    valid.append(item)
                elif "question" in item:
                    valid.append({"grammar_point": item.get("_topic", "Imported"), "exercises": [item]})
            if not valid:
                QMessageBox.warning(self, "Warning", "No grammar exercises found.")
                return
            self._queue = valid
            total = sum(len(item.get("exercises", [])) for item in valid)
            self.queue_lbl.setText(f"Imported: {total} saved questions")
            first = valid[0]
            merged = []
            for item in valid:
                merged.extend(item.get("exercises", []))
            self.helper_lbl.setText("Imported questions loaded for review.")
            self._load_exercise_batch(first.get("grammar_point", "Imported"), merged)
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def _load_from_db(self):
        selected_topic = self.topic_cb.currentText().strip()
        sets = db.get_grammar_library_sets(grammar_point=selected_topic, limit=150)
        if not sets:
            QMessageBox.information(self, "Empty Topic Library", f"No saved grammar questions for '{selected_topic}' yet.")
            return
        self._queue = sets
        total = sum(len(item.get("exercises", [])) for item in sets)
        self.queue_lbl.setText(f"Library: {total} saved questions")
        first = sets[0]
        merged = []
        for item in sets:
            merged.extend(item.get("exercises", []))
        self.helper_lbl.setText(f"Loaded saved questions for: {selected_topic}")
        self._load_exercise_batch(first.get("grammar_point", selected_topic), merged)

    def _load_all_from_db(self):
        sets = db.get_grammar_library_sets(limit=150)
        if not sets:
            QMessageBox.information(self, "Empty Library", "No grammar sets in library yet.")
            return
        self._queue = sets
        total = sum(len(item.get("exercises", [])) for item in sets)
        self.queue_lbl.setText(f"Library: {total} saved questions")
        first = sets[0]
        merged = []
        for item in sets:
            merged.extend(item.get("exercises", []))
        self.helper_lbl.setText("Loaded saved questions from the full grammar library.")
        self._load_exercise_batch(first.get("grammar_point", self.topic_cb.currentText().strip()), merged)

    def _on_builder_imported(self, items: list):
        valid = [item for item in items if "exercises" in item]
        if not valid:
            return
        self._queue.extend(valid)
        total = sum(len(item.get("exercises", [])) for item in self._queue)
        self.queue_lbl.setText(f"Imported: {total} saved questions")
        first = valid[0]
        merged = []
        for item in self._queue:
            merged.extend(item.get("exercises", []))
        self.helper_lbl.setText("Builder content loaded into review session.")
        self._load_exercise_batch(first.get("grammar_point", "Imported"), merged)

    def _refresh_library_status(self):
        selected_topic = self.topic_cb.currentText().strip()
        topic_count = db.get_grammar_library_count(selected_topic)
        total_count = db.get_grammar_library_count()
        self.saved_lbl.setText(f"Topic library: {topic_count}  |  Total library: {total_count}")
