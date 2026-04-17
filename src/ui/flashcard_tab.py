"""
Flashcard Tab - Hệ thống ôn tập từ vựng theo spaced repetition
"""
import random
from datetime import datetime, timedelta
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QFrame, QProgressBar, QComboBox, QGroupBox,
    QSizePolicy, QStackedWidget
)
from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve, QRect
from PySide6.QtGui import QFont, QColor


class FlashCard(QFrame):
    """Widget hiển thị một thẻ flashcard (lật được)"""
    clicked = Signal()

    def __init__(self):
        super().__init__()
        self._showing_front = True
        self._front_text = ""
        self._back_text = ""
        self.setMinimumHeight(220)
        self.setFrameShape(QFrame.Shape.Panel)
        self.setStyleSheet("""
            FlashCard {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1e2a4a, stop:1 #0d1b35);
                border: 2px solid #2a82da;
                border-radius: 16px;
            }
            FlashCard:hover { border-color: #4fc3f7; }
        """)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.hint_label = QLabel("[ click to flip ]")
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint_label.setStyleSheet("color:#555; font-size:11px;")
        layout.addWidget(self.hint_label)

        self.main_label = QLabel("")
        self.main_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_label.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        self.main_label.setStyleSheet("color:#4fc3f7;")
        self.main_label.setWordWrap(True)
        layout.addWidget(self.main_label)

        self.sub_label = QLabel("")
        self.sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sub_label.setFont(QFont("Segoe UI", 12))
        self.sub_label.setStyleSheet("color:#a0c4ff;")
        self.sub_label.setWordWrap(True)
        layout.addWidget(self.sub_label)

    def set_card(self, front: str, back: str, sub: str = ""):
        self._front_text = front
        self._back_text = back
        self._sub = sub
        self._showing_front = True
        self.main_label.setText(front)
        self.sub_label.setText("")
        self.hint_label.setText("🃏 Click để xem nghĩa")

    def flip(self):
        self._showing_front = not self._showing_front
        if self._showing_front:
            self.main_label.setText(self._front_text)
            self.sub_label.setText("")
            self.hint_label.setText("🃏 Click để xem nghĩa")
            self.setStyleSheet(self.styleSheet())
        else:
            self.main_label.setText(self._back_text)
            self.sub_label.setText(self._sub)
            self.hint_label.setText("✅ Nghĩa của từ")
            self.setStyleSheet("""
                FlashCard {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #1a3a1a, stop:1 #0d2010);
                    border: 2px solid #27ae60;
                    border-radius: 16px;
                }
            """)

    def mousePressEvent(self, event):
        self.flip()
        self.clicked.emit()


class FlashcardTab(QWidget):
    """Tab ôn tập flashcard với simple spaced repetition"""

    def __init__(self, vocab_bank):
        super().__init__()
        self.vocab_bank = vocab_bank
        self._deck: list = []
        self._current_index = 0
        self._session_correct = 0
        self._session_total = 0
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Header
        header = QHBoxLayout()
        header.addWidget(QLabel("🃏 Flashcard Review"))
        header.addStretch()

        self.deck_label = QLabel("Deck: All")
        header.addWidget(self.deck_label)

        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["All", "easy", "medium", "hard", "Due Today"])
        self.filter_combo.setFixedWidth(110)
        self.filter_combo.currentTextChanged.connect(self._load_deck)
        header.addWidget(self.filter_combo)

        shuffle_btn = QPushButton("🔀 Shuffle")
        shuffle_btn.setFixedWidth(90)
        shuffle_btn.clicked.connect(self._shuffle)
        header.addWidget(shuffle_btn)
        layout.addLayout(header)

        # Progress
        prog_row = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setStyleSheet("""
            QProgressBar { border-radius:4px; background:#222; }
            QProgressBar::chunk { background:#2a82da; border-radius:4px; }
        """)
        prog_row.addWidget(self.progress_bar)
        self.progress_label = QLabel("0 / 0")
        self.progress_label.setFixedWidth(60)
        prog_row.addWidget(self.progress_label)
        layout.addLayout(prog_row)

        # Session stats
        stats_row = QHBoxLayout()
        self.correct_label = QLabel("✅ Correct: 0")
        self.correct_label.setStyleSheet("color:#27ae60; font-weight:bold;")
        self.wrong_label = QLabel("❌ Wrong: 0")
        self.wrong_label.setStyleSheet("color:#e74c3c; font-weight:bold;")
        self.score_label = QLabel("Score: -")
        self.score_label.setStyleSheet("color:#f39c12; font-weight:bold;")
        stats_row.addWidget(self.correct_label)
        stats_row.addWidget(self.wrong_label)
        stats_row.addStretch()
        stats_row.addWidget(self.score_label)
        layout.addLayout(stats_row)

        # FlashCard widget
        self.card = FlashCard()
        layout.addWidget(self.card, stretch=1)

        # Buttons
        btn_row = QHBoxLayout()

        self.wrong_btn = QPushButton("❌ Sai")
        self.wrong_btn.setFixedHeight(48)
        self.wrong_btn.setStyleSheet("""
            QPushButton { background:#c0392b; color:white; border-radius:8px; font-size:15px; font-weight:bold; }
            QPushButton:hover { background:#e74c3c; }
        """)
        self.wrong_btn.clicked.connect(lambda: self._answer(False))

        self.skip_btn = QPushButton("⏭ Skip")
        self.skip_btn.setFixedWidth(90)
        self.skip_btn.setFixedHeight(48)
        self.skip_btn.setStyleSheet(
            "QPushButton { background:#555; color:white; border-radius:8px; }"
        )
        self.skip_btn.clicked.connect(self._next)

        self.correct_btn = QPushButton("✅ Đúng")
        self.correct_btn.setFixedHeight(48)
        self.correct_btn.setStyleSheet("""
            QPushButton { background:#27ae60; color:white; border-radius:8px; font-size:15px; font-weight:bold; }
            QPushButton:hover { background:#2ecc71; }
        """)
        self.correct_btn.clicked.connect(lambda: self._answer(True))

        btn_row.addWidget(self.wrong_btn)
        btn_row.addWidget(self.skip_btn)
        btn_row.addWidget(self.correct_btn)
        layout.addLayout(btn_row)

        # Restart
        restart_btn = QPushButton("🔄 Restart Session")
        restart_btn.clicked.connect(self._restart)
        restart_btn.setStyleSheet("color:#888; background:transparent; border:1px solid #444; border-radius:4px; padding:4px;")
        layout.addWidget(restart_btn)

        self._load_deck()

    def _load_deck(self):
        f = self.filter_combo.currentText()
        if f == "All":
            self._deck = list(self.vocab_bank.items)
        elif f == "Due Today":
            self._deck = list(self.vocab_bank.items)  # simplified
        else:
            self._deck = self.vocab_bank.get_by_difficulty(f)

        self._current_index = 0
        self._session_correct = 0
        self._session_total = 0
        self.deck_label.setText(f"Deck: {f} ({len(self._deck)})")
        self._update_progress()
        self._show_card()

    def _shuffle(self):
        random.shuffle(self._deck)
        self._current_index = 0
        self._show_card()

    def _show_card(self):
        if not self._deck:
            self.card.set_card("📭 No cards", "Hãy thêm từ vựng trước!", "")
            self._set_buttons_enabled(False)
            return
        self._set_buttons_enabled(True)
        if self._current_index >= len(self._deck):
            self._show_done()
            return
        item = self._deck[self._current_index]
        self.card.set_card(item.word, item.definition, item.example)
        self._update_progress()

    def _show_done(self):
        pct = int(self._session_correct / max(self._session_total, 1) * 100)
        self.card.set_card(
            "🎉 Session Complete!",
            f"Score: {self._session_correct}/{self._session_total} ({pct}%)",
            "Click Restart để ôn lại"
        )
        self._set_buttons_enabled(False)
        self.score_label.setText(f"Score: {pct}%")

    def _answer(self, correct: bool):
        if self._current_index >= len(self._deck):
            return
        item = self._deck[self._current_index]
        item.review_count += 1
        if correct:
            item.correct_count += 1
            self._session_correct += 1
        self._session_total += 1
        self._update_stats()
        self._next()

    def _next(self):
        self._current_index += 1
        self._show_card()

    def _restart(self):
        self._load_deck()

    def _update_progress(self):
        total = len(self._deck)
        current = min(self._current_index + 1, total)
        self.progress_label.setText(f"{current} / {total}")
        if total:
            self.progress_bar.setValue(int(self._current_index / total * 100))

    def _update_stats(self):
        wrong = self._session_total - self._session_correct
        self.correct_label.setText(f"✅ Correct: {self._session_correct}")
        self.wrong_label.setText(f"❌ Wrong: {wrong}")

    def _set_buttons_enabled(self, val: bool):
        for btn in [self.correct_btn, self.wrong_btn, self.skip_btn]:
            btn.setEnabled(val)

    def refresh(self):
        """Gọi khi vocab_bank cập nhật"""
        self._load_deck()
