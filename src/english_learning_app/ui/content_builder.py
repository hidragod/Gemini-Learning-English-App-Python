"""Reusable content builder for reading, writing, grammar, and listening."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .styles import (
    ACCENT,
    ACCENT_ALT,
    BG_CARD,
    BG_INPUT,
    BORDER,
    TEXT_MAIN,
    TEXT_MUTED,
    app_font,
    card_style,
    display_font,
)


READING_TOPICS = [
    "Vietnamese culture and traditions",
    "Environmental issues",
    "Technology in modern life",
    "Health and wellness",
    "Travel and tourism in Vietnam",
    "Education system",
    "Food and cuisine",
    "Career and work-life balance",
    "Social media impact",
    "Climate change",
    "Artificial Intelligence",
    "Space exploration",
    "Mental health awareness",
    "E-commerce",
    "Traditional Vietnamese festivals",
]

WRITING_TOPICS = [
    "Introduce yourself",
    "Describe your hometown",
    "The importance of learning English",
    "Environmental problems",
    "Advantages of technology",
    "My dream job",
    "A formal letter",
    "An informal email to a friend",
    "My daily routine",
    "My favorite hobby",
    "Food in my country",
]

GRAMMAR_TOPICS = [
    "Present Simple vs Present Continuous",
    "Past Simple vs Past Continuous",
    "Present Perfect",
    "Conditional sentences",
    "Modal verbs",
    "Passive voice",
    "Reported speech",
    "Articles",
    "Prepositions of time and place",
    "Comparatives and superlatives",
]

LISTENING_TOPICS = [
    "Daily life sentences",
    "Travel and directions",
    "Food and ordering",
    "Health and doctor visits",
    "Work and office",
    "Shopping",
    "Weather and seasons",
    "Family and friends",
    "Technology",
    "Education",
]

LEVELS = ["A1", "A2", "B1", "B2", "C1"]


def _card(radius: int = 12) -> QFrame:
    frame = QFrame()
    frame.setObjectName("card")
    frame.setStyleSheet(f"QFrame#card{{{card_style(radius)}}}")
    return frame


def _safe_json(raw: str):
    raw = re.sub(r"```(?:json)?\s*", "", raw, flags=re.IGNORECASE).strip().rstrip("`").strip()
    for left, right in [("{", "}"), ("[", "]")]:
        start = raw.find(left)
        end = raw.rfind(right)
        if start != -1 and end > start:
            try:
                return json.loads(raw[start : end + 1])
            except Exception:
                pass
    return None


class BuilderWorker(QThread):
    item_done = Signal(int, dict)
    progress = Signal(int, int, str)
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, mode: str, topics: list[str], level: str, total: int):
        super().__init__()
        self.mode = mode
        self.topics = topics
        self.level = level
        self.total = total
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        from src.english_learning_app.modules.ai_module import (
            _call_web,
            _use_web,
            generate_grammar_exercise,
            generate_reading_passage,
        )

        if not _use_web():
            self.error.emit("Gemini Web is not connected. Open Gemini Web first.")
            return

        items: list[dict] = []
        topics = self.topics or ["General"]
        for index in range(self.total):
            if self._stop:
                break
            topic = topics[index % len(topics)]
            self.progress.emit(index, self.total, f"{self.mode.title()} {index + 1}: {topic}")
            try:
                item = self._generate_one(topic, self.level, generate_reading_passage, generate_grammar_exercise, _call_web)
                item["_topic"] = topic
                item["_level"] = self.level
                item["_created"] = datetime.now().isoformat(timespec="seconds")
                items.append(item)
                self.item_done.emit(index, item)
            except Exception as exc:
                self.error.emit(f"Item {index + 1} failed: {exc}")
        self.finished.emit(items)

    def _generate_one(self, topic, level, gen_reading, gen_grammar, call_web) -> dict:
        if self.mode == "reading":
            return gen_reading("", topic, level)
        if self.mode == "grammar":
            return {"grammar_point": topic, "exercises": gen_grammar("", topic)}
        if self.mode == "writing":
            prompt = f"""Create one writing task for topic "{topic}" at {level} level.
Return JSON only:
{{"topic":"{topic}","prompt":"Write task","guide":"3 short bullet-style tips","vocabulary":["word1","word2","word3"],"min_words":80,"max_words":140}}"""
            raw = call_web(prompt)
            return _safe_json(raw) or {
                "topic": topic,
                "prompt": raw[:300],
                "guide": "",
                "vocabulary": [],
                "min_words": 80,
                "max_words": 140,
            }
        if self.mode == "listening":
            prompt = f"""Generate 5 natural dictation sentences about "{topic}" at {level} level.
Return JSON only:
{{"topic":"{topic}","sentences":["sentence 1","sentence 2","sentence 3","sentence 4","sentence 5"],"difficulty":"{level}"}}"""
            raw = call_web(prompt)
            return _safe_json(raw) or {
                "topic": topic,
                "sentences": [raw[:200]],
                "difficulty": level,
            }
        return {}


class ContentBuilderWidget(QWidget):
    imported = Signal(list)

    MODES = {
        "reading": ("Reading", READING_TOPICS),
        "writing": ("Writing", WRITING_TOPICS),
        "grammar": ("Grammar", GRAMMAR_TOPICS),
        "listening": ("Listening", LISTENING_TOPICS),
    }

    def __init__(self, mode: str, parent=None):
        super().__init__(parent)
        self.mode = mode
        self._worker: BuilderWorker | None = None
        self._items: list[dict] = []
        self._mode_label, self._topics = self.MODES[mode]
        self._build_ui()
        self._ai_timer = QTimer(self)
        self._ai_timer.timeout.connect(self._refresh_ai_buttons)
        self._ai_timer.start(1500)
        self._refresh_ai_buttons()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(14)

        config = _card()
        config_layout = QVBoxLayout(config)
        config_layout.setContentsMargins(18, 16, 18, 16)
        config_layout.setSpacing(12)

        header = QLabel(f"{self._mode_label} Builder")
        header.setFont(display_font(15))
        config_layout.addWidget(header)

        config_row = QHBoxLayout()

        level_col = QVBoxLayout()
        level_label = QLabel("Level")
        level_label.setStyleSheet(f"color:{TEXT_MUTED};")
        level_col.addWidget(level_label)
        self.level_cb = QComboBox()
        self.level_cb.addItems(LEVELS)
        self.level_cb.setCurrentText("B1")
        self.level_cb.setFixedWidth(100)
        level_col.addWidget(self.level_cb)
        config_row.addLayout(level_col)

        total_col = QVBoxLayout()
        total_label = QLabel("Total items")
        total_label.setStyleSheet(f"color:{TEXT_MUTED};")
        total_col.addWidget(total_label)
        self.total_spin = QSpinBox()
        self.total_spin.setRange(1, 200)
        self.total_spin.setValue(5)
        self.total_spin.setFixedWidth(110)
        self.total_spin.setFont(app_font(11))
        total_col.addWidget(self.total_spin)
        config_row.addLayout(total_col)

        topic_col = QVBoxLayout()
        topic_label = QLabel("Topic source")
        topic_label.setStyleSheet(f"color:{TEXT_MUTED};")
        topic_col.addWidget(topic_label)
        self.topics_cb = QComboBox()
        self.topics_cb.addItem("Rotate all topics")
        self.topics_cb.addItems(self._topics)
        self.topics_cb.setMinimumWidth(280)
        topic_col.addWidget(self.topics_cb)
        config_row.addLayout(topic_col)

        config_row.addStretch()
        config_layout.addLayout(config_row)
        root.addWidget(config)

        buttons = QHBoxLayout()
        self.start_btn = QPushButton("Generate")
        self.start_btn.setObjectName("btnPrimary")
        self.start_btn.clicked.connect(self._start)
        buttons.addWidget(self.start_btn)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setObjectName("btnDanger")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop)
        buttons.addWidget(self.stop_btn)

        self.import_btn = QPushButton("Import JSON")
        self.import_btn.clicked.connect(self._import)
        buttons.addWidget(self.import_btn)

        self.export_btn = QPushButton("Export JSON")
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self._export)
        buttons.addWidget(self.export_btn)

        self.save_db_btn = QPushButton("Save to Library")
        self.save_db_btn.setObjectName("btnSuccess")
        self.save_db_btn.setEnabled(False)
        self.save_db_btn.clicked.connect(self._save_to_db)
        buttons.addWidget(self.save_db_btn)

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self._clear)
        buttons.addWidget(self.clear_btn)

        buttons.addStretch()
        self.count_lbl = QLabel("0 items")
        self.count_lbl.setFont(app_font(12, QFont.Weight.Bold))
        self.count_lbl.setStyleSheet(f"color:{ACCENT_ALT};")
        buttons.addWidget(self.count_lbl)
        root.addLayout(buttons)

        progress_card = _card(8)
        progress_layout = QVBoxLayout(progress_card)
        progress_layout.setContentsMargins(14, 10, 14, 10)
        self.status_lbl = QLabel("Ready to generate library content.")
        self.status_lbl.setStyleSheet(f"color:{TEXT_MUTED};")
        progress_layout.addWidget(self.status_lbl)
        self.prog_bar = QProgressBar()
        self.prog_bar.setValue(0)
        self.prog_bar.setFixedHeight(8)
        progress_layout.addWidget(self.prog_bar)
        root.addWidget(progress_card)

        list_label = QLabel("Generated Items")
        list_label.setFont(display_font(14))
        root.addWidget(list_label)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(["#", "Topic", "Summary"])
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.itemClicked.connect(self._on_item_click)
        self.tree.setStyleSheet(
            f"""
            QTreeWidget {{
                background:{BG_CARD};
                color:{TEXT_MAIN};
                border:1px solid {BORDER};
                border-radius:10px;
                font-size:13px;
            }}
            QTreeWidget::item:selected {{
                background:{ACCENT};
                color:white;
            }}
            QHeaderView::section {{
                background:{BG_INPUT};
                color:{TEXT_MUTED};
                border:none;
                border-bottom:1px solid {BORDER};
                padding:8px;
                font-weight:600;
            }}
            """
        )
        root.addWidget(self.tree, 1)

        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setFixedHeight(180)
        self.preview.setFont(app_font(11))
        self.preview.setPlaceholderText("Select an item to inspect the generated content.")
        root.addWidget(self.preview)

    def _start(self):
        from src.english_learning_app.modules.ai_module import _use_web, get_web_job_status

        if not _use_web():
            QMessageBox.warning(self, "AI unavailable", "Gemini Web is not connected. Open Gemini Web first.")
            return
        busy_job = get_web_job_status()
        if busy_job:
            self.status_lbl.setText(f"Gemini Web is busy: {busy_job}")
            self.status_lbl.setStyleSheet("color:#f59e0b;")
            return

        topics = self._topics if self.topics_cb.currentIndex() == 0 else [self.topics_cb.currentText()]
        total = self.total_spin.value()
        level = self.level_cb.currentText()

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.prog_bar.setMaximum(total)
        self.prog_bar.setValue(0)
        self.status_lbl.setText(f"Generating {total} {self.mode} items at {level}...")
        self.status_lbl.setStyleSheet(f"color:{ACCENT};")

        self._worker = BuilderWorker(self.mode, topics, level, total)
        self._worker.item_done.connect(self._on_item)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _stop(self):
        if self._worker:
            self._worker.stop()
        self.stop_btn.setEnabled(False)
        self.status_lbl.setText("Generation stopped by user.")
        self.status_lbl.setStyleSheet(f"color:{TEXT_MUTED};")

    def _on_progress(self, done: int, total: int, label: str):
        self.prog_bar.setValue(done)
        self.status_lbl.setText(f"{done}/{total} · {label}")

    def _on_item(self, idx: int, item: dict):
        self._items.append(item)
        self._add_tree_row(idx + 1, item)
        self.count_lbl.setText(f"{len(self._items)} items")

    def _on_finished(self, _items: list):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.export_btn.setEnabled(bool(self._items))
        self.save_db_btn.setEnabled(bool(self._items))
        self.prog_bar.setValue(len(self._items))
        self.status_lbl.setText(f"Done. {len(self._items)} items ready.")
        self.status_lbl.setStyleSheet(f"color:{ACCENT_ALT};")
        self._refresh_ai_buttons()

    def _on_error(self, message: str):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_lbl.setText(f"Generation error: {message[:100]}")
        self.status_lbl.setStyleSheet("color:#f87171;")
        self._refresh_ai_buttons()

    def _refresh_ai_buttons(self):
        from src.english_learning_app.modules.ai_module import get_web_job_status

        busy_job = get_web_job_status()
        running = bool(self._worker and self._worker.isRunning())
        self.start_btn.setEnabled(not running and not busy_job)
        if busy_job and not running:
            self.start_btn.setToolTip(f"Gemini Web is busy: {busy_job}")
            if self.status_lbl.text() in {"Ready to generate library content.", "Generation stopped by user."} or self.status_lbl.text().startswith("Done."):
                self.status_lbl.setText(f"Gemini Web is busy: {busy_job}")
                self.status_lbl.setStyleSheet("color:#f59e0b;")
        else:
            self.start_btn.setToolTip("")

    def _add_tree_row(self, number: int, item: dict):
        node = QTreeWidgetItem(self.tree)
        node.setText(0, str(number))
        topic = item.get("_topic", item.get("topic", item.get("grammar_point", "General")))
        node.setText(1, topic)
        if self.mode == "reading":
            node.setText(2, f"{len(item.get('passage', '').split())} words · {len(item.get('questions', []))} questions")
        elif self.mode == "grammar":
            node.setText(2, f"{len(item.get('exercises', []))} exercise(s)")
        elif self.mode == "writing":
            node.setText(2, f"{item.get('min_words', 80)}-{item.get('max_words', 140)} words")
        elif self.mode == "listening":
            node.setText(2, f"{len(item.get('sentences', []))} sentences")
        node.setData(0, Qt.ItemDataRole.UserRole, item)
        self.tree.scrollToBottom()

    def _on_item_click(self, node: QTreeWidgetItem, _column: int):
        item = node.data(0, Qt.ItemDataRole.UserRole)
        if not item:
            return
        if self.mode == "reading":
            questions = "\n".join(f"{i}. {q}" for i, q in enumerate(item.get("questions", []), start=1))
            answers = "\n".join(f"{i}. {a}" for i, a in enumerate(item.get("answers", []), start=1))
            text = f"Passage:\n{item.get('passage', '')}\n\nQuestions:\n{questions}\n\nAnswers:\n{answers}"
        elif self.mode == "grammar":
            lines = []
            for index, exercise in enumerate(item.get("exercises", []), start=1):
                lines.append(f"{index}. {exercise.get('question', '')}")
                lines.append(f"Answer: {exercise.get('answer', '')}")
                lines.append(f"Explanation: {exercise.get('explanation', '')}")
                lines.append("")
            text = "\n".join(lines)
        elif self.mode == "writing":
            vocab = ", ".join(item.get("vocabulary", []))
            text = (
                f"Topic: {item.get('topic', '')}\n\n"
                f"Prompt:\n{item.get('prompt', '')}\n\n"
                f"Guide:\n{item.get('guide', '')}\n\n"
                f"Useful vocabulary: {vocab}"
            )
        elif self.mode == "listening":
            sentences = "\n".join(f"{i}. {s}" for i, s in enumerate(item.get("sentences", []), start=1))
            text = f"Topic: {item.get('topic', '')}\nLevel: {item.get('difficulty', '')}\n\n{sentences}"
        else:
            text = json.dumps(item, ensure_ascii=False, indent=2)
        self.preview.setPlainText(text)

    def _import(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import JSON",
            str(Path.home() / "Downloads"),
            "JSON Files (*.json);;All Files (*)",
        )
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data = data.get("items", data.get(self.mode, [data]))
            if not isinstance(data, list):
                raise ValueError("JSON must be a list or an object with an 'items' key.")
            start_index = len(self._items)
            self._items.extend(data)
            for offset, item in enumerate(data, start=1):
                self._add_tree_row(start_index + offset, item)
            self.count_lbl.setText(f"{len(self._items)} items")
            self.export_btn.setEnabled(bool(self._items))
            self.save_db_btn.setEnabled(bool(self._items))
            self.status_lbl.setText(f"Imported {len(data)} items from {Path(path).name}.")
            self.status_lbl.setStyleSheet(f"color:{ACCENT_ALT};")
            self.imported.emit(data)
        except Exception as exc:
            QMessageBox.critical(self, "Import error", str(exc))

    def _save_to_db(self):
        if not self._items:
            return
        from src.english_learning_app.modules import database as db

        saved = 0
        failed = 0
        for item in self._items:
            try:
                if self.mode == "reading":
                    db.save_reading_item(
                        passage=item.get("passage", ""),
                        topic=item.get("_topic", item.get("topic", "General")),
                        questions=item.get("questions", []),
                        answers=item.get("answers", []),
                        level=item.get("_level", "B1"),
                    )
                elif self.mode == "grammar":
                    db.save_grammar_library_set(
                        grammar_point=item.get("grammar_point", item.get("_topic", "General")),
                        exercises=item.get("exercises", []),
                    )
                elif self.mode == "writing":
                    db.save_writing_prompt(
                        topic=item.get("topic", item.get("_topic", "General")),
                        prompt=item.get("prompt", ""),
                        guide=item.get("guide", ""),
                        vocabulary=item.get("vocabulary", []),
                        level=item.get("_level", "B1"),
                    )
                elif self.mode == "listening":
                    db.save_listening_set(
                        topic=item.get("_topic", item.get("topic", "General")),
                        sentences=item.get("sentences", []),
                        level=item.get("_level", "B1"),
                    )
                saved += 1
            except Exception:
                failed += 1

        message = f"Saved {saved} item(s) to the library."
        if failed:
            message += f" {failed} item(s) failed."
        self.status_lbl.setText(message)
        self.status_lbl.setStyleSheet(f"color:{ACCENT_ALT};")
        QMessageBox.information(self, "Save complete", message)

    def _export(self):
        if not self._items:
            return
        default_name = f"{self.mode}_content_{len(self._items)}.json"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export JSON",
            str(Path.home() / "Downloads" / default_name),
            "JSON Files (*.json);;All Files (*)",
        )
        if not path:
            return
        payload = {
            "mode": self.mode,
            "exported_at": datetime.now().isoformat(timespec="seconds"),
            "count": len(self._items),
            "items": self._items,
        }
        Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        QMessageBox.information(self, "Export complete", f"Saved {len(self._items)} item(s) to:\n{path}")

    def _clear(self):
        self._items.clear()
        self.tree.clear()
        self.preview.clear()
        self.count_lbl.setText("0 items")
        self.export_btn.setEnabled(False)
        self.save_db_btn.setEnabled(False)
        self.prog_bar.setValue(0)
        self.status_lbl.setText("Cleared.")
        self.status_lbl.setStyleSheet(f"color:{TEXT_MUTED};")

    def get_items(self) -> list:
        return list(self._items)
