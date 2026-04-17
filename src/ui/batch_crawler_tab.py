"""
Batch Crawler Tab - Crawl nhiều URL cùng lúc, export kết quả
"""
import threading
import csv
import json
from pathlib import Path
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTextEdit, QTableWidget, QTableWidgetItem, QGroupBox,
    QProgressBar, QFileDialog, QHeaderView, QAbstractItemView,
    QComboBox, QCheckBox, QSplitter
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont


class BatchCrawlerTab(QWidget):
    row_done = Signal(int, dict)   # row_index, result

    def __init__(self, crawler, gemini_web, signals):
        super().__init__()
        self.crawler = crawler
        self.gemini_web = gemini_web
        self.signals = signals
        self._running = False
        self._results: list[dict] = []
        self.row_done.connect(self._update_row)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # URL Input
        input_group = QGroupBox("📋 URL List (một URL mỗi dòng)")
        input_layout = QVBoxLayout(input_group)

        self.url_input = QTextEdit()
        self.url_input.setFixedHeight(120)
        self.url_input.setPlaceholderText(
            "https://example.com\nhttps://bbc.com/news\nhttps://learningenglish.voanews.com\n..."
        )
        self.url_input.setFont(QFont("Consolas", 9))
        input_layout.addWidget(self.url_input)

        # Options row
        opt_row = QHBoxLayout()
        opt_row.addWidget(QLabel("Mode:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Simple", "Stealth", "JS Browser"])
        self.mode_combo.setFixedWidth(110)
        opt_row.addWidget(self.mode_combo)

        self.analyze_cb = QCheckBox("🤖 AI Summarize each page")
        opt_row.addWidget(self.analyze_cb)
        opt_row.addStretch()

        self.start_btn = QPushButton("▶ Start Batch Crawl")
        self.start_btn.setFixedHeight(34)
        self.start_btn.setStyleSheet("background:#2a82da; color:white; border-radius:5px; font-weight:bold; padding:0 16px;")
        self.start_btn.clicked.connect(self._start)

        self.stop_btn = QPushButton("⏹ Stop")
        self.stop_btn.setFixedWidth(80)
        self.stop_btn.setFixedHeight(34)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("background:#c0392b; color:white; border-radius:5px;")
        self.stop_btn.clicked.connect(self._stop)

        opt_row.addWidget(self.start_btn)
        opt_row.addWidget(self.stop_btn)
        input_layout.addLayout(opt_row)
        layout.addWidget(input_group)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setStyleSheet("""
            QProgressBar { border-radius:4px; background:#222; }
            QProgressBar::chunk { background:#27ae60; border-radius:4px; }
        """)
        layout.addWidget(self.progress_bar)

        # Results table
        splitter = QSplitter(Qt.Orientation.Vertical)

        table_box = QGroupBox("📊 Results")
        table_layout = QVBoxLayout(table_box)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["URL", "Status", "Title", "Words", "Summary / Error"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget { gridline-color:#333; }
            QTableWidget::item:selected { background:#2a82da; }
        """)
        self.table.cellDoubleClicked.connect(self._open_detail)
        table_layout.addWidget(self.table)
        splitter.addWidget(table_box)

        # Detail view
        detail_box = QGroupBox("📄 Detail (double-click row)")
        detail_layout = QVBoxLayout(detail_box)
        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setFont(QFont("Segoe UI", 10))
        detail_layout.addWidget(self.detail_text)
        splitter.addWidget(detail_box)
        splitter.setSizes([400, 200])
        layout.addWidget(splitter, stretch=1)

        # Export buttons
        export_row = QHBoxLayout()
        export_row.addStretch()
        for label, func in [("📥 Export CSV", self._export_csv), ("📥 Export JSON", self._export_json)]:
            btn = QPushButton(label)
            btn.setFixedHeight(30)
            btn.setStyleSheet("background:#34495e; color:white; border-radius:4px; padding:0 12px;")
            btn.clicked.connect(func)
            export_row.addWidget(btn)
        layout.addLayout(export_row)

    def _start(self):
        urls_raw = self.url_input.toPlainText().strip().split("\n")
        urls = [u.strip() for u in urls_raw if u.strip() and u.strip().startswith("http")]
        if not urls:
            self.signals.status_changed.emit("❌ Không có URL hợp lệ!")
            return

        self._running = True
        self._results = []
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.table.setRowCount(0)
        self.progress_bar.setMaximum(len(urls))
        self.progress_bar.setValue(0)

        def run():
            for i, url in enumerate(urls):
                if not self._running:
                    break
                self.signals.status_changed.emit(f"Crawling {i+1}/{len(urls)}: {url}")

                result = self.crawler.fetch(url)
                summary = ""

                if result.get("success") and self.analyze_cb.isChecked() and self.gemini_web and self.gemini_web._is_ready:
                    try:
                        import asyncio
                        loop = asyncio.new_event_loop()
                        summary = loop.run_until_complete(
                            self.gemini_web.chat(f"Summarize this page in 1 sentence:\n{result.get('text','')[:2000]}")
                        )
                        loop.close()
                    except Exception:
                        summary = "(AI unavailable)"

                row_data = {
                    "url": url,
                    "success": result.get("success", False),
                    "status": result.get("status", ""),
                    "title": result.get("title", ""),
                    "word_count": len(result.get("text", "").split()),
                    "text": result.get("text", "")[:5000],
                    "links": result.get("links", []),
                    "summary": summary,
                    "error": result.get("error", ""),
                }
                self._results.append(row_data)
                self.row_done.emit(i, row_data)

            self._running = False
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            done = len(self._results)
            ok = sum(1 for r in self._results if r["success"])
            self.signals.status_changed.emit(f"✅ Batch done: {ok}/{done} success")
            self.progress_bar.setValue(self.progress_bar.maximum())

        threading.Thread(target=run, daemon=True).start()

    def _stop(self):
        self._running = False
        self.stop_btn.setEnabled(False)

    def _update_row(self, row_index: int, data: dict):
        self.table.insertRow(row_index)
        color = QColor("#1a3a1a") if data["success"] else QColor("#3a1a1a")

        def cell(text: str, align=Qt.AlignmentFlag.AlignLeft) -> QTableWidgetItem:
            item = QTableWidgetItem(str(text))
            item.setBackground(color)
            item.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
            return item

        self.table.setItem(row_index, 0, cell(data["url"]))
        status_text = f"{'✅' if data['success'] else '❌'} {data.get('status','')}"
        self.table.setItem(row_index, 1, cell(status_text, Qt.AlignmentFlag.AlignCenter))
        self.table.setItem(row_index, 2, cell(data["title"]))
        self.table.setItem(row_index, 3, cell(str(data["word_count"]), Qt.AlignmentFlag.AlignCenter))
        info = data["summary"] if data["summary"] else data.get("error", "OK")
        self.table.setItem(row_index, 4, cell(info))

        self.table.setRowHeight(row_index, 26)
        self.progress_bar.setValue(row_index + 1)

    def _open_detail(self, row: int, col: int):
        if row < len(self._results):
            r = self._results[row]
            detail = (
                f"URL: {r['url']}\n"
                f"Title: {r['title']}\n"
                f"Status: {r.get('status','')}\n"
                f"Words: {r['word_count']}\n"
                f"Links: {len(r.get('links',[]))}\n\n"
                f"{'SUMMARY:\n' + r['summary'] if r['summary'] else ''}\n\n"
                f"TEXT PREVIEW:\n{r.get('text','')[:2000]}"
            )
            self.detail_text.setPlainText(detail)

    def _export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export CSV", "batch_results.csv", "CSV Files (*.csv)")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["url", "success", "status", "title", "word_count", "summary", "error"])
            writer.writeheader()
            for r in self._results:
                writer.writerow({k: r.get(k, "") for k in writer.fieldnames})
        self.signals.status_changed.emit(f"✅ Exported CSV: {path}")

    def _export_json(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export JSON", "batch_results.json", "JSON Files (*.json)")
        if not path:
            return
        export = [{k: v for k, v in r.items() if k != "text"} for r in self._results]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(export, f, ensure_ascii=False, indent=2)
        self.signals.status_changed.emit(f"✅ Exported JSON: {path}")
