"""
English Learning Tab - Tích hợp Crawler + Gemini Web cho học tiếng Anh
Dùng GeminiWebClient (browser) thay vì API
"""
import threading
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QTextEdit, QLabel, QComboBox, QGroupBox, QSplitter,
    QListWidget, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont


class EnglishLearningTab(QWidget):
    content_ready = Signal(dict)
    analysis_ready = Signal(str)

    def __init__(self, gemini_web, crawler, signals):
        super().__init__()
        self.gemini_web = gemini_web   # GeminiWebClient (có thể None nếu chưa login)
        self.crawler = crawler
        self.signals = signals
        self._current_text = ""
        self._current_url = ""
        self._setup_ui()
        self.content_ready.connect(self._show_content)
        self.analysis_ready.connect(self._show_analysis)

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # ── URL Fetch Panel ──
        fetch_group = QGroupBox("📖 Load English Content")
        fetch_layout = QHBoxLayout(fetch_group)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://www.bbc.com/news/... hoặc bất kỳ bài tiếng Anh nào")
        self.url_input.returnPressed.connect(self._load_content)

        self.content_type = QComboBox()
        self.content_type.addItems(["article", "vocabulary", "grammar", "story"])
        self.content_type.setFixedWidth(110)

        self.load_btn = QPushButton("📥 Load")
        self.load_btn.setFixedWidth(80)
        self.load_btn.setStyleSheet("background:#27ae60; color:white; border-radius:4px; padding:6px;")
        self.load_btn.clicked.connect(self._load_content)

        fetch_layout.addWidget(self.url_input)
        fetch_layout.addWidget(self.content_type)
        fetch_layout.addWidget(self.load_btn)
        layout.addWidget(fetch_group)

        # ── Quick Sources ──
        quick_group = QGroupBox("⚡ Quick Sources")
        quick_layout = QHBoxLayout(quick_group)
        sources = [
            ("BBC News",     "https://www.bbc.com/news"),
            ("VOA Learning", "https://learningenglish.voanews.com"),
            ("CNN",          "https://edition.cnn.com"),
            ("TED Blog",     "https://blog.ted.com"),
        ]
        for name, url in sources:
            btn = QPushButton(name)
            btn.setFixedHeight(28)
            btn.clicked.connect(lambda checked, u=url: self._quick_load(u))
            btn.setStyleSheet("background:#34495e; color:white; border-radius:3px; padding:4px 8px;")
            quick_layout.addWidget(btn)
        quick_layout.addStretch()
        layout.addWidget(quick_group)

        # ── Main Splitter ──
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Article text
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        left_header = QHBoxLayout()
        left_header.addWidget(QLabel("📄 Article Text"))
        self.word_count_label = QLabel("Words: 0")
        self.word_count_label.setStyleSheet("color:#888;")
        left_header.addStretch()
        left_header.addWidget(self.word_count_label)
        left_layout.addLayout(left_header)

        self.article_text = QTextEdit()
        self.article_text.setReadOnly(True)
        self.article_text.setFont(QFont("Georgia", 11))
        self.article_text.setStyleSheet(
            "QTextEdit { background:#1e1e2e; color:#dde; padding:10px; border-radius:6px; }"
        )
        left_layout.addWidget(self.article_text)
        splitter.addWidget(left_widget)

        # Right: AI Analysis
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        task_group = QGroupBox("🤖 AI Analysis  (yêu cầu đăng nhập Gemini Web trước)")
        task_layout = QVBoxLayout(task_group)

        btn_row = QHBoxLayout()
        tasks = [
            ("📝 Vocabulary", "vocabulary"),
            ("📐 Grammar",    "grammar"),
            ("📋 Summary",    "summary"),
            ("❓ Quiz",       "quiz"),
        ]
        for label, task in tasks:
            btn = QPushButton(label)
            btn.setFixedHeight(32)
            btn.setStyleSheet(
                "QPushButton { background:#2c3e50; color:#ecf0f1; border-radius:4px; }"
                "QPushButton:hover { background:#3d5166; }"
            )
            btn.clicked.connect(lambda checked, t=task: self._analyze(t))
            btn_row.addWidget(btn)
        task_layout.addLayout(btn_row)

        custom_layout = QHBoxLayout()
        self.custom_prompt = QLineEdit()
        self.custom_prompt.setPlaceholderText("Custom question about the article...")
        custom_btn = QPushButton("Ask")
        custom_btn.setFixedWidth(55)
        custom_btn.setStyleSheet("background:#8e44ad; color:white; border-radius:4px;")
        custom_btn.clicked.connect(self._custom_analyze)
        custom_layout.addWidget(self.custom_prompt)
        custom_layout.addWidget(custom_btn)
        task_layout.addLayout(custom_layout)
        right_layout.addWidget(task_group)

        self.analysis_text = QTextEdit()
        self.analysis_text.setReadOnly(True)
        self.analysis_text.setFont(QFont("Segoe UI", 10))
        self.analysis_text.setStyleSheet(
            "QTextEdit { background:#1a1a2e; color:#e0e0e0; border-radius:6px; padding:8px; }"
        )
        right_layout.addWidget(self.analysis_text, stretch=1)

        # Vocabulary list
        vocab_group = QGroupBox("🗂️ Saved Vocabulary")
        vocab_layout = QVBoxLayout(vocab_group)
        self.vocab_list = QListWidget()
        self.vocab_list.setMaximumHeight(120)
        vocab_layout.addWidget(self.vocab_list)
        btn_row2 = QHBoxLayout()
        save_btn = QPushButton("💾 Save to Vocab List")
        save_btn.clicked.connect(self._save_vocab)
        clear_btn = QPushButton("🗑️ Clear")
        clear_btn.setFixedWidth(60)
        clear_btn.clicked.connect(self.vocab_list.clear)
        btn_row2.addWidget(save_btn)
        btn_row2.addWidget(clear_btn)
        vocab_layout.addLayout(btn_row2)
        right_layout.addWidget(vocab_group)

        splitter.addWidget(right_widget)
        splitter.setSizes([500, 500])
        layout.addWidget(splitter, stretch=1)

    # ── Slots ────────────────────────────────────────────────────────────────

    def _quick_load(self, url: str):
        self.url_input.setText(url)
        self._load_content()

    def _load_content(self):
        url = self.url_input.text().strip()
        if not url:
            return
        if not url.startswith("http"):
            url = "https://" + url
            self.url_input.setText(url)

        self._current_url = url
        self.load_btn.setEnabled(False)
        self.article_text.setPlainText("⏳ Đang tải bài...")
        self.signals.status_changed.emit(f"Loading: {url}")

        def run():
            result = self.crawler.fetch(url)
            if result["success"]:
                self.content_ready.emit({
                    "success": True,
                    "url": url,
                    "title": result.get("title", ""),
                    "text": result.get("text", ""),
                })
            else:
                self.content_ready.emit({"success": False, "error": result.get("error", "")})

        threading.Thread(target=run, daemon=True).start()

    def _show_content(self, data: dict):
        self.load_btn.setEnabled(True)
        if data.get("success"):
            text = data.get("text", "")
            title = data.get("title", "")
            self._current_text = text
            display = f"--- {title} ---\n\n{text}" if title else text
            self.article_text.setPlainText(display[:15000])
            wc = len(text.split())
            self.word_count_label.setText(f"Words: {wc:,}")
            self.signals.status_changed.emit(f"✅ Loaded | {wc:,} words")
        else:
            self.article_text.setPlainText(f"❌ {data.get('error', 'Unknown error')}")
            self.signals.status_changed.emit("❌ Load failed")

    def _analyze(self, task: str):
        if not self._current_text:
            QMessageBox.warning(self, "No Content", "Hãy load bài viết trước!")
            return
        if not self.gemini_web or not self.gemini_web._is_ready:
            QMessageBox.warning(self, "Gemini Web",
                "Cần đăng nhập Gemini Web trước!\nVào tab '🌐 Gemini Web' → Open Browser & Login")
            return

        self.analysis_text.setPlainText(f"⏳ Đang phân tích ({task})...")
        self.signals.status_changed.emit(f"🤖 Analyzing: {task}...")

        task_prompts = {
            "vocabulary": f"From this English text, list 10 important vocabulary words with definitions and examples:\n\n{self._current_text[:3000]}",
            "grammar":    f"Analyze key grammar structures in this text:\n\n{self._current_text[:3000]}",
            "summary":    f"Summarize this text in simple English:\n\n{self._current_text[:3000]}",
            "quiz":       f"Create 5 multiple-choice questions about this content:\n\n{self._current_text[:3000]}",
        }
        prompt = task_prompts.get(task, self._current_text[:3000])

        def run():
            try:
                import asyncio
                loop = asyncio.new_event_loop()
                response = loop.run_until_complete(self.gemini_web.chat(prompt))
                loop.close()
                self.analysis_ready.emit(response)
            except Exception as e:
                self.analysis_ready.emit(f"❌ Lỗi: {e}")

        threading.Thread(target=run, daemon=True).start()

    def _custom_analyze(self):
        question = self.custom_prompt.text().strip()
        if not question or not self._current_text:
            return
        if not self.gemini_web or not self.gemini_web._is_ready:
            QMessageBox.warning(self, "Gemini Web",
                "Cần đăng nhập Gemini Web trước!\nVào tab '🌐 Gemini Web' → Open Browser & Login")
            return

        self.analysis_text.setPlainText("⏳ Đang xử lý...")
        prompt = f"{question}\n\nContext:\n{self._current_text[:4000]}"

        def run():
            try:
                import asyncio
                loop = asyncio.new_event_loop()
                response = loop.run_until_complete(self.gemini_web.chat(prompt))
                loop.close()
                self.analysis_ready.emit(response)
            except Exception as e:
                self.analysis_ready.emit(f"❌ Lỗi: {e}")

        threading.Thread(target=run, daemon=True).start()

    def _show_analysis(self, text: str):
        self.analysis_text.setPlainText(text)
        self.signals.status_changed.emit("✅ Analysis complete")

    def _save_vocab(self):
        for line in self.analysis_text.toPlainText().split("\n"):
            line = line.strip()
            if line and len(line) > 3:
                self.vocab_list.addItem(line)
