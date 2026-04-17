"""Vocabulary UI with flashcards, quiz, import, and builder integration."""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QFormLayout, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QProgressBar, QPushButton,
    QSizePolicy, QTabWidget, QTextEdit, QVBoxLayout, QWidget,
)

from ..modules import database as db
from ..modules import tts_module
from .styles import tab_style

BG_CARD = "#1e2130"
BG_INPUT = "#13151f"
ACCENT = "#5b6af0"
ACCENT_ALT = "#3dd68c"
TEXT = "#e8eaf0"
TEXT_MUTED = "#8892a4"
BORDER = "#2a2f42"
WARN = "#f59e0b"


def _btn(bg: str) -> str:
    return (
        f"QPushButton{{background:{bg};color:white;border:none;border-radius:10px;"
        f"padding:0 18px;font-size:15px;font-weight:700;}}"
        f"QPushButton:hover{{background:{bg};opacity:0.9;}}"
    )


def _meaning(d: dict) -> str:
    return d.get("meaning_vi") or d.get("vi", "")


def _example(d: dict) -> str:
    return d.get("example") or d.get("sentence", "")


def _ipa(d: dict) -> str:
    return d.get("phonetic") or d.get("ipa", "")


def _pos(d: dict) -> str:
    return d.get("part_of_speech") or d.get("pos", "")


def _definition(d: dict) -> str:
    return d.get("meaning_en") or d.get("definition", "")


def _study_note(d: dict) -> str:
    return d.get("study_note") or d.get("note", "")


def _memory_hint(d: dict) -> str:
    return d.get("memory_hint") or d.get("hint", "")


def _quiz_option_text(d: dict) -> str:
    vi = _meaning(d)
    definition = _definition(d)
    if vi and definition:
        return f"{vi}\n{definition}"
    return vi or definition or _example(d) or d.get("word", "")


def _study_prompt_text(d: dict) -> str:
    parts = []
    if _definition(d):
        parts.append(_definition(d))
    if _study_note(d):
        parts.append(f"Study note: {_study_note(d)}")
    if _memory_hint(d):
        parts.append(f"Memory hint: {_memory_hint(d)}")
    if _meaning(d):
        parts.append(f"Vietnamese: {_meaning(d)}")
    return "\n".join(parts) or _quiz_option_text(d)


class TTSWorker(QThread):
    finished = Signal()
    error = Signal(str)
    def __init__(self, text: str, slow: bool = False):
        super().__init__(); self.text = text; self.slow = slow
    def run(self):
        try: tts_module.speak_word(self.text, slow=self.slow)
        except Exception as exc: self.error.emit(str(exc))
        self.finished.emit()


class AIExplainWorker(QThread):
    result = Signal(str)
    error = Signal(str)
    def __init__(self, api_key: str, word: str):
        super().__init__(); self.api_key = api_key; self.word = word
    def run(self):
        try:
            from ..modules import ai_module
            prompt = f'Explain the English word "{self.word}" for a Vietnamese B1 learner in Vietnamese with sections: WORD, IPA, PART OF SPEECH, VIETNAMESE MEANING, EXAMPLES, COMMON PHRASES, MEMORY TIP.'
            self.result.emit(ai_module._call_ai(self.api_key, prompt))
        except Exception as exc:
            self.error.emit(str(exc))


class FlashCard(QFrame):
    def __init__(self, word_data: dict, parent=None):
        super().__init__(parent)
        self.word = word_data; self.front = True
        self.setMinimumSize(500, 200); self.setMaximumSize(660, 270)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet("QFrame{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #1e3a8a,stop:1 #1e293b);border-radius:18px;border:2px solid #3b82f6;}")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lay = QVBoxLayout(self); self.lay.setContentsMargins(24, 18, 24, 18); self.lay.setSpacing(6)
        self._show()

    def _clear(self):
        while self.lay.count():
            item = self.lay.takeAt(0)
            if item.widget(): item.widget().deleteLater()

    def _show(self):
        self._clear()
        if self.front:
            tag = QLabel(f"  {self.word.get('topic', 'General')}  ")
            tag.setStyleSheet("color:#7dd3fc;font-size:14px;background:#0f2a4a;border-radius:10px;padding:5px 10px;border:none;")
            tag.setFixedWidth(180); self.lay.addWidget(tag)
            word = QLabel(self.word.get("word", ""))
            word.setStyleSheet("color:#f0f9ff;background:transparent;border:none;font-size:50px;font-weight:800;")
            word.setAlignment(Qt.AlignmentFlag.AlignCenter); word.setWordWrap(True)
            self.lay.addWidget(word)
            ipa = QLabel(_ipa(self.word)); ipa.setStyleSheet("color:#93c5fd;font-size:22px;background:transparent;border:none;"); ipa.setAlignment(Qt.AlignmentFlag.AlignCenter); self.lay.addWidget(ipa)
            pos = QLabel(f"[ {_pos(self.word)} ]"); pos.setStyleSheet("color:#94a3b8;font-size:18px;font-style:italic;background:transparent;border:none;"); pos.setAlignment(Qt.AlignmentFlag.AlignCenter); self.lay.addWidget(pos)
            hint = QLabel("Tap to reveal meaning"); hint.setStyleSheet("color:#60a5fa;font-size:14px;background:transparent;border:none;"); hint.setAlignment(Qt.AlignmentFlag.AlignCenter); self.lay.addWidget(hint)
        else:
            word = QLabel(self.word.get("word", "")); word.setStyleSheet("color:#7dd3fc;background:transparent;border:none;font-size:26px;font-weight:800;"); word.setWordWrap(True); self.lay.addWidget(word)
            meaning = QLabel(f"Meaning: {_meaning(self.word)}"); meaning.setStyleSheet("color:#fde68a;background:transparent;border:none;font-size:26px;font-weight:500;"); meaning.setWordWrap(True); self.lay.addWidget(meaning)
            if _definition(self.word):
                definition = QLabel(f"Definition: {_definition(self.word)}"); definition.setStyleSheet("color:#e2e8f0;font-size:18px;background:transparent;border:none;"); definition.setWordWrap(True); self.lay.addWidget(definition)
            example = QLabel(f"Example: {_example(self.word)}"); example.setStyleSheet("color:#cbd5e1;font-size:18px;font-style:italic;background:transparent;border:none;"); example.setWordWrap(True); self.lay.addWidget(example)
            if _study_note(self.word):
                note = QLabel(f"Study note: {_study_note(self.word)}"); note.setStyleSheet("color:#a7f3d0;font-size:17px;background:transparent;border:none;"); note.setWordWrap(True); self.lay.addWidget(note)
            if _memory_hint(self.word):
                memory = QLabel(f"Memory hint: {_memory_hint(self.word)}"); memory.setStyleSheet("color:#fcd34d;font-size:17px;background:transparent;border:none;"); memory.setWordWrap(True); self.lay.addWidget(memory)
            hint = QLabel("Tap to flip back"); hint.setStyleSheet("color:#60a5fa;font-size:14px;background:transparent;border:none;"); hint.setAlignment(Qt.AlignmentFlag.AlignCenter); self.lay.addWidget(hint)

    def set_word(self, data: dict):
        self.word = data; self.front = True; self._show()

    def mousePressEvent(self, event):
        self.front = not self.front; self._show(); super().mousePressEvent(event)


class AddWordDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add New Word"); self.setFixedSize(460, 420)
        self.setStyleSheet(f"QDialog{{background:{BG_CARD};}} QLabel{{color:{TEXT};font-size:14px;}} QLineEdit,QTextEdit,QComboBox{{background:{BG_INPUT};color:{TEXT};border:1.5px solid {BORDER};border-radius:8px;padding:8px;font-size:14px;}}")
        lay = QFormLayout(self); lay.setSpacing(12); lay.setContentsMargins(22, 22, 22, 22)
        self.word_in = QLineEdit(); self.word_in.setPlaceholderText("e.g. accomplish")
        self.meaning_in = QLineEdit(); self.meaning_in.setPlaceholderText("Vietnamese meaning")
        self.ipa_in = QLineEdit(); self.ipa_in.setPlaceholderText("/əˈkʌmplɪʃ/")
        self.pos_in = QComboBox(); self.pos_in.addItems(["noun", "verb", "adjective", "adverb", "phrase", "idiom"])
        self.topic_in = QLineEdit(); self.topic_in.setPlaceholderText("e.g. Work, Education")
        self.example_in = QTextEdit(); self.example_in.setFixedHeight(72); self.example_in.setPlaceholderText("Example sentence in English...")
        lay.addRow("Word *:", self.word_in); lay.addRow("Meaning *:", self.meaning_in); lay.addRow("IPA:", self.ipa_in)
        lay.addRow("Part of Speech:", self.pos_in); lay.addRow("Topic:", self.topic_in); lay.addRow("Example:", self.example_in)
        save = QPushButton("Save Word (+3 XP)"); save.setStyleSheet(_btn(ACCENT_ALT)); save.clicked.connect(self._save); lay.addRow(save)

    def _save(self):
        word = self.word_in.text().strip(); meaning = self.meaning_in.text().strip()
        if not word or not meaning:
            QMessageBox.warning(self, "Missing Data", "Word and meaning are required."); return
        db.add_word(word=word, meaning_vi=meaning, example=self.example_in.toPlainText().strip(), topic=self.topic_in.text().strip() or "General", phonetic=self.ipa_in.text().strip(), part_of_speech=self.pos_in.currentText())
        db.update_today_progress(words_learned=1, xp_earned=3); self.accept()


class FlashcardTab(QWidget):
    def __init__(self, get_api_key_fn, parent=None):
        super().__init__(parent)
        self.get_api_key = get_api_key_fn; self.words = []; self.current_idx = 0; self.tts_worker = None; self.ai_worker = None
        self._build_ui(); self._load_words()

    def _build_ui(self):
        lay = QVBoxLayout(self); lay.setContentsMargins(14, 12, 14, 12); lay.setSpacing(8)
        top = QHBoxLayout(); top.addWidget(QLabel("Topic:"))
        self.topic_cb = QComboBox(); self.topic_cb.setFixedWidth(180)
        for topic in db.get_topics(): self.topic_cb.addItem(topic)
        self.topic_cb.currentTextChanged.connect(self._load_words); top.addWidget(self.topic_cb); top.addSpacing(12)
        self.counter = QLabel("0 / 0"); self.counter.setStyleSheet(f"color:{TEXT_MUTED};font-size:16px;font-weight:600;"); top.addWidget(self.counter); top.addStretch()
        add = QPushButton("Add Word"); add.setStyleSheet(_btn(ACCENT_ALT)); add.clicked.connect(self._add_word); top.addWidget(add); lay.addLayout(top)
        row = QHBoxLayout(); row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.card = FlashCard({"word": "Choose a topic...", "meaning_vi": "", "phonetic": "", "part_of_speech": ""}); row.addWidget(self.card); lay.addLayout(row)
        nav = QHBoxLayout()
        for text, color, fn in [("Previous", "#475569", self._prev), ("Speak", "#3b82f6", self._speak), ("Slow", "#f59e0b", self._speak_slow), ("Next", "#3b82f6", self._next), ("Shuffle", "#6366f1", self._shuffle)]:
            b = QPushButton(text); b.setFixedHeight(40); b.setStyleSheet(_btn(color)); b.clicked.connect(fn); nav.addWidget(b)
        lay.addLayout(nav)
        study_hint = QLabel("Tip: use Vocab Builder to create subject packs for anatomy, physiology, microbiology, pathology, and other Gemini-assisted study topics.")
        study_hint.setWordWrap(True)
        study_hint.setStyleSheet(f"color:{TEXT_MUTED}; font-size:14px; line-height:1.4;")
        lay.addWidget(study_hint)
        ai_card = QFrame(); ai_card.setStyleSheet("QFrame{background:#0d1a3a;border:1.5px solid #1e3a7a;border-radius:12px;}")
        ai = QVBoxLayout(ai_card); ai.setContentsMargins(12, 6, 12, 6); ai.setSpacing(4)
        hdr = QHBoxLayout(); title = QLabel("AI Word Coach"); title.setStyleSheet(f"color:{ACCENT};border:none;font-size:14px;font-weight:800;"); hdr.addWidget(title); hdr.addStretch()
        self.ai_btn = QPushButton("Explain This Word"); self.ai_btn.setFixedHeight(34); self.ai_btn.setStyleSheet(_btn(ACCENT)); self.ai_btn.clicked.connect(self._ai_explain); hdr.addWidget(self.ai_btn); ai.addLayout(hdr)
        self.ai_loading = QProgressBar(); self.ai_loading.setRange(0, 0); self.ai_loading.setFixedHeight(4); self.ai_loading.setVisible(False); ai.addWidget(self.ai_loading)
        self.ai_text = QTextEdit(); self.ai_text.setReadOnly(True); self.ai_text.setFont(QFont("Segoe UI", 15)); self.ai_text.setPlaceholderText("Press 'Explain This Word' to get a detailed explanation."); self.ai_text.setStyleSheet(f"QTextEdit{{background:{BG_INPUT};color:{TEXT};border:none;border-radius:8px;padding:10px 12px;font-size:15px;line-height:1.4;}}"); self.ai_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding); ai.addWidget(self.ai_text); lay.addWidget(ai_card)
        info = QFrame(); info.setStyleSheet(f"QFrame{{background:{BG_CARD};border-radius:8px;border:1.5px solid {BORDER};}}")
        info_lay = QHBoxLayout(info); info_lay.setContentsMargins(10, 6, 10, 6); info_lay.setSpacing(12); self.info_lbs = {}
        for key, label, color in [("level", "Level", ACCENT_ALT), ("part_of_speech", "Part of Speech", "#a855f7"), ("topic", "Topic", "#3b82f6")]:
            col = QVBoxLayout(); t = QLabel(label); t.setStyleSheet(f"color:{TEXT_MUTED};font-size:12px;border:none;"); v = QLabel("-"); v.setStyleSheet(f"color:{color};font-weight:700;font-size:15px;border:none;"); col.addWidget(t); col.addWidget(v); info_lay.addLayout(col); self.info_lbs[key] = v
        info_lay.addStretch(); lay.addWidget(info)

    def _load_words(self):
        settings = db.get_vocab_learning_settings()
        self.words = db.get_due_flashcards(self.topic_cb.currentText(), limit=max(settings.get("daily_reviews", 15), 10))
        if not self.words:
            self.words = db.get_words_by_topic(self.topic_cb.currentText(), limit=max(settings.get("daily_new_words", 10), 10))
        self.current_idx = 0
        self._show_current()

    def _show_current(self):
        if not self.words:
            self.counter.setText("0 / 0")
            self.ai_text.setPlainText("No words in this topic yet. Save words from Vocab Builder or add them manually.")
            for label in self.info_lbs.values(): label.setText("-")
            return
        word = self.words[self.current_idx]
        self.card.set_word(word)
        self.counter.setText(f"{self.current_idx + 1} / {len(self.words)}")
        for key, label in self.info_lbs.items():
            label.setText(_pos(word) if key == "part_of_speech" else word.get(key, "-"))
        self.ai_text.clear()

    def _mark_reviewed(self):
        if not self.words: return
        word = self.words[self.current_idx]
        if word.get("id"):
            db.review_flashcard(word["id"], correct=True)
            db.update_today_progress(words_reviewed=1)

    def _next(self):
        if not self.words: return
        self._mark_reviewed()
        if self.current_idx < len(self.words) - 1:
            self.current_idx += 1
            self._show_current()

    def _prev(self):
        if self.words and self.current_idx > 0:
            self.current_idx -= 1
            self._show_current()

    def _shuffle(self):
        import random
        if self.words:
            random.shuffle(self.words)
            self.current_idx = 0
            self._show_current()

    def _speak(self):
        if not self.words or (self.tts_worker and self.tts_worker.isRunning()): return
        self.tts_worker = TTSWorker(self.words[self.current_idx].get("word", ""))
        self.tts_worker.start()

    def _speak_slow(self):
        if not self.words or (self.tts_worker and self.tts_worker.isRunning()): return
        self.tts_worker = TTSWorker(self.words[self.current_idx].get("word", ""), slow=True)
        self.tts_worker.start()

    def _ai_explain(self):
        if not self.words: return
        from ..modules.ai_module import _use_web
        if not self.get_api_key() and not _use_web():
            self.ai_text.setPlainText("Gemini Web is not connected.\nOpen the Gemini Web tab first.")
            return
        word = self.words[self.current_idx].get("word", "")
        self.ai_btn.setEnabled(False); self.ai_loading.setVisible(True); self.ai_text.setPlainText(f"Explaining '{word}'...")
        self.ai_worker = AIExplainWorker(self.get_api_key(), word)
        self.ai_worker.result.connect(self._on_ai_done); self.ai_worker.error.connect(self._on_ai_err); self.ai_worker.start()

    def _on_ai_done(self, text: str):
        self.ai_btn.setEnabled(True); self.ai_loading.setVisible(False); self.ai_text.setPlainText(text)
        cursor = self.ai_text.textCursor(); cursor.select(QTextCursor.SelectionType.Document)
        fmt = QTextCharFormat(); fmt.setFont(QFont("Segoe UI", 15)); cursor.mergeCharFormat(fmt)

    def _on_ai_err(self, err: str):
        self.ai_btn.setEnabled(True); self.ai_loading.setVisible(False); self.ai_text.setPlainText(f"Error: {err}")

    def _add_word(self):
        dialog = AddWordDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            current = self.topic_cb.currentText()
            self.topic_cb.blockSignals(True); self.topic_cb.clear()
            for topic in db.get_topics(): self.topic_cb.addItem(topic)
            idx = self.topic_cb.findText(current); self.topic_cb.setCurrentIndex(max(0, idx)); self.topic_cb.blockSignals(False)
            self._load_words(); QMessageBox.information(self, "Saved", "The new word was saved. +3 XP")

    def refresh_topics(self):
        current = self.topic_cb.currentText()
        self.topic_cb.blockSignals(True); self.topic_cb.clear()
        for topic in db.get_topics(): self.topic_cb.addItem(topic)
        idx = self.topic_cb.findText(current); self.topic_cb.setCurrentIndex(max(0, idx)); self.topic_cb.blockSignals(False)
        self._load_words()


class QuizTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.words = []; self.current_word = None; self.correct = 0; self.total = 0; self._answered = False
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self); lay.setContentsMargins(16, 12, 16, 12); lay.setSpacing(8)
        hdr = QHBoxLayout(); title = QLabel("Vocabulary Quiz"); title.setStyleSheet("font-size:18px;font-weight:800;border:none;"); hdr.addWidget(title); hdr.addStretch()
        self.score_lbl = QLabel("Correct 0  Wrong 0"); self.score_lbl.setStyleSheet(f"color:{TEXT_MUTED};font-size:16px;font-weight:700;"); hdr.addWidget(self.score_lbl); lay.addLayout(hdr)
        quiz_hint = QLabel("This quiz uses general English vocabulary only. Subject-specific terms are kept in Study Quiz so the practice set stays consistent.")
        quiz_hint.setWordWrap(True)
        quiz_hint.setStyleSheet(f"color:{TEXT_MUTED}; font-size:14px; line-height:1.4;")
        lay.addWidget(quiz_hint)
        top = QHBoxLayout(); top.addWidget(QLabel("Topic:"))
        self.topic_cb = QComboBox(); self.topic_cb.setFixedWidth(180)
        for topic in db.get_topics(vocab_kind="general"): self.topic_cb.addItem(topic)
        top.addWidget(self.topic_cb); top.addStretch()
        start = QPushButton("Start Quiz"); start.setStyleSheet(_btn(ACCENT)); start.clicked.connect(self._start); top.addWidget(start); lay.addLayout(top)
        card = QFrame(); card.setStyleSheet(f"QFrame{{background:{BG_CARD};border-radius:14px;border:1.5px solid {BORDER};}}"); card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        card_lay = QVBoxLayout(card); card_lay.setContentsMargins(18, 16, 18, 16); card_lay.setSpacing(8)
        self.q_hint = QLabel("Choose the correct meaning or definition:"); self.q_hint.setStyleSheet(f"color:{TEXT_MUTED};font-size:15px;border:none;"); card_lay.addWidget(self.q_hint)
        self.word_lbl = QLabel("-"); self.word_lbl.setStyleSheet("color:#f0f9ff;border:none;font-size:42px;font-weight:800;"); self.word_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter); card_lay.addWidget(self.word_lbl)
        self.ph_lbl = QLabel(""); self.ph_lbl.setStyleSheet("color:#7dd3fc;font-size:20px;border:none;"); self.ph_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter); card_lay.addWidget(self.ph_lbl)
        self.ans_btns = []; grid = QGridLayout(); grid.setSpacing(6)
        for i in range(4):
            b = QPushButton(""); b.setMinimumHeight(58); b.setFont(QFont("Segoe UI", 15)); b.setStyleSheet(self._choice("#2a2f42")); b.clicked.connect(lambda _, x=i: self._check(x)); grid.addWidget(b, i // 2, i % 2); self.ans_btns.append(b)
        card_lay.addLayout(grid)
        self.fb_lbl = QLabel(""); self.fb_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter); self.fb_lbl.setStyleSheet("border:none;font-size:17px;font-weight:800;"); card_lay.addWidget(self.fb_lbl)
        self.next_btn = QPushButton("Next Question"); self.next_btn.setFixedHeight(38); self.next_btn.setStyleSheet(_btn(ACCENT)); self.next_btn.setVisible(False); self.next_btn.clicked.connect(self._next_q); card_lay.addWidget(self.next_btn)
        lay.addWidget(card)
        pr = QHBoxLayout(); self.prog = QProgressBar(); self.prog.setRange(0, 10); self.prog.setValue(0); self.prog.setFixedHeight(8); self.prog.setTextVisible(False); pr.addWidget(QLabel("Progress:")); pr.addWidget(self.prog, stretch=1); lay.addLayout(pr)
        lay.addStretch()

    def _choice(self, bg: str) -> str:
        return f"QPushButton{{background:{bg};color:{TEXT};border:none;border-radius:11px;padding:12px 16px;font-size:16px;font-weight:600;text-align:left;}}QPushButton:hover{{background:#3a3f55;}}"

    def _start(self):
        settings = db.get_vocab_learning_settings()
        self.words = db.get_due_flashcards(self.topic_cb.currentText(), limit=max(settings.get("daily_reviews", 15), 20), vocab_kind="general")
        if len(self.words) < 4: self.words = db.get_words_by_topic(self.topic_cb.currentText(), limit=40, vocab_kind="general")
        if len(self.words) < 4:
            QMessageBox.warning(self, "Not Enough Words", "This topic needs at least 4 general English words."); return
        self.correct = 0; self.total = 0; self.prog.setMaximum(min(10, len(self.words))); self.prog.setValue(0); self._update_score(); self._next_q()

    def _next_q(self):
        import random
        if not self.words or self.total >= min(10, len(self.words)):
            self._results(); return
        self.current_word = random.choice(self.words)
        wrong = [w for w in self.words if w["id"] != self.current_word["id"]]
        options = [self.current_word] + random.sample(wrong, min(3, len(wrong))); random.shuffle(options); self._correct_idx = options.index(self.current_word)
        self.word_lbl.setText(self.current_word.get("word", "")); self.ph_lbl.setText(_ipa(self.current_word)); self.fb_lbl.clear(); self.next_btn.setVisible(False); self._answered = False
        for i, btn in enumerate(self.ans_btns):
            btn.setVisible(True); btn.setText(_quiz_option_text(options[i])); btn.setStyleSheet(self._choice("#2a2f42")); btn.setEnabled(True)

    def _check(self, idx: int):
        if self._answered: return
        self._answered = True; self.total += 1
        for i, btn in enumerate(self.ans_btns):
            btn.setEnabled(False)
            if i == self._correct_idx: btn.setStyleSheet(self._choice("#15803d"))
            elif i == idx: btn.setStyleSheet(self._choice("#b91c1c"))
        if idx == self._correct_idx:
            self.correct += 1; self.fb_lbl.setText("Correct! +2 XP"); self.fb_lbl.setStyleSheet(f"color:{ACCENT_ALT};font-size:16px;font-weight:700;border:none;"); db.update_today_progress(words_reviewed=1, xp_earned=2)
        else:
            self.fb_lbl.setText(f"Wrong. Correct answer: {_quiz_option_text(self.current_word)}"); self.fb_lbl.setStyleSheet("color:#f87171;font-size:16px;border:none;")
        self.prog.setValue(self.total); self._update_score(); self.next_btn.setVisible(True)

    def _update_score(self):
        self.score_lbl.setText(f"Correct {self.correct}  Wrong {self.total - self.correct}")

    def _results(self):
        pct = int(self.correct / self.total * 100) if self.total else 0
        self.word_lbl.setText(f"{pct}%"); self.ph_lbl.setText(f"{self.correct}/{self.total} correct"); self.fb_lbl.setText("Completed!" if pct >= 70 else "Keep practicing!"); self.fb_lbl.setStyleSheet(f"color:{'#22c55e' if pct >= 70 else WARN};font-size:16px;font-weight:700;border:none;")
        for btn in self.ans_btns: btn.setVisible(False)
        self.next_btn.setVisible(False)

    def refresh_topics(self):
        current = self.topic_cb.currentText(); self.topic_cb.clear()
        for topic in db.get_topics(vocab_kind="general"): self.topic_cb.addItem(topic)
        idx = self.topic_cb.findText(current); self.topic_cb.setCurrentIndex(max(0, idx))


class StudyQuizTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.words = []
        self.current_word = None
        self.correct = 0
        self.total = 0
        self._answered = False
        self._direction = "term_to_definition"
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self); lay.setContentsMargins(16, 12, 16, 12); lay.setSpacing(8)
        hdr = QHBoxLayout(); title = QLabel("Study Quiz"); title.setStyleSheet("font-size:18px;font-weight:800;border:none;"); hdr.addWidget(title); hdr.addStretch()
        self.score_lbl = QLabel("Correct 0  Wrong 0"); self.score_lbl.setStyleSheet(f"color:{TEXT_MUTED};font-size:16px;font-weight:700;"); hdr.addWidget(self.score_lbl); lay.addLayout(hdr)
        hint = QLabel("Best for medical, academic, and other specialist study packs. General English words are kept out of this mode.")
        hint.setWordWrap(True); hint.setStyleSheet(f"color:{TEXT_MUTED}; font-size:14px; line-height:1.4;"); lay.addWidget(hint)
        top = QHBoxLayout(); top.addWidget(QLabel("Topic:"))
        self.topic_cb = QComboBox(); self.topic_cb.setFixedWidth(220)
        for topic in db.get_topics(vocab_kind="study"): self.topic_cb.addItem(topic)
        top.addWidget(self.topic_cb)
        top.addWidget(QLabel("Mode:"))
        self.mode_cb = QComboBox(); self.mode_cb.setFixedWidth(220); self.mode_cb.addItems(["Term -> Definition", "Definition -> Term", "Mixed"])
        top.addWidget(self.mode_cb)
        top.addStretch()
        start = QPushButton("Start Study Quiz"); start.setStyleSheet(_btn("#0f766e")); start.clicked.connect(self._start); top.addWidget(start); lay.addLayout(top)
        card = QFrame(); card.setStyleSheet(f"QFrame{{background:{BG_CARD};border-radius:14px;border:1.5px solid {BORDER};}}"); card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        card_lay = QVBoxLayout(card); card_lay.setContentsMargins(18, 16, 18, 16); card_lay.setSpacing(8)
        self.q_hint = QLabel("Choose the best answer:"); self.q_hint.setStyleSheet(f"color:{TEXT_MUTED};font-size:15px;border:none;"); card_lay.addWidget(self.q_hint)
        self.prompt_lbl = QLabel("-"); self.prompt_lbl.setStyleSheet("color:#f0f9ff;border:none;font-size:24px;font-weight:800;"); self.prompt_lbl.setWordWrap(True); self.prompt_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter); card_lay.addWidget(self.prompt_lbl)
        self.meta_lbl = QLabel(""); self.meta_lbl.setStyleSheet("color:#7dd3fc;font-size:16px;border:none;"); self.meta_lbl.setWordWrap(True); self.meta_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter); card_lay.addWidget(self.meta_lbl)
        self.ans_btns = []; grid = QGridLayout(); grid.setSpacing(6)
        for i in range(4):
            b = QPushButton(""); b.setMinimumHeight(62); b.setFont(QFont("Segoe UI", 14)); b.setStyleSheet(self._choice("#2a2f42")); b.clicked.connect(lambda _, x=i: self._check(x)); grid.addWidget(b, i // 2, i % 2); self.ans_btns.append(b)
        card_lay.addLayout(grid)
        self.fb_lbl = QLabel(""); self.fb_lbl.setWordWrap(True); self.fb_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter); self.fb_lbl.setStyleSheet("border:none;font-size:16px;font-weight:800;"); card_lay.addWidget(self.fb_lbl)
        self.next_btn = QPushButton("Next Question"); self.next_btn.setFixedHeight(38); self.next_btn.setStyleSheet(_btn(ACCENT)); self.next_btn.setVisible(False); self.next_btn.clicked.connect(self._next_q); card_lay.addWidget(self.next_btn)
        lay.addWidget(card)
        pr = QHBoxLayout(); self.prog = QProgressBar(); self.prog.setRange(0, 10); self.prog.setValue(0); self.prog.setFixedHeight(8); self.prog.setTextVisible(False); pr.addWidget(QLabel("Progress:")); pr.addWidget(self.prog, stretch=1); lay.addLayout(pr)
        lay.addStretch()

    def _choice(self, bg: str) -> str:
        return f"QPushButton{{background:{bg};color:{TEXT};border:none;border-radius:11px;padding:12px 16px;font-size:14px;font-weight:600;text-align:left;}}QPushButton:hover{{background:#3a3f55;}}"

    def _study_candidates(self, topic: str) -> list[dict]:
        words = db.get_due_flashcards(topic, limit=40, vocab_kind="study")
        if len(words) < 4:
            words = db.get_words_by_topic(topic, limit=60, vocab_kind="study")
        return [w for w in words if _definition(w) or _study_note(w) or _memory_hint(w)]

    def _start(self):
        self.words = self._study_candidates(self.topic_cb.currentText())
        if len(self.words) < 4:
            QMessageBox.warning(self, "Not Enough Study Terms", "This topic needs at least 4 saved study terms with definitions or notes."); return
        self.correct = 0; self.total = 0; self.prog.setMaximum(min(10, len(self.words))); self.prog.setValue(0); self._update_score(); self._next_q()

    def _pick_direction(self) -> str:
        mode = self.mode_cb.currentText()
        if mode == "Term -> Definition":
            return "term_to_definition"
        if mode == "Definition -> Term":
            return "definition_to_term"
        import random
        return random.choice(["term_to_definition", "definition_to_term"])

    def _next_q(self):
        import random
        if not self.words or self.total >= min(10, len(self.words)):
            self._results(); return
        self.current_word = random.choice(self.words)
        self._direction = self._pick_direction()
        wrong = [w for w in self.words if w["id"] != self.current_word["id"]]
        options = [self.current_word] + random.sample(wrong, min(3, len(wrong))); random.shuffle(options); self._correct_idx = options.index(self.current_word)
        if self._direction == "term_to_definition":
            self.q_hint.setText("Choose the best definition or study note:")
            self.prompt_lbl.setText(self.current_word.get("word", ""))
            meta = []
            if _ipa(self.current_word): meta.append(_ipa(self.current_word))
            if _pos(self.current_word): meta.append(_pos(self.current_word))
            self.meta_lbl.setText("  |  ".join(meta))
            for i, btn in enumerate(self.ans_btns):
                btn.setVisible(True); btn.setText(_study_prompt_text(options[i])); btn.setStyleSheet(self._choice("#2a2f42")); btn.setEnabled(True)
        else:
            self.q_hint.setText("Which term matches this definition or study note?")
            self.prompt_lbl.setText(_study_prompt_text(self.current_word))
            self.meta_lbl.setText(self.current_word.get("topic", ""))
            for i, btn in enumerate(self.ans_btns):
                label = options[i].get("word", "")
                if _ipa(options[i]): label += f"\n{_ipa(options[i])}"
                btn.setVisible(True); btn.setText(label); btn.setStyleSheet(self._choice("#2a2f42")); btn.setEnabled(True)
        self.fb_lbl.clear(); self.next_btn.setVisible(False); self._answered = False

    def _check(self, idx: int):
        if self._answered: return
        self._answered = True; self.total += 1
        for i, btn in enumerate(self.ans_btns):
            btn.setEnabled(False)
            if i == self._correct_idx: btn.setStyleSheet(self._choice("#15803d"))
            elif i == idx: btn.setStyleSheet(self._choice("#b91c1c"))
        if idx == self._correct_idx:
            self.correct += 1; self.fb_lbl.setText("Correct! +2 XP"); self.fb_lbl.setStyleSheet(f"color:{ACCENT_ALT};font-size:16px;font-weight:700;border:none;"); db.update_today_progress(words_reviewed=1, xp_earned=2)
        else:
            self.fb_lbl.setText(f"Wrong. Correct answer: {self.current_word.get('word', '')}\n{_study_prompt_text(self.current_word)}"); self.fb_lbl.setStyleSheet("color:#f87171;font-size:15px;border:none;")
        self.prog.setValue(self.total); self._update_score(); self.next_btn.setVisible(True)

    def _update_score(self):
        self.score_lbl.setText(f"Correct {self.correct}  Wrong {self.total - self.correct}")

    def _results(self):
        pct = int(self.correct / self.total * 100) if self.total else 0
        self.prompt_lbl.setText(f"{pct}%")
        self.meta_lbl.setText(f"{self.correct}/{self.total} correct")
        self.fb_lbl.setText("Completed!" if pct >= 70 else "Keep reviewing the study pack.")
        self.fb_lbl.setStyleSheet(f"color:{'#22c55e' if pct >= 70 else WARN};font-size:16px;font-weight:700;border:none;")
        for btn in self.ans_btns: btn.setVisible(False)
        self.next_btn.setVisible(False)

    def refresh_topics(self):
        current = self.topic_cb.currentText(); self.topic_cb.clear()
        for topic in db.get_topics(vocab_kind="study"): self.topic_cb.addItem(topic)
        idx = self.topic_cb.findText(current); self.topic_cb.setCurrentIndex(max(0, idx))


class VocabularyWidget(QWidget):
    def __init__(self, get_api_key_fn=None, parent=None):
        super().__init__(parent)
        self.get_api_key = get_api_key_fn or (lambda: "")
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(0)
        tabs = QTabWidget(); tabs.setFont(QFont("Segoe UI", 12)); tabs.setStyleSheet(tab_style())
        self.flashcard_tab = FlashcardTab(self.get_api_key); tabs.addTab(self.flashcard_tab, "Flashcards")
        self.quiz_tab = QuizTab(); tabs.addTab(self.quiz_tab, "Quiz")
        self.study_quiz_tab = StudyQuizTab(); tabs.addTab(self.study_quiz_tab, "Study Quiz")
        from .vocab_builder import VocabBuilderWidget
        self.vocab_builder = VocabBuilderWidget(); self.vocab_builder.save_db_btn.clicked.connect(self._on_builder_saved); tabs.addTab(self.vocab_builder, "Vocab Builder")
        lay.addWidget(tabs, stretch=1)

    def _on_builder_saved(self):
        self.flashcard_tab.refresh_topics(); self.quiz_tab.refresh_topics(); self.study_quiz_tab.refresh_topics()

    def import_vocab_json(self):
        path_str, _ = QFileDialog.getOpenFileName(self, "Import Vocabulary", str(Path.home() / "Downloads"), "JSON Files (*.json);;CSV Files (*.csv);;All Files (*)")
        if not path_str: return
        try:
            path = Path(path_str)
            words = self._parse_csv(path) if path.suffix.lower() == ".csv" else self._parse_json(path)
            if not words:
                QMessageBox.warning(self, "No Data", "No valid vocabulary items were found in the file."); return
            conn = db.get_connection(); cur = conn.cursor(); cur.execute("SELECT LOWER(word), COALESCE(topic, '') FROM vocabulary")
            existing = {(row[0], row[1]) for row in cur.fetchall()}; conn.close()
            added = skipped = 0
            for item in words:
                word = item.get("word", "").strip(); topic = item.get("topic", "Imported")
                key = (word.lower(), topic)
                if not word or key in existing:
                    skipped += 1; continue
                db.add_word(word=word, meaning_vi=item.get("vi", item.get("meaning_vi", "")), example=item.get("sentence", item.get("example", "")), topic=topic, phonetic=item.get("ipa", item.get("phonetic", "")), part_of_speech=item.get("pos", item.get("part_of_speech", "")), level=item.get("level", "B1"), meaning_en=item.get("definition", item.get("meaning_en", "")), study_note=item.get("study_note", item.get("note", "")), memory_hint=item.get("memory_hint", item.get("hint", "")))
                existing.add(key); added += 1
            db.update_today_progress(words_learned=added, xp_earned=added); self.flashcard_tab.refresh_topics(); self.quiz_tab.refresh_topics(); self.study_quiz_tab.refresh_topics()
            msg = f"Imported {added} new words." + (f" ({skipped} duplicates skipped)" if skipped else "")
            QMessageBox.information(self, "Import Complete", msg)
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def _parse_json(self, path: Path) -> list[dict]:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            for key in ("items", "words", "vocabulary", "data", "vocab"):
                if key in data and isinstance(data[key], list):
                    data = data[key]; break
            else:
                data = list(data.values())[0] if data else []
        if not isinstance(data, list): return []
        result = []
        for item in data:
            if not isinstance(item, dict): continue
            word = (item.get("word") or item.get("Word") or item.get("english") or "").strip()
            if not word: continue
            result.append({"word": word, "ipa": item.get("ipa") or item.get("IPA") or item.get("phonetic") or "", "pos": item.get("pos") or item.get("part_of_speech") or item.get("type") or "", "vi": item.get("vi") or item.get("vietnamese") or item.get("meaning_vi") or item.get("meaning") or "", "sentence": item.get("sentence") or item.get("example") or "", "definition": item.get("definition") or item.get("meaning_en") or "", "study_note": item.get("study_note") or item.get("note") or "", "memory_hint": item.get("memory_hint") or item.get("hint") or "", "level": item.get("level") or item.get("_level") or "B1", "topic": item.get("topic") or item.get("_topic") or "Imported"})
        return result

    def _parse_csv(self, path: Path) -> list[dict]:
        import csv
        reader = csv.DictReader(path.read_text(encoding="utf-8-sig").splitlines())
        def first(row: dict, cols: list[str]) -> str:
            for col in cols:
                if col in row and row[col]: return row[col]
            return ""
        result = []
        for row in reader:
            word = first(row, ["word", "Word", "english", "term"]).strip()
            if not word: continue
            result.append({"word": word, "ipa": first(row, ["ipa", "IPA", "phonetic", "pronunciation"]), "pos": first(row, ["pos", "POS", "type", "part_of_speech"]), "vi": first(row, ["vi", "vietnamese", "Vietnamese", "meaning", "definition"]), "sentence": first(row, ["sentence", "example", "example_sentence"]), "definition": first(row, ["definition", "meaning_en", "english_definition"]), "study_note": first(row, ["study_note", "note", "clinical_note"]), "memory_hint": first(row, ["memory_hint", "hint", "memory_tip"]), "level": first(row, ["level", "Level"]) or "B1", "topic": first(row, ["topic", "Topic"]) or "Imported"})
        return result
