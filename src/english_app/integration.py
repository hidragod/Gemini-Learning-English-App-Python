"""
English App Integration Module
Kết nối với phần mềm học tiếng Anh đã có sẵn
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTextEdit, QLabel, QGroupBox, QListWidget, QListWidgetItem,
    QSplitter, QComboBox, QLineEdit, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
import json
from pathlib import Path


# ─── Data model ──────────────────────────────────────────────────────────────

class VocabularyItem:
    def __init__(self, word: str, definition: str, example: str = "",
                 source_url: str = "", difficulty: str = "medium"):
        self.word = word
        self.definition = definition
        self.example = example
        self.source_url = source_url
        self.difficulty = difficulty
        self.review_count = 0
        self.correct_count = 0

    def to_dict(self) -> dict:
        return self.__dict__

    @classmethod
    def from_dict(cls, d: dict):
        item = cls(d["word"], d["definition"], d.get("example", ""),
                   d.get("source_url", ""), d.get("difficulty", "medium"))
        item.review_count = d.get("review_count", 0)
        item.correct_count = d.get("correct_count", 0)
        return item


class VocabularyBank:
    """Quản lý ngân hàng từ vựng, lưu JSON local"""

    def __init__(self, save_path: str = "vocabulary_bank.json"):
        self.save_path = Path(save_path)
        self.items: list[VocabularyItem] = []
        self.load()

    def add(self, item: VocabularyItem):
        # Tránh trùng lặp
        existing = [i for i in self.items if i.word.lower() == item.word.lower()]
        if not existing:
            self.items.append(item)
            self.save()

    def remove(self, word: str):
        self.items = [i for i in self.items if i.word.lower() != word.lower()]
        self.save()

    def save(self):
        with open(self.save_path, "w", encoding="utf-8") as f:
            json.dump([i.to_dict() for i in self.items], f, ensure_ascii=False, indent=2)

    def load(self):
        if self.save_path.exists():
            try:
                with open(self.save_path, encoding="utf-8") as f:
                    data = json.load(f)
                self.items = [VocabularyItem.from_dict(d) for d in data]
            except Exception:
                self.items = []

    def search(self, query: str) -> list[VocabularyItem]:
        q = query.lower()
        return [i for i in self.items if q in i.word.lower() or q in i.definition.lower()]

    def get_by_difficulty(self, difficulty: str) -> list[VocabularyItem]:
        return [i for i in self.items if i.difficulty == difficulty]


# ─── Widget ──────────────────────────────────────────────────────────────────

class EnglishAppIntegration(QWidget):
    """Widget tích hợp vào phần mềm học tiếng Anh chính"""

    word_selected = Signal(str)   # emit khi chọn từ để tra cứu

    def __init__(self, gemini_web=None, vocab_bank: VocabularyBank = None):
        super().__init__()
        self.gemini_web = gemini_web
        self.vocab_bank = vocab_bank or VocabularyBank()
        self._setup_ui()
        self._refresh_list()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Search
        search_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search vocabulary...")
        self.search_input.textChanged.connect(self._on_search)
        search_row.addWidget(self.search_input)

        diff_filter = QComboBox()
        diff_filter.addItems(["All", "easy", "medium", "hard"])
        diff_filter.setFixedWidth(80)
        diff_filter.currentTextChanged.connect(self._filter_difficulty)
        search_row.addWidget(diff_filter)
        layout.addLayout(search_row)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Vocab list
        list_box = QGroupBox(f"📚 Vocabulary Bank ({len(self.vocab_bank.items)} words)")
        list_layout = QVBoxLayout(list_box)
        self.vocab_list = QListWidget()
        self.vocab_list.currentItemChanged.connect(self._on_item_selected)
        list_layout.addWidget(self.vocab_list)

        list_btns = QHBoxLayout()
        del_btn = QPushButton("🗑 Remove")
        del_btn.setStyleSheet("background:#c0392b; color:white; border-radius:3px; padding:4px;")
        del_btn.clicked.connect(self._delete_word)
        export_btn = QPushButton("📤 Export")
        export_btn.clicked.connect(self._export)
        list_btns.addWidget(del_btn)
        list_btns.addWidget(export_btn)
        list_layout.addLayout(list_btns)
        splitter.addWidget(list_box)

        # Detail panel
        detail_box = QGroupBox("📖 Word Detail")
        detail_layout = QVBoxLayout(detail_box)

        self.word_label = QLabel("")
        self.word_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self.word_label.setStyleSheet("color:#4fc3f7;")
        detail_layout.addWidget(self.word_label)

        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setFont(QFont("Segoe UI", 10))
        detail_layout.addWidget(self.detail_text)

        # Add word manually
        add_group = QGroupBox("➕ Add Word")
        add_layout = QVBoxLayout(add_group)
        self.new_word = QLineEdit(); self.new_word.setPlaceholderText("Word")
        self.new_def = QLineEdit(); self.new_def.setPlaceholderText("Definition")
        self.new_example = QLineEdit(); self.new_example.setPlaceholderText("Example sentence (optional)")
        diff_row = QHBoxLayout()
        diff_row.addWidget(QLabel("Difficulty:"))
        self.new_diff = QComboBox()
        self.new_diff.addItems(["easy", "medium", "hard"])
        self.new_diff.setCurrentIndex(1)
        diff_row.addStretch()
        diff_row.addWidget(self.new_diff)

        add_btn = QPushButton("➕ Add to Bank")
        add_btn.setStyleSheet("background:#27ae60; color:white; border-radius:4px; padding:6px;")
        add_btn.clicked.connect(self._add_word)

        ai_btn = QPushButton("🤖 AI Generate Definition")
        ai_btn.setStyleSheet("background:#8e44ad; color:white; border-radius:4px; padding:6px;")
        ai_btn.clicked.connect(self._ai_define)

        for w in [self.new_word, self.new_def, self.new_example]:
            add_layout.addWidget(w)
        add_layout.addLayout(diff_row)
        add_layout.addWidget(add_btn)
        add_layout.addWidget(ai_btn)
        detail_layout.addWidget(add_group)
        splitter.addWidget(detail_box)

        splitter.setSizes([300, 400])
        layout.addWidget(splitter, stretch=1)

    def _refresh_list(self, items=None):
        self.vocab_list.clear()
        source = items if items is not None else self.vocab_bank.items
        for item in source:
            diff_emoji = {"easy": "🟢", "medium": "🟡", "hard": "🔴"}.get(item.difficulty, "⚪")
            self.vocab_list.addItem(f"{diff_emoji} {item.word}")

    def _on_item_selected(self, current, previous):
        if not current:
            return
        word = current.text().split(" ", 1)[1] if " " in current.text() else current.text()
        items = [i for i in self.vocab_bank.items if i.word == word]
        if items:
            item = items[0]
            self.word_label.setText(item.word)
            detail = (
                f"📖 Definition:\n{item.definition}\n\n"
                f"💬 Example:\n{item.example or '(none)'}\n\n"
                f"🔗 Source: {item.source_url or '(manual)'}\n"
                f"⭐ Difficulty: {item.difficulty}\n"
                f"📊 Reviews: {item.review_count} | Correct: {item.correct_count}"
            )
            self.detail_text.setPlainText(detail)
            self.word_selected.emit(word)

    def _on_search(self, text: str):
        if text:
            self._refresh_list(self.vocab_bank.search(text))
        else:
            self._refresh_list()

    def _filter_difficulty(self, diff: str):
        if diff == "All":
            self._refresh_list()
        else:
            self._refresh_list(self.vocab_bank.get_by_difficulty(diff))

    def _add_word(self):
        word = self.new_word.text().strip()
        definition = self.new_def.text().strip()
        if not word or not definition:
            QMessageBox.warning(self, "Input Error", "Cần nhập word và definition!")
            return
        item = VocabularyItem(
            word=word,
            definition=definition,
            example=self.new_example.text().strip(),
            difficulty=self.new_diff.currentText()
        )
        self.vocab_bank.add(item)
        self._refresh_list()
        for w in [self.new_word, self.new_def, self.new_example]:
            w.clear()

    def _ai_define(self):
        word = self.new_word.text().strip()
        if not word or not self.gemini_web:
            QMessageBox.warning(self, "Gemini Web",
                "Cần đăng nhập Gemini Web trước!\nVào tab '🌐 Gemini Web' → Open Browser & Login")
            return
        if not self.gemini_web._is_ready:
            QMessageBox.warning(self, "Gemini Web", "Gemini Web chưa sẵn sàng!")
            return
        prompt = (
            f"Define the English word '{word}' concisely. "
            f"Provide: 1) definition, 2) one example sentence. "
            f"Format:\nDEFINITION: ...\nEXAMPLE: ..."
        )
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(self.gemini_web.chat(prompt))
            loop.close()
        except Exception as e:
            result = ""
        lines = result.split("\n")
        for line in lines:
            if line.startswith("DEFINITION:"):
                self.new_def.setText(line.replace("DEFINITION:", "").strip())
            elif line.startswith("EXAMPLE:"):
                self.new_example.setText(line.replace("EXAMPLE:", "").strip())

    def _delete_word(self):
        item = self.vocab_list.currentItem()
        if not item:
            return
        word = item.text().split(" ", 1)[1] if " " in item.text() else item.text()
        self.vocab_bank.remove(word)
        self._refresh_list()

    def _export(self):
        import csv
        path = Path("vocabulary_export.csv")
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["word", "definition", "example", "difficulty"])
            writer.writeheader()
            for item in self.vocab_bank.items:
                writer.writerow({
                    "word": item.word,
                    "definition": item.definition,
                    "example": item.example,
                    "difficulty": item.difficulty,
                })
        QMessageBox.information(self, "Exported", f"✅ Exported to {path.absolute()}")

    def import_from_gemini_analysis(self, analysis_text: str, source_url: str = ""):
        """Parse kết quả phân tích từ Gemini và thêm vào vocab bank"""
        lines = analysis_text.split("\n")
        added = 0
        for line in lines:
            line = line.strip()
            if ":" in line and len(line) > 5 and not line.startswith("#"):
                parts = line.split(":", 1)
                word = parts[0].strip().lstrip("0123456789.-) ").strip()
                definition = parts[1].strip() if len(parts) > 1 else ""
                if word and definition and len(word.split()) <= 3:
                    item = VocabularyItem(word, definition, source_url=source_url)
                    self.vocab_bank.add(item)
                    added += 1
        if added:
            self._refresh_list()
        return added
