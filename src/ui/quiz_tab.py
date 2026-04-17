"""
Quiz Tab - Trắc nghiệm từ vựng với Gemini AI tạo câu hỏi
"""
import random
import threading
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QGroupBox, QRadioButton, QButtonGroup, QTextEdit, QComboBox,
    QProgressBar, QFrame
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont


class QuizTab(QWidget):
    question_ready = Signal(dict)
    ai_question_ready = Signal(str)

    def __init__(self, gemini_web, vocab_bank):
        super().__init__()
        self.gemini_web = gemini_web
        self.vocab_bank = vocab_bank
        self._questions: list[dict] = []
        self._current_q = 0
        self._score = 0
        self._answered = False
        self.question_ready.connect(self._show_question)
        self.ai_question_ready.connect(self._show_ai_result)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Controls
        ctrl_group = QGroupBox("⚙️ Quiz Settings")
        ctrl_layout = QHBoxLayout(ctrl_group)

        ctrl_layout.addWidget(QLabel("Type:"))
        self.quiz_type = QComboBox()
        self.quiz_type.addItems(["Multiple Choice (Vocab)", "Fill in Blank (AI)", "Definition Match"])
        self.quiz_type.setFixedWidth(200)
        ctrl_layout.addWidget(self.quiz_type)

        ctrl_layout.addWidget(QLabel("Difficulty:"))
        self.diff_combo = QComboBox()
        self.diff_combo.addItems(["All", "easy", "medium", "hard"])
        self.diff_combo.setFixedWidth(80)
        ctrl_layout.addWidget(self.diff_combo)

        ctrl_layout.addWidget(QLabel("Questions:"))
        self.count_combo = QComboBox()
        self.count_combo.addItems(["5", "10", "15", "20"])
        self.count_combo.setCurrentIndex(1)
        self.count_combo.setFixedWidth(60)
        ctrl_layout.addWidget(self.count_combo)

        start_btn = QPushButton("▶ Start Quiz")
        start_btn.setFixedHeight(34)
        start_btn.setStyleSheet("background:#2a82da; color:white; border-radius:5px; font-weight:bold; padding:0 16px;")
        start_btn.clicked.connect(self._start_quiz)
        ctrl_layout.addStretch()
        ctrl_layout.addWidget(start_btn)
        layout.addWidget(ctrl_group)

        # Progress
        prog_row = QHBoxLayout()
        self.prog_bar = QProgressBar()
        self.prog_bar.setFixedHeight(8)
        self.prog_bar.setStyleSheet("""
            QProgressBar { border-radius:4px; background:#222; }
            QProgressBar::chunk { background:#f39c12; border-radius:4px; }
        """)
        self.prog_label = QLabel("Q 0/0")
        self.prog_label.setFixedWidth(60)
        self.score_label = QLabel("Score: 0")
        self.score_label.setStyleSheet("color:#27ae60; font-weight:bold;")
        prog_row.addWidget(self.prog_bar)
        prog_row.addWidget(self.prog_label)
        prog_row.addStretch()
        prog_row.addWidget(self.score_label)
        layout.addLayout(prog_row)

        # Question card
        q_frame = QFrame()
        q_frame.setFrameShape(QFrame.Shape.StyledPanel)
        q_frame.setStyleSheet("QFrame { background:#1a1a2e; border-radius:10px; padding:8px; }")
        q_layout = QVBoxLayout(q_frame)

        self.question_label = QLabel("Press 'Start Quiz' to begin!")
        self.question_label.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.question_label.setWordWrap(True)
        self.question_label.setStyleSheet("color:#e0e0e0; padding:8px;")
        q_layout.addWidget(self.question_label)

        # Radio buttons for MCQ
        self.btn_group = QButtonGroup(self)
        self.radio_btns: list[QRadioButton] = []
        for i in range(4):
            rb = QRadioButton(f"Option {i+1}")
            rb.setFont(QFont("Segoe UI", 11))
            rb.setStyleSheet("QRadioButton { color:#ccc; padding:6px; } QRadioButton:hover { color:white; }")
            self.btn_group.addButton(rb, i)
            self.radio_btns.append(rb)
            q_layout.addWidget(rb)

        # Free text for AI quiz
        self.ai_result_text = QTextEdit()
        self.ai_result_text.setPlaceholderText("AI-generated quiz will appear here...")
        self.ai_result_text.setFixedHeight(160)
        self.ai_result_text.setReadOnly(True)
        self.ai_result_text.hide()
        q_layout.addWidget(self.ai_result_text)

        layout.addWidget(q_frame, stretch=1)

        # Feedback
        self.feedback_label = QLabel("")
        self.feedback_label.setFont(QFont("Segoe UI", 11))
        self.feedback_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.feedback_label.setStyleSheet("padding:6px; border-radius:6px;")
        layout.addWidget(self.feedback_label)

        # Action buttons
        btn_row = QHBoxLayout()
        self.submit_btn = QPushButton("✔ Submit Answer")
        self.submit_btn.setFixedHeight(42)
        self.submit_btn.setStyleSheet("background:#27ae60; color:white; border-radius:6px; font-size:13px; font-weight:bold;")
        self.submit_btn.clicked.connect(self._submit)
        self.submit_btn.setEnabled(False)

        self.next_btn = QPushButton("Next ▶")
        self.next_btn.setFixedHeight(42)
        self.next_btn.setFixedWidth(100)
        self.next_btn.setStyleSheet("background:#555; color:white; border-radius:6px; font-size:13px;")
        self.next_btn.clicked.connect(self._next_question)
        self.next_btn.setEnabled(False)

        btn_row.addWidget(self.submit_btn)
        btn_row.addWidget(self.next_btn)
        layout.addLayout(btn_row)

        self.btn_group.buttonClicked.connect(lambda: self.submit_btn.setEnabled(True))

    # ─── Quiz Logic ─────────────────────────────────────────────────────────

    def _start_quiz(self):
        qtype = self.quiz_type.currentText()
        diff = self.diff_combo.currentText()
        count = int(self.count_combo.currentText())

        if "AI" in qtype:
            self._start_ai_quiz()
            return

        items = self.vocab_bank.items if diff == "All" else self.vocab_bank.get_by_difficulty(diff)
        if len(items) < 4:
            self.question_label.setText("❌ Cần ít nhất 4 từ vựng trong bank để quiz!")
            return

        sample = random.sample(items, min(count, len(items)))
        self._questions = []

        for item in sample:
            wrong_pool = [x for x in items if x.word != item.word]
            wrongs = random.sample(wrong_pool, min(3, len(wrong_pool)))

            if "Definition Match" in qtype:
                # Question: show definition, pick word
                opts = [item.word] + [w.word for w in wrongs]
                random.shuffle(opts)
                self._questions.append({
                    "question": f"Which word matches:\n\n\"{item.definition}\"",
                    "options": opts,
                    "answer": item.word,
                    "explanation": f"Example: {item.example}" if item.example else ""
                })
            else:
                # Multiple choice: show word, pick definition
                opts = [item.definition] + [w.definition for w in wrongs]
                random.shuffle(opts)
                self._questions.append({
                    "question": f"What is the meaning of:\n\n「 {item.word} 」",
                    "options": opts,
                    "answer": item.definition,
                    "explanation": f"Example: {item.example}" if item.example else ""
                })

        self._current_q = 0
        self._score = 0
        self._answered = False
        self._show_question_at(0)

    def _start_ai_quiz(self):
        words = [i.word for i in self.vocab_bank.items[:15]]
        if not words:
            self.question_label.setText("❌ Vocab bank trống!")
            return
        if not self.gemini_web or not self.gemini_web._is_ready:
            self.question_label.setText("❌ Cần đăng nhập Gemini Web trước! (Tab 🌐 Gemini Web)")
            return

        for rb in self.radio_btns:
            rb.hide()
        self.ai_result_text.show()
        self.ai_result_text.setPlainText("⏳ Gemini đang tạo quiz...")
        self.submit_btn.setEnabled(False)

        def run():
            prompt = (
                f"Create a 5-question English fill-in-the-blank quiz using these words: "
                f"{', '.join(words[:10])}.\n"
                f"Format each question as:\nQ1. The ___ was very long. (Answer: journey)\n"
                f"Provide answers at the end labeled ANSWERS:"
            )
            try:
                import asyncio
                loop = asyncio.new_event_loop()
                result = loop.run_until_complete(self.gemini_web.chat(prompt))
                loop.close()
            except Exception as e:
                result = f"❌ Lỗi Gemini Web: {e}"
            self.ai_question_ready.emit(result)

        threading.Thread(target=run, daemon=True).start()

    def _show_ai_result(self, text: str):
        self.ai_result_text.setPlainText(text)

    def _show_question_at(self, idx: int):
        if idx >= len(self._questions):
            self._show_results()
            return

        for rb in self.radio_btns:
            rb.show()
        self.ai_result_text.hide()

        q = self._questions[idx]
        self.question_label.setText(q["question"])
        self.feedback_label.setText("")
        self._answered = False
        self.submit_btn.setEnabled(False)
        self.next_btn.setEnabled(False)

        for i, rb in enumerate(self.radio_btns):
            if i < len(q["options"]):
                rb.setText(q["options"][i])
                rb.show()
                rb.setChecked(False)
                rb.setStyleSheet("QRadioButton { color:#ccc; padding:6px; } QRadioButton:hover { color:white; }")
            else:
                rb.hide()

        total = len(self._questions)
        self.prog_label.setText(f"Q {idx+1}/{total}")
        self.prog_bar.setValue(int(idx / total * 100))
        self.score_label.setText(f"Score: {self._score}/{idx}")

    def _show_question(self, q: dict):
        pass  # used via signal if needed

    def _submit(self):
        if self._answered:
            return
        checked = self.btn_group.checkedButton()
        if not checked:
            return

        self._answered = True
        q = self._questions[self._current_q]
        selected = checked.text()
        correct = q["answer"]

        if selected == correct:
            self._score += 1
            self.feedback_label.setText("✅ Correct!")
            self.feedback_label.setStyleSheet("background:#1a3a1a; color:#2ecc71; border-radius:6px; padding:6px;")
            checked.setStyleSheet("QRadioButton { color:#2ecc71; font-weight:bold; padding:6px; }")
        else:
            self.feedback_label.setText(f"❌ Wrong! Correct: {correct}\n{q.get('explanation','')}")
            self.feedback_label.setStyleSheet("background:#3a1a1a; color:#e74c3c; border-radius:6px; padding:6px;")
            checked.setStyleSheet("QRadioButton { color:#e74c3c; padding:6px; }")
            for rb in self.radio_btns:
                if rb.text() == correct:
                    rb.setStyleSheet("QRadioButton { color:#2ecc71; font-weight:bold; padding:6px; }")

        self.score_label.setText(f"Score: {self._score}/{self._current_q+1}")
        self.next_btn.setEnabled(True)
        self.submit_btn.setEnabled(False)

    def _next_question(self):
        self._current_q += 1
        self._show_question_at(self._current_q)

    def _show_results(self):
        total = len(self._questions)
        pct = int(self._score / max(total, 1) * 100)
        emoji = "🏆" if pct >= 80 else "👍" if pct >= 60 else "📚"
        self.question_label.setText(
            f"{emoji} Quiz Complete!\n\n"
            f"Score: {self._score} / {total}  ({pct}%)\n\n"
            f"{'Excellent! 🌟' if pct >= 80 else 'Good job! Keep practicing!' if pct >= 60 else 'Keep studying! You got this! 💪'}"
        )
        for rb in self.radio_btns:
            rb.hide()
        self.feedback_label.setText("")
        self.prog_bar.setValue(100)
        self.submit_btn.setEnabled(False)
        self.next_btn.setEnabled(False)
