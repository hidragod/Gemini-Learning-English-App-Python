"""
Crawler Tab UI
"""
import threading
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QTextEdit, QLabel, QComboBox, QSplitter, QListWidget, QGroupBox
)
from PySide6.QtCore import Qt, Signal, QObject


class CrawlerTab(QWidget):
    result_ready = Signal(dict)

    def __init__(self, crawler, signals):
        super().__init__()
        self.crawler = crawler
        self.signals = signals
        self._setup_ui()
        self.result_ready.connect(self._show_result)

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # URL bar
        url_group = QGroupBox("🔍 Fetch URL")
        url_layout = QHBoxLayout(url_group)
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://example.com")
        self.url_input.returnPressed.connect(self._fetch)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Simple Fetch", "Stealth Fetch", "JS Browser"])
        self.mode_combo.setFixedWidth(140)

        self.fetch_btn = QPushButton("Fetch")
        self.fetch_btn.setFixedWidth(80)
        self.fetch_btn.clicked.connect(self._fetch)
        self.fetch_btn.setStyleSheet("background:#2a82da; color:white; border-radius:4px; padding:6px;")

        url_layout.addWidget(self.url_input)
        url_layout.addWidget(self.mode_combo)
        url_layout.addWidget(self.fetch_btn)
        layout.addWidget(url_group)

        # CSS Selector
        sel_group = QGroupBox("CSS Selector Query")
        sel_layout = QHBoxLayout(sel_group)
        self.sel_input = QLineEdit()
        self.sel_input.setPlaceholderText("e.g. h1, .article, table")
        self.sel_btn = QPushButton("Query")
        self.sel_btn.setFixedWidth(70)
        self.sel_btn.clicked.connect(self._query_css)
        sel_layout.addWidget(self.sel_input)
        sel_layout.addWidget(self.sel_btn)
        layout.addWidget(sel_group)

        # Splitter: text + links
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Text result
        text_box = QGroupBox("📄 Page Content")
        text_layout = QVBoxLayout(text_box)
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setFont(__import__("PySide6.QtGui", fromlist=["QFont"]).QFont("Consolas", 9))
        text_layout.addWidget(self.result_text)
        splitter.addWidget(text_box)

        # Links list
        links_box = QGroupBox("🔗 Links")
        links_layout = QVBoxLayout(links_box)
        self.links_list = QListWidget()
        self.links_list.itemDoubleClicked.connect(lambda item: self.url_input.setText(item.text()))
        links_layout.addWidget(self.links_list)
        splitter.addWidget(links_box)

        splitter.setSizes([700, 300])
        layout.addWidget(splitter)

    def _fetch(self):
        url = self.url_input.text().strip()
        if not url:
            return
        if not url.startswith("http"):
            url = "https://" + url
            self.url_input.setText(url)

        self.fetch_btn.setEnabled(False)
        self.result_text.setPlainText("⏳ Đang fetch...")
        self.signals.status_changed.emit(f"Fetching {url}...")

        mode = self.mode_combo.currentText()

        def run():
            if mode == "JS Browser":
                from src.crawler.crawler import BrowserCrawler
                result = BrowserCrawler().fetch_with_js(url)
            elif mode == "Stealth Fetch":
                result = self.crawler.fetch(url)  # stealth via Scrapling
            else:
                result = self.crawler.fetch(url)
            self.result_ready.emit(result)

        threading.Thread(target=run, daemon=True).start()

    def _show_result(self, result: dict):
        self.fetch_btn.setEnabled(True)
        if result.get("success"):
            title = result.get("title", "")
            text = result.get("text", "")
            self.result_text.setPlainText(f"Title: {title}\n\n{text[:10000]}")
            links = result.get("links", [])
            self.links_list.clear()
            for link in links[:100]:
                if link:
                    self.links_list.addItem(link)
            self.signals.status_changed.emit(f"✅ Fetched | {len(text)} chars | {len(links)} links")
        else:
            self.result_text.setPlainText(f"❌ Error: {result.get('error')}")
            self.signals.status_changed.emit("❌ Fetch failed")

    def _query_css(self):
        url = self.url_input.text().strip()
        sel = self.sel_input.text().strip()
        if not url or not sel:
            return

        def run():
            result = self.crawler.fetch(url)
            if result["success"]:
                elements = self.crawler.search_elements(result["html"], sel)
                text = "\n---\n".join(elements) if elements else "(No elements found)"
                self.result_ready.emit({"success": True, "text": text, "links": []})
            else:
                self.result_ready.emit(result)

        threading.Thread(target=run, daemon=True).start()

    def get_current_text(self) -> str:
        return self.result_text.toPlainText()

    def get_current_url(self) -> str:
        return self.url_input.text()
