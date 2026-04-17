"""Database manager for reviewing and cleaning learning data."""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QHeaderView,
    QAbstractItemView,
)

from ..modules import database as db
from .styles import (
    ACCENT,
    ACCENT_DANGER,
    BG_CARD,
    BG_INPUT,
    BORDER,
    TEXT_MAIN,
    TEXT_MUTED,
    app_font,
    card_style,
    display_font,
    tab_style,
)


def _card() -> QFrame:
    frame = QFrame()
    frame.setObjectName("card")
    frame.setStyleSheet(f"QFrame#card{{{card_style(12)}}}")
    return frame


def _table(headers: list[str]) -> QTableWidget:
    table = QTableWidget()
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setAlternatingRowColors(False)
    table.setWordWrap(False)
    table.verticalHeader().setVisible(False)
    table.horizontalHeader().setStretchLastSection(True)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    table.setStyleSheet(
        f"""
        QTableWidget {{
            background: {BG_INPUT};
            color: {TEXT_MAIN};
            border: 1px solid {BORDER};
            border-radius: 10px;
            gridline-color: {BORDER};
            font-size: 13px;
        }}
        QHeaderView::section {{
            background: {BG_CARD};
            color: {TEXT_MAIN};
            padding: 8px 10px;
            border: none;
            border-bottom: 1px solid {BORDER};
            font-weight: 600;
        }}
        QTableWidget::item:selected {{
            background: {ACCENT};
            color: white;
        }}
        """
    )
    return table


def _excerpt(text: str, limit: int = 72) -> str:
    text = (text or "").replace("\n", " ").strip()
    return text if len(text) <= limit else text[: limit - 1] + "..."


def _load_json_records(parent: QWidget, title: str) -> list[dict] | None:
    path, _ = QFileDialog.getOpenFileName(
        parent,
        title,
        str(Path.home() / "Downloads"),
        "JSON Files (*.json);;All Files (*)",
    )
    if not path:
        return None
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = data.get("items", data.get("rows", [data]))
        if not isinstance(data, list):
            raise ValueError("JSON must be a list or an object with an 'items' key.")
        return [item for item in data if isinstance(item, dict)]
    except Exception as exc:
        QMessageBox.critical(parent, "Import error", str(exc))
        return None


def _export_json_records(parent: QWidget, title: str, filename: str, rows: list[dict]):
    path, _ = QFileDialog.getSaveFileName(
        parent,
        title,
        str(Path.home() / "Downloads" / filename),
        "JSON Files (*.json);;All Files (*)",
    )
    if not path:
        return
    payload = {"count": len(rows), "items": rows}
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    QMessageBox.information(parent, "Export complete", f"Saved {len(rows)} record(s) to:\n{path}")


def _insert_reading_rows(rows: list[dict]) -> int:
    conn = db.get_connection()
    c = conn.cursor()
    inserted = 0
    for row in rows:
        passage = row.get("passage", "")
        topic = row.get("topic", "General")
        if not passage:
            continue
        c.execute(
            """
            INSERT INTO reading_history (passage, topic, questions, answers, score, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                passage,
                topic,
                json.dumps(row.get("questions", []), ensure_ascii=False),
                json.dumps(row.get("answers", []), ensure_ascii=False),
                row.get("score", 0),
                row.get("created_at") or None,
            ),
        )
        inserted += 1
    conn.commit()
    conn.close()
    return inserted


def _insert_writing_rows(rows: list[dict]) -> int:
    conn = db.get_connection()
    c = conn.cursor()
    inserted = 0
    for row in rows:
        if not row.get("content"):
            continue
        c.execute(
            """
            INSERT INTO writing_history (topic, content, feedback, score, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                row.get("topic", "General"),
                row.get("content", ""),
                row.get("feedback", ""),
                row.get("score", 0),
                row.get("created_at") or None,
            ),
        )
        inserted += 1
    conn.commit()
    conn.close()
    return inserted


def _insert_grammar_rows(rows: list[dict]) -> int:
    conn = db.get_connection()
    c = conn.cursor()
    inserted = 0
    for row in rows:
        if not row.get("question"):
            continue
        c.execute(
            """
            INSERT INTO grammar_history
                (exercise_type, question, user_answer, correct_answer, explanation, is_correct, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row.get("exercise_type", "General"),
                row.get("question", ""),
                row.get("user_answer", ""),
                row.get("correct_answer", ""),
                row.get("explanation", ""),
                int(bool(row.get("is_correct", 0))),
                row.get("created_at") or None,
            ),
        )
        inserted += 1
    conn.commit()
    conn.close()
    return inserted


def _insert_grammar_library_rows(rows: list[dict]) -> int:
    conn = db.get_connection()
    c = conn.cursor()
    inserted = 0
    for row in rows:
        if not row.get("question"):
            continue
        c.execute(
            """
            INSERT OR IGNORE INTO grammar_library (grammar_point, question, answer, explanation, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                row.get("grammar_point", "General"),
                row.get("question", ""),
                row.get("answer", ""),
                row.get("explanation", ""),
                row.get("created_at") or None,
            ),
        )
        inserted += c.rowcount
    conn.commit()
    conn.close()
    return inserted


def _insert_listening_rows(rows: list[dict]) -> int:
    conn = db.get_connection()
    c = conn.cursor()
    inserted = 0
    for row in rows:
        if not row.get("original_text"):
            continue
        c.execute(
            """
            INSERT INTO listening_history (original_text, user_answer, accuracy, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                row.get("original_text", ""),
                row.get("user_answer", ""),
                row.get("accuracy", 0),
                row.get("created_at") or None,
            ),
        )
        inserted += 1
    conn.commit()
    conn.close()
    return inserted


def _insert_speaking_rows(rows: list[dict]) -> int:
    conn = db.get_connection()
    c = conn.cursor()
    inserted = 0
    for row in rows:
        if not row.get("topic_text"):
            continue
        c.execute(
            """
            INSERT INTO speaking_history (level, topic_text, user_text, coach_feedback, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                row.get("level", "B1"),
                row.get("topic_text", ""),
                row.get("user_text", ""),
                row.get("coach_feedback", ""),
                row.get("created_at") or None,
            ),
        )
        inserted += 1
    conn.commit()
    conn.close()
    return inserted


class EditWordDialog(QDialog):
    def __init__(self, row_data: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Edit Vocabulary: {row_data.get('word', '')}")
        self.setMinimumWidth(520)
        self.setStyleSheet(
            f"""
            QDialog {{ background: #0f1117; color: {TEXT_MAIN}; }}
            QLabel {{ color: {TEXT_MAIN}; }}
            QLineEdit, QTextEdit, QComboBox {{
                background: {BG_INPUT};
                color: {TEXT_MAIN};
                border: 1px solid {BORDER};
                border-radius: 8px;
                padding: 8px 10px;
                font-size: 13px;
            }}
            """
        )

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(10)

        self.word_edit = QLineEdit(row_data.get("word", ""))
        self.meaning_edit = QLineEdit(row_data.get("meaning_vi", row_data.get("vi", "")))
        self.phonetic_edit = QLineEdit(row_data.get("phonetic", row_data.get("ipa", "")))
        self.pos_combo = QComboBox()
        self.pos_combo.addItems(["noun", "verb", "adjective", "adverb", "phrase", "other"])
        self.pos_combo.setCurrentText(row_data.get("part_of_speech", row_data.get("pos", "noun")) or "noun")
        self.topic_edit = QLineEdit(row_data.get("topic", ""))
        self.level_combo = QComboBox()
        self.level_combo.addItems(["A1", "A2", "B1", "B2", "C1", "C2"])
        self.level_combo.setCurrentText(row_data.get("level", "B1") or "B1")
        self.example_edit = QTextEdit()
        self.example_edit.setFixedHeight(100)
        self.example_edit.setPlainText(row_data.get("example", row_data.get("sentence", "")))

        form.addRow("Word", self.word_edit)
        form.addRow("Meaning", self.meaning_edit)
        form.addRow("Phonetic", self.phonetic_edit)
        form.addRow("Part of speech", self.pos_combo)
        form.addRow("Topic", self.topic_edit)
        form.addRow("Level", self.level_combo)
        form.addRow("Example", self.example_edit)
        layout.addLayout(form)

        buttons = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Save")
        save_btn.setObjectName("btnPrimary")
        save_btn.clicked.connect(self.accept)
        buttons.addStretch()
        buttons.addWidget(cancel_btn)
        buttons.addWidget(save_btn)
        layout.addLayout(buttons)

    def values(self) -> dict:
        return {
            "word": self.word_edit.text().strip(),
            "meaning_vi": self.meaning_edit.text().strip(),
            "phonetic": self.phonetic_edit.text().strip(),
            "part_of_speech": self.pos_combo.currentText(),
            "topic": self.topic_edit.text().strip(),
            "level": self.level_combo.currentText(),
            "example": self.example_edit.toPlainText().strip(),
        }


class RecordTab(QWidget):
    def __init__(
        self,
        title: str,
        loader,
        deleter,
        columns: list[tuple[str, str]],
        detail_builder,
        importer=None,
        parent=None,
    ):
        super().__init__(parent)
        self.title = title
        self.loader = loader
        self.deleter = deleter
        self.columns = columns
        self.detail_builder = detail_builder
        self.importer = importer
        self.rows: list[dict] = []
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        controls = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(f"Search {self.title.lower()}...")
        self.search_edit.textChanged.connect(self.refresh)
        controls.addWidget(self.search_edit, 1)

        self.count_label = QLabel("")
        self.count_label.setStyleSheet(f"color: {TEXT_MUTED};")
        controls.addWidget(self.count_label)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh)
        controls.addWidget(self.refresh_btn)

        self.import_btn = QPushButton("Import JSON")
        self.import_btn.clicked.connect(self._import_json)
        controls.addWidget(self.import_btn)

        self.export_btn = QPushButton("Export JSON")
        self.export_btn.clicked.connect(self._export_json)
        controls.addWidget(self.export_btn)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setObjectName("btnDanger")
        self.delete_btn.setEnabled(False)
        self.delete_btn.clicked.connect(self._delete_selected)
        controls.addWidget(self.delete_btn)
        root.addLayout(controls)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.table = _table([label for label, _ in self.columns])
        self.table.itemSelectionChanged.connect(self._update_detail)
        self.table.doubleClicked.connect(self._update_detail)
        splitter.addWidget(self.table)

        preview_card = _card()
        preview_layout = QVBoxLayout(preview_card)
        preview_layout.setContentsMargins(16, 16, 16, 16)
        preview_layout.setSpacing(10)
        preview_title = QLabel(f"{self.title} Details")
        preview_title.setFont(display_font(15))
        preview_layout.addWidget(preview_title)
        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setMinimumWidth(320)
        self.preview.setPlaceholderText("Select a row to inspect the saved data.")
        preview_layout.addWidget(self.preview)
        splitter.addWidget(preview_card)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        root.addWidget(splitter, 1)

    def refresh(self):
        self.rows = self.loader(self.search_edit.text().strip())
        self.table.setRowCount(len(self.rows))
        for row_idx, row in enumerate(self.rows):
            for col_idx, (_, key) in enumerate(self.columns):
                value = row.get(key, "")
                if isinstance(value, float):
                    text = f"{value:.0%}" if 0 <= value <= 1 else f"{value:.2f}"
                else:
                    text = str(value)
                item = QTableWidgetItem(text)
                if col_idx == 0:
                    item.setData(Qt.ItemDataRole.UserRole, row.get("id"))
                self.table.setItem(row_idx, col_idx, item)
        self.table.resizeColumnsToContents()
        self.count_label.setText(f"{len(self.rows)} records")
        self.delete_btn.setEnabled(False)
        self.preview.clear()

    def _selected_row(self) -> dict | None:
        indexes = self.table.selectionModel().selectedRows()
        if not indexes:
            return None
        return self.rows[indexes[0].row()]

    def _update_detail(self):
        row = self._selected_row()
        self.delete_btn.setEnabled(row is not None)
        self.preview.setPlainText("" if row is None else self.detail_builder(row))

    def _delete_selected(self):
        row = self._selected_row()
        if row is None:
            return
        reply = QMessageBox.question(
            self,
            f"Delete {self.title}",
            "Delete the selected record from the database?",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.deleter(row["id"])
        self.refresh()

    def _export_json(self):
        _export_json_records(
            self,
            f"Export {self.title} JSON",
            f"{self.title.lower()}_records.json",
            self.rows,
        )

    def _import_json(self):
        if self.importer is None:
            QMessageBox.information(self, "Import unavailable", f"Import is not configured for {self.title}.")
            return
        rows = _load_json_records(self, f"Import {self.title} JSON")
        if rows is None:
            return
        inserted = self.importer(rows)
        self.refresh()
        QMessageBox.information(self, "Import complete", f"Imported {inserted} {self.title.lower()} record(s).")


class VocabTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows: list[dict] = []
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        controls = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search vocabulary...")
        self.search_edit.textChanged.connect(self.refresh)
        controls.addWidget(self.search_edit, 1)

        self.topic_combo = QComboBox()
        self.topic_combo.setMinimumWidth(160)
        self.topic_combo.currentTextChanged.connect(self.refresh)
        controls.addWidget(self.topic_combo)

        self.count_label = QLabel("")
        self.count_label.setStyleSheet(f"color: {TEXT_MUTED};")
        controls.addWidget(self.count_label)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh)
        controls.addWidget(self.refresh_btn)

        self.import_btn = QPushButton("Import JSON")
        self.import_btn.clicked.connect(self._import_json)
        controls.addWidget(self.import_btn)

        self.export_btn = QPushButton("Export JSON")
        self.export_btn.clicked.connect(self._export_json)
        controls.addWidget(self.export_btn)

        self.edit_btn = QPushButton("Edit")
        self.edit_btn.setEnabled(False)
        self.edit_btn.clicked.connect(self._edit_selected)
        controls.addWidget(self.edit_btn)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setObjectName("btnDanger")
        self.delete_btn.setEnabled(False)
        self.delete_btn.clicked.connect(self._delete_selected)
        controls.addWidget(self.delete_btn)
        root.addLayout(controls)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.table = _table(["ID", "Word", "Meaning", "Topic", "POS", "Level", "Created"])
        self.table.itemSelectionChanged.connect(self._update_detail)
        self.table.doubleClicked.connect(self._edit_selected)
        splitter.addWidget(self.table)

        detail_card = _card()
        detail_layout = QVBoxLayout(detail_card)
        detail_layout.setContentsMargins(16, 16, 16, 16)
        title = QLabel("Vocabulary Details")
        title.setFont(display_font(15))
        detail_layout.addWidget(title)
        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setPlaceholderText("Select a word to inspect and edit its saved data.")
        detail_layout.addWidget(self.preview)
        splitter.addWidget(detail_card)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        root.addWidget(splitter, 1)

    def refresh(self):
        current_topic = self.topic_combo.currentText() or "All"
        self.topic_combo.blockSignals(True)
        self.topic_combo.clear()
        self.topic_combo.addItems(db.get_topics())
        idx = self.topic_combo.findText(current_topic)
        self.topic_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.topic_combo.blockSignals(False)

        self.rows = db.get_all_words(
            self.search_edit.text().strip(),
            self.topic_combo.currentText() or "All",
        )
        self.table.setRowCount(len(self.rows))
        for row_idx, row in enumerate(self.rows):
            values = [
                row.get("id", ""),
                row.get("word", ""),
                row.get("meaning_vi", row.get("vi", "")),
                row.get("topic", ""),
                row.get("part_of_speech", row.get("pos", "")),
                row.get("level", ""),
                row.get("created_at", ""),
            ]
            for col_idx, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if col_idx == 0:
                    item.setData(Qt.ItemDataRole.UserRole, row.get("id"))
                self.table.setItem(row_idx, col_idx, item)
        self.table.resizeColumnsToContents()
        self.count_label.setText(f"{len(self.rows)} words")
        self.edit_btn.setEnabled(False)
        self.delete_btn.setEnabled(False)
        self.preview.clear()

    def _selected_row(self) -> dict | None:
        indexes = self.table.selectionModel().selectedRows()
        if not indexes:
            return None
        return self.rows[indexes[0].row()]

    def _update_detail(self):
        row = self._selected_row()
        enabled = row is not None
        self.edit_btn.setEnabled(enabled)
        self.delete_btn.setEnabled(enabled)
        if row is None:
            self.preview.clear()
            return
        self.preview.setPlainText(
            "\n".join(
                [
                    f"Word: {row.get('word', '')}",
                    f"Meaning: {row.get('meaning_vi', row.get('vi', ''))}",
                    f"Phonetic: {row.get('phonetic', row.get('ipa', ''))}",
                    f"Part of speech: {row.get('part_of_speech', row.get('pos', ''))}",
                    f"Topic: {row.get('topic', '')}",
                    f"Level: {row.get('level', '')}",
                    "",
                    "Example:",
                    row.get("example", row.get("sentence", "")),
                ]
            )
        )

    def _edit_selected(self):
        row = self._selected_row()
        if row is None:
            return
        dialog = EditWordDialog(row, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        if not values["word"]:
            QMessageBox.warning(self, "Missing word", "Word cannot be empty.")
            return
        db.update_word(row["id"], **values)
        self.refresh()

    def _delete_selected(self):
        row = self._selected_row()
        if row is None:
            return
        reply = QMessageBox.question(
            self,
            "Delete Vocabulary",
            "Delete the selected word and its flashcard progress?",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        db.delete_word(row["id"])
        self.refresh()

    def _export_json(self):
        _export_json_records(
            self,
            "Export Vocabulary JSON",
            "vocabulary_records.json",
            self.rows,
        )

    def _import_json(self):
        rows = _load_json_records(self, "Import Vocabulary JSON")
        if rows is None:
            return
        inserted = 0
        for row in rows:
            word = (row.get("word") or "").strip()
            if not word:
                continue
            db.add_word(
                word=word,
                meaning_vi=row.get("meaning_vi", row.get("vi", "")),
                example=row.get("example", row.get("sentence", "")),
                topic=row.get("topic", "General"),
                phonetic=row.get("phonetic", row.get("ipa", "")),
                part_of_speech=row.get("part_of_speech", row.get("pos", "noun")),
                level=row.get("level", "B1"),
            )
            inserted += 1
        self.refresh()
        QMessageBox.information(self, "Import complete", f"Imported {inserted} vocabulary record(s).")


def _reading_detail(row: dict) -> str:
    questions = row.get("questions") or []
    answers = row.get("answers") or []
    pairs = []
    for idx, question in enumerate(questions, start=1):
        answer = answers[idx - 1] if idx - 1 < len(answers) else ""
        pairs.append(f"{idx}. {question}\nAnswer: {answer}")
    return "\n".join(
        [
            f"Topic: {row.get('topic', '')}",
            f"Score: {row.get('score', 0)}",
            f"Created: {row.get('created_at', '')}",
            "",
            "Passage:",
            row.get("passage", ""),
            "",
            "Questions:",
            "\n\n".join(pairs) if pairs else "No saved questions.",
        ]
    )


def _writing_detail(row: dict) -> str:
    return "\n".join(
        [
            f"Topic: {row.get('topic', '')}",
            f"Score: {row.get('score', '')}",
            f"Created: {row.get('created_at', '')}",
            "",
            "Draft:",
            row.get("content", ""),
            "",
            "Feedback:",
            row.get("feedback", ""),
        ]
    )


def _grammar_detail(row: dict) -> str:
    return "\n".join(
        [
            f"Exercise type: {row.get('exercise_type', '')}",
            f"Correct: {'Yes' if row.get('is_correct') else 'No'}",
            f"Created: {row.get('created_at', '')}",
            "",
            "Question:",
            row.get("question", ""),
            "",
            "Your answer:",
            row.get("user_answer", ""),
            "",
            "Correct answer:",
            row.get("correct_answer", ""),
            "",
            "Explanation:",
            row.get("explanation", ""),
        ]
    )


def _grammar_library_detail(row: dict) -> str:
    return "\n".join(
        [
            f"Grammar point: {row.get('grammar_point', '')}",
            f"Created: {row.get('created_at', '')}",
            "",
            "Question:",
            row.get("question", ""),
            "",
            "Answer:",
            row.get("answer", ""),
            "",
            "Explanation:",
            row.get("explanation", ""),
        ]
    )


def _listening_mode(row: dict) -> str:
    return "Library" if float(row.get("accuracy", 0)) == -1 else "Practice"


def _listening_detail(row: dict) -> str:
    accuracy = row.get("accuracy", "")
    accuracy_text = "Library item" if float(accuracy) == -1 else f"{float(accuracy):.0%}"
    return "\n".join(
        [
            f"Mode: {_listening_mode(row)}",
            f"Accuracy: {accuracy_text}",
            f"Created: {row.get('created_at', '')}",
            "",
            "Original text:",
            row.get("original_text", ""),
            "",
            "User answer:",
            row.get("user_answer", "") or "(empty)",
        ]
    )


def _speaking_detail(row: dict) -> str:
    return "\n".join(
        [
            f"Level: {row.get('level', '')}",
            f"Created: {row.get('created_at', '')}",
            "",
            "Topic:",
            row.get("topic_text", ""),
            "",
            "User response:",
            row.get("user_text", ""),
            "",
            "Coach feedback:",
            row.get("coach_feedback", ""),
        ]
    )


class MaintenancePanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setStyleSheet(f"QFrame#card{{{card_style(12)}}}")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        title = QLabel("Database Maintenance")
        title.setFont(display_font(16))
        layout.addWidget(title)

        subtitle = QLabel(
            "Use these tools to clean progress, practice history, or rebuild the library state without touching source code."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"color: {TEXT_MUTED};")
        layout.addWidget(subtitle)

        buttons = QHBoxLayout()

        reset_progress_btn = QPushButton("Reset Progress")
        reset_progress_btn.clicked.connect(self._reset_progress)
        buttons.addWidget(reset_progress_btn)

        clear_history_btn = QPushButton("Clear Practice History")
        clear_history_btn.clicked.connect(self._clear_history)
        buttons.addWidget(clear_history_btn)

        clear_library_btn = QPushButton("Clear Library Data")
        clear_library_btn.clicked.connect(self._clear_library)
        buttons.addWidget(clear_library_btn)

        wipe_btn = QPushButton("Clear All Learning Data")
        wipe_btn.setStyleSheet(
            f"background: {ACCENT_DANGER}; color: white; border: none; border-radius: 10px; padding: 8px 18px;"
        )
        wipe_btn.clicked.connect(self._clear_all)
        buttons.addWidget(wipe_btn)

        buttons.addStretch()
        layout.addLayout(buttons)

    def _confirm(self, title: str, message: str) -> bool:
        reply = QMessageBox.warning(
            self,
            title,
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return reply == QMessageBox.StandardButton.Yes

    def _reset_progress(self):
        if not self._confirm("Reset Progress", "Reset flashcard progress and daily progress stats?"):
            return
        db.reset_all_progress()
        QMessageBox.information(self, "Done", "Progress data was reset.")

    def _clear_history(self):
        if not self._confirm("Clear Practice History", "Delete reading, writing, grammar, listening, speaking, and progress history?"):
            return
        db.clear_practice_history()
        QMessageBox.information(self, "Done", "Practice history was cleared.")

    def _clear_library(self):
        if not self._confirm("Clear Library Data", "Delete saved vocabulary, grammar library, and listening library data?"):
            return
        db.clear_library_data()
        QMessageBox.information(self, "Done", "Library data was cleared.")

    def _clear_all(self):
        if not self._confirm("Clear All Learning Data", "This will wipe all learning data and keep only your app settings. Continue?"):
            return
        db.clear_all_learning_data(include_settings=False)
        QMessageBox.information(self, "Done", "All learning data was cleared.")


class DBManagerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        title = QLabel("Database Manager")
        title.setFont(display_font(22))
        root.addWidget(title)

        subtitle = QLabel(
            "Review saved vocabulary, reading, writing, grammar, listening, and speaking records. Clean the database in controlled groups when you need a fresh learning state."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"color: {TEXT_MUTED};")
        root.addWidget(subtitle)

        self.maintenance = MaintenancePanel()
        root.addWidget(self.maintenance)

        tabs = QTabWidget()
        tabs.setStyleSheet(tab_style())
        tabs.setFont(app_font(11, QFont.Weight.Medium))

        tabs.addTab(VocabTab(), "Vocabulary")
        tabs.addTab(
            RecordTab(
                "Reading",
                db.get_all_reading,
                db.delete_reading,
                [("ID", "id"), ("Topic", "topic"), ("Score", "score"), ("Created", "created_at")],
                _reading_detail,
                importer=_insert_reading_rows,
            ),
            "Reading",
        )
        tabs.addTab(
            RecordTab(
                "Writing",
                db.get_all_writing,
                db.delete_writing,
                [("ID", "id"), ("Topic", "topic"), ("Score", "score"), ("Created", "created_at")],
                _writing_detail,
                importer=_insert_writing_rows,
            ),
            "Writing",
        )
        tabs.addTab(
            RecordTab(
                "Grammar Attempts",
                db.get_all_grammar,
                db.delete_grammar,
                [("ID", "id"), ("Type", "exercise_type"), ("Question", "question"), ("Created", "created_at")],
                _grammar_detail,
                importer=_insert_grammar_rows,
            ),
            "Grammar Attempts",
        )
        tabs.addTab(
            RecordTab(
                "Grammar Library",
                db.get_all_grammar_library,
                db.delete_grammar_library,
                [("ID", "id"), ("Point", "grammar_point"), ("Question", "question"), ("Created", "created_at")],
                _grammar_library_detail,
                importer=_insert_grammar_library_rows,
            ),
            "Grammar Library",
        )
        tabs.addTab(
            RecordTab(
                "Listening",
                db.get_all_listening,
                db.delete_listening,
                [("ID", "id"), ("Mode", "mode"), ("Accuracy", "accuracy_text"), ("Content", "summary"), ("Created", "created_at")],
                _listening_detail,
                importer=_insert_listening_rows,
            ),
            "Listening",
        )
        tabs.addTab(
            RecordTab(
                "Speaking",
                db.get_all_speaking,
                db.delete_speaking,
                [("ID", "id"), ("Level", "level"), ("Topic", "summary"), ("Created", "created_at")],
                _speaking_detail,
                importer=_insert_speaking_rows,
            ),
            "Speaking",
        )
        root.addWidget(tabs, 1)

        listening_tab = tabs.widget(5)
        speaking_tab = tabs.widget(6)
        if isinstance(listening_tab, RecordTab):
            original_loader = listening_tab.loader
            listening_tab.loader = lambda search: [
                {
                    **row,
                    "mode": _listening_mode(row),
                    "accuracy_text": "Library" if float(row.get("accuracy", 0)) == -1 else f"{float(row.get('accuracy', 0)):.0%}",
                    "summary": _excerpt(row.get("original_text", "")),
                }
                for row in original_loader(search)
            ]
            listening_tab.refresh()
        if isinstance(speaking_tab, RecordTab):
            original_loader = speaking_tab.loader
            speaking_tab.loader = lambda search: [
                {**row, "summary": _excerpt(row.get("topic_text", ""))}
                for row in original_loader(search)
            ]
            speaking_tab.refresh()
