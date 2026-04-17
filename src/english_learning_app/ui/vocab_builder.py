"""
Vocab Builder Widget
Tích hợp generate_vocab_b1.py vào trong app.
Tạo danh sách từ vựng theo cấp độ, chủ đề, số lượng tùy chỉnh.
Chạy trong QThread — UI không bị freeze.
"""
import asyncio
import json
import re
import threading
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QFrame, QProgressBar, QSpinBox, QLineEdit,
    QTextEdit, QFileDialog, QCheckBox, QGroupBox, QScrollArea,
    QTableWidget, QTableWidgetItem, QHeaderView, QSplitter, QGridLayout,
    QMessageBox, QSizePolicy
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFont, QColor

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent  # src/english_learning_app/ui → project root

GENERAL_ENGLISH_TOPICS = [
    "daily life and routines", "travel and tourism", "food and cooking",
    "health and medicine", "technology and internet", "education and study",
    "work and career", "environment and nature", "culture and traditions",
    "sport and fitness", "shopping and money", "family and relationships",
    "emotions and personality", "transport and directions", "weather and seasons",
    "media and entertainment", "government and society", "science and discovery",
    "art and music", "animals and wildlife", "body and appearance",
    "clothes and fashion", "housing and furniture", "time and schedules",
    "business and economy", "social issues", "hobbies and free time",
    "numbers and measurements", "language and communication", "colors and shapes",
]

SPECIALIZED_TOPICS = [
    "medical English for doctors",
    "anatomy",
    "physiology",
    "microbiology",
    "pathology",
    "pharmacology",
    "biochemistry",
    "immunology",
    "histology",
    "internal medicine",
    "surgery",
    "pediatrics",
    "obstetrics and gynecology",
    "public health",
    "clinical reasoning",
]

TOPICS = GENERAL_ENGLISH_TOPICS + SPECIALIZED_TOPICS

LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]
BUILD_MODES = [
    "General English",
    "Medical Study Pack",
    "Clinical MCQ Pack",
]
SAVE_TOPIC_SUGGESTIONS = [
    "Daily English",
    "Travel English",
    "Business English",
    "Technology English",
    "Medical English for doctors",
    "Doctor-patient communication",
    "Clinical vocabulary",
    "Anatomy",
    "Physiology",
    "Microbiology",
    "Pathology",
    "Pharmacology",
    "Biochemistry",
    "Immunology",
]

ACADEMIC_KEYWORDS = {
    "anatomy",
    "physiology",
    "microbiology",
    "pathology",
    "pharmacology",
    "biochemistry",
    "immunology",
    "histology",
    "clinical",
    "medicine",
    "surgery",
    "pediatrics",
    "obstetrics",
    "gynecology",
    "public health",
    "doctor",
}

STUDY_PACK_PRESETS = [
    {"label": "Anatomy Basics", "topic": "anatomy", "mode": "Medical Study Pack", "level": "B1", "target": 120, "batch": 40},
    {"label": "Physiology Core", "topic": "physiology", "mode": "Medical Study Pack", "level": "B1", "target": 140, "batch": 40},
    {"label": "Microbiology", "topic": "microbiology", "mode": "Medical Study Pack", "level": "B1", "target": 120, "batch": 40},
    {"label": "Clinical Pharma", "topic": "pharmacology", "mode": "Clinical MCQ Pack", "level": "B2", "target": 100, "batch": 30},
    {"label": "Surgery Review", "topic": "surgery", "mode": "Clinical MCQ Pack", "level": "B2", "target": 100, "batch": 30},
    {"label": "Clinical Reasoning", "topic": "clinical reasoning", "mode": "Clinical MCQ Pack", "level": "B2", "target": 90, "batch": 30},
]


# ── Worker Thread ─────────────────────────────────────────────────────────────

class VocabGenWorker(QThread):
    progress    = Signal(int, int, str)   # done, total, topic
    word_batch  = Signal(list)            # list of word dicts mỗi batch
    finished    = Signal(list)            # all words
    error       = Signal(str)

    def __init__(self, level: str, total: int, topics: list[str], batch_size: int = 80, build_mode: str = "General English"):
        super().__init__()
        self.level      = level
        self.total      = total
        self.topics     = topics
        self.batch_size = batch_size
        self.build_mode = build_mode
        self.min_acceptable = max(1, total - max(10, int(total * 0.05)))
        self._stop      = False
        self._loop: asyncio.AbstractEventLoop | None = None

    def _word_key(self, word: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", (word or "").strip().lower())

    def _load_existing_prompt_words(self) -> set[str]:
        from src.english_learning_app.modules import database as db

        conn = db.get_connection()
        c = conn.cursor()
        if self.topics:
            placeholders = ",".join("?" for _ in self.topics)
            c.execute(
                f"SELECT word FROM vocabulary WHERE topic IN ({placeholders})",
                self.topics,
            )
        else:
            c.execute("SELECT word FROM vocabulary")
        words = {(row[0] or "").strip().lower() for row in c.fetchall() if row[0]}
        conn.close()
        return {w for w in words if w}

    def _build_avoid_words(self, session_words: list[str], existing_prompt_words: set[str]) -> list[str]:
        recent = session_words[-120:]
        older_pool = sorted(existing_prompt_words.difference(recent))
        if len(older_pool) > 60:
            step = max(1, len(older_pool) // 60)
            older_pool = older_pool[::step][:60]
        return recent + older_pool

    def stop(self):
        self._stop = True
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)

    def run(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._generate())
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self._loop.close()

    async def _generate(self):
        from src.english_learning_app.modules.ai_module import _call_web, _use_web

        if not _use_web():
            self.error.emit(
                "Gemini Web is not connected.\nOpen Gemini Web and start the browser first."
            )
            return

        all_words: list[dict] = []
        existing: set[str] = set()
        existing_prompt_words = self._load_existing_prompt_words()
        accepted_words_in_order: list[str] = []
        batch_num = 0
        stale_batches = 0
        low_yield_batches = 0
        last_success_topic = self.topics[0] if self.topics else "general english"
        current_batch_size = self.batch_size

        while len(all_words) < self.total and not self._stop:
            remaining = self.total - len(all_words)
            this_batch = min(current_batch_size, remaining)
            topic = self._pick_topic(batch_num, remaining, last_success_topic)
            avoid_words = self._build_avoid_words(accepted_words_in_order, existing_prompt_words)

            self.progress.emit(len(all_words), self.total, topic)
            prompt = self._make_prompt(topic, this_batch, avoid_words)

            try:
                raw = _call_web(
                    prompt,
                    timeout=90,
                    job_name=f"Vocabulary Builder batch {batch_num + 1}",
                )
            except Exception as e:
                self.error.emit(f"Batch {batch_num+1} error: {e}")
                break

            batch = _parse_vocab(raw)
            new_words = []
            raw_count = len(batch)
            for w in batch:
                key = self._word_key(w["word"])
                if key and key not in existing and w["word"]:
                    w["topic"] = topic
                    new_words.append(w)
                    existing.add(key)
                    prompt_word = w["word"].strip().lower()
                    if prompt_word:
                        existing_prompt_words.add(prompt_word)
                        accepted_words_in_order.append(prompt_word)

            accepted_words = new_words[:remaining]
            all_words.extend(accepted_words)
            fresh_ratio = len(new_words) / max(1, raw_count)
            if new_words:
                last_success_topic = topic
                stale_batches = 0
                if fresh_ratio >= 0.75:
                    low_yield_batches = 0
                    current_batch_size = min(self.batch_size, current_batch_size + 10)
                else:
                    low_yield_batches += 1
                self.word_batch.emit(accepted_words)
            else:
                stale_batches += 1
                low_yield_batches += 1

            if fresh_ratio < 0.55:
                current_batch_size = max(15, min(current_batch_size - 10, remaining))
            elif fresh_ratio < 0.75:
                current_batch_size = max(20, min(current_batch_size - 5, remaining))
            else:
                current_batch_size = min(self.batch_size, max(current_batch_size, min(remaining, self.batch_size)))

            batch_num += 1

            if len(all_words) >= self.min_acceptable and stale_batches >= 2:
                break
            if len(all_words) >= self.min_acceptable and low_yield_batches >= 3:
                break
            if stale_batches >= max(4, len(self.topics)):
                break
            if low_yield_batches >= max(5, len(self.topics) + 1):
                break

        self.finished.emit(all_words[:self.total])

    def _pick_topic(self, batch_num: int, remaining: int, last_success_topic: str) -> str:
        if not self.topics:
            return "general english"
        if len(self.topics) == 1:
            return self.topics[0]
        if remaining <= max(10, self.batch_size // 2):
            return last_success_topic or self.topics[0]
        return self.topics[batch_num % len(self.topics)]

    def _topic_instruction(self, topic: str) -> str:
        lowered = topic.lower()
        if self.build_mode == "Clinical MCQ Pack":
            return (
                "Focus on exam-style clinical study terms. Prefer high-yield concepts, short definitions, test-friendly distractor-resistant wording, "
                "and concise study notes that work well in MCQ review."
            )
        if self.build_mode == "Medical Study Pack":
            return (
                "Focus on academic medical study terms. Prefer core structures, processes, organisms, mechanisms, and concise learning notes. "
                "Vietnamese meanings may be short definitions or study-friendly explanations."
            )
        if any(keyword in lowered for keyword in ACADEMIC_KEYWORDS):
            return (
                "Focus on high-yield academic study terms. Prefer core concepts, structures, processes, organisms, or clinical terms. "
                "Vietnamese meanings may be short definitions or study-friendly explanations. Example sentences can be short learning statements."
            )
        return (
            "Focus on practical English vocabulary for Vietnamese learners. Prefer useful words, collocations, and short natural examples."
        )

    def _make_prompt(self, topic: str, count: int, avoid_words: list[str]) -> str:
        avoid_block = ""
        if avoid_words:
            avoid_block = "\nDo not return any of these words: " + ", ".join(avoid_words) + "."
        topic_instruction = self._topic_instruction(topic)
        schema = '"word":"...", "ipa":"/.../", "pos":"noun|verb|adj|adv", "vi":"nghia tieng Viet", "sentence":"Example sentence."'
        if self.build_mode in {"Medical Study Pack", "Clinical MCQ Pack"} or any(keyword in topic.lower() for keyword in ACADEMIC_KEYWORDS):
            schema = (
                '"word":"...", "ipa":"/.../", "pos":"noun|verb|adj|adv", "vi":"nghia tieng Viet", '
                '"definition":"short English definition", "study_note":"short study note", '
                '"memory_hint":"quick memory hook", "difficulty":"easy|medium|hard", "sentence":"short study sentence."'
            )
        return f"""Generate up to {count} unique {self.level}-level English vocabulary words about "{topic}".
For Vietnamese learners. Return ONLY a raw JSON array, no markdown, no explanation:
 
 [
   {{{schema}}},
   ...
 ]
 
 Rules: prefer {count} entries if possible, but return fewer entries instead of repeating words.
 Rules: no duplicates, no plural/singular duplicates, no tense variants, no simple derivations of excluded words, no near-synonym restatements of the same headword.
 Rules: {self.level} CEFR level, accurate Vietnamese meanings, natural example sentences.
 {topic_instruction}{avoid_block}
 Start array with [ and end with ]"""



# ── Parse helper ─────────────────────────────────────────────────────────────

def _parse_vocab(raw: str) -> list[dict]:
    raw = re.sub(r"```(?:json)?\s*", "", raw, flags=re.IGNORECASE).strip().rstrip("`").strip()
    candidates = [raw]
    start, end = raw.find("["), raw.rfind("]")
    if start != -1 and end > start:
        candidates.append(raw[start:end + 1])
    obj_start, obj_end = raw.find("{"), raw.rfind("}")
    if obj_start != -1 and obj_end > obj_start:
        candidates.append(raw[obj_start:obj_end + 1])

    data = None
    for candidate in candidates:
        normalized = re.sub(r",\s*([\]}])", r"\1", candidate)
        try:
            parsed = json.loads(normalized)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            parsed = (
                parsed.get("words")
                or parsed.get("items")
                or parsed.get("vocabulary")
                or parsed.get("data")
                or parsed.get("results")
            )
        if isinstance(parsed, list):
            data = parsed
            break
    if data is None:
        return []
    result = []
    for item in data:
        if not isinstance(item, dict):
            continue
        word = (item.get("word") or item.get("Word") or
                item.get("english") or item.get("term") or "").strip()
        if not word:
            continue
        result.append({
            "word":     word,
            "ipa":      item.get("ipa") or item.get("IPA") or item.get("pronunciation") or "",
            "pos":      item.get("pos") or item.get("type") or item.get("part_of_speech") or "",
            "vi":       (item.get("vi") or item.get("vietnamese") or
                         item.get("meaning") or item.get("definition") or ""),
            "sentence": (item.get("sentence") or item.get("example") or
                         item.get("example_sentence") or ""),
            "definition": item.get("definition") or item.get("meaning_en") or "",
            "study_note": item.get("study_note") or item.get("note") or item.get("clinical_note") or "",
            "memory_hint": item.get("memory_hint") or item.get("memoryTip") or item.get("hint") or "",
            "difficulty": item.get("difficulty") or "",
        })
    return result


def _parse_vocab_list(data: list) -> list[dict]:
    """Chuẩn hóa list các word dict từ nhiều format khác nhau."""
    result = []
    for item in data:
        if not isinstance(item, dict):
            continue
        word = (
            item.get("word") or item.get("Word") or
            item.get("english") or item.get("English") or
            item.get("term") or ""
        ).strip()
        if not word:
            continue
        result.append({
            "word":     word,
            "ipa":      item.get("ipa") or item.get("IPA") or item.get("phonetic") or item.get("pronunciation") or "",
            "pos":      item.get("pos") or item.get("POS") or item.get("type") or item.get("part_of_speech") or "",
            "vi":       (item.get("vi") or item.get("vietnamese") or item.get("Vietnamese") or
                         item.get("meaning") or item.get("definition") or ""),
            "sentence": (item.get("sentence") or item.get("example") or
                         item.get("example_sentence") or item.get("Example") or ""),
            "definition": item.get("definition") or item.get("meaning_en") or "",
            "study_note": item.get("study_note") or item.get("note") or item.get("clinical_note") or "",
            "memory_hint": item.get("memory_hint") or item.get("memoryTip") or item.get("hint") or "",
            "difficulty": item.get("difficulty") or item.get("level") or "",
        })
    return result


# ── UI ────────────────────────────────────────────────────────────────────────

BG_CARD   = "#1e2130"
BG_MAIN   = "#0f1117"
ACCENT    = "#5b6af0"
TEXT_MAIN = "#e8eaf0"
TEXT_DIM  = "#8892a4"
BORDER    = "#2a2f42"
ACCENT2   = "#3dd68c"


def _card(parent=None) -> QFrame:
    f = QFrame(parent)
    f.setObjectName("card")
    f.setStyleSheet(f"QFrame#card {{ background:{BG_CARD}; border:1.5px solid {BORDER}; border-radius:12px; }}")
    return f


class VocabBuilderWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: VocabGenWorker | None = None
        self._all_words: list[dict] = []
        self._build_ui()
        self._ai_timer = QTimer(self)
        self._ai_timer.timeout.connect(self._refresh_ai_buttons)
        self._ai_timer.start(1500)
        self._refresh_ai_buttons()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.setSpacing(20)

        # ── Header ────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        title = QLabel("Vocabulary Builder")
        title.setObjectName("title")
        title.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        hdr.addWidget(title)
        hdr.addStretch()
        sub = QLabel("Generate vocabulary lists using Gemini Web AI")
        sub.setObjectName("subtitle")
        sub.setFont(QFont("Segoe UI", 12))
        sub.setStyleSheet(f"color:{TEXT_DIM};")
        outer.addLayout(hdr)
        outer.addWidget(sub)
        preset_hint = QLabel("Supports custom study topics such as anatomy, physiology, microbiology, pathology, pharmacology, and other Gemini-assisted subject packs.")
        preset_hint.setWordWrap(True)
        preset_hint.setStyleSheet(f"color:{TEXT_DIM}; font-size:12px;")
        outer.addWidget(preset_hint)
        mode_hint = QLabel("Use General English for everyday vocabulary, Medical Study Pack for theory terms, and Clinical MCQ Pack for test-style review sets.")
        mode_hint.setWordWrap(True)
        mode_hint.setStyleSheet(f"color:{TEXT_DIM}; font-size:12px;")
        outer.addWidget(mode_hint)

        preset_card = _card()
        preset_lay = QVBoxLayout(preset_card)
        preset_lay.setContentsMargins(20, 16, 20, 16)
        preset_lay.setSpacing(10)
        preset_title = QLabel("Study Pack Presets")
        preset_title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        preset_lay.addWidget(preset_title)
        preset_note = QLabel("Quick presets fill topic, study mode, level, target, and batch size for common medical review packs.")
        preset_note.setWordWrap(True)
        preset_note.setStyleSheet(f"color:{TEXT_DIM}; font-size:12px;")
        preset_lay.addWidget(preset_note)
        preset_grid = QGridLayout()
        preset_grid.setHorizontalSpacing(10)
        preset_grid.setVerticalSpacing(10)
        self._preset_buttons = []
        for idx, preset in enumerate(STUDY_PACK_PRESETS):
            btn = QPushButton(preset["label"])
            btn.setFixedHeight(38)
            btn.clicked.connect(lambda _, p=preset: self._apply_preset(p))
            preset_grid.addWidget(btn, idx // 3, idx % 3)
            self._preset_buttons.append(btn)
        preset_lay.addLayout(preset_grid)
        outer.addWidget(preset_card)

        # ── Config card ───────────────────────────────────────────────
        cfg_card = _card()
        cfg_lay  = QVBoxLayout(cfg_card)
        cfg_lay.setContentsMargins(20, 16, 20, 16)
        cfg_lay.setSpacing(14)

        cfg_title = QLabel("Configuration")
        cfg_title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        cfg_lay.addWidget(cfg_title)

        row1 = QHBoxLayout()
        row1.setSpacing(16)

        # Level
        lvl_col = QVBoxLayout()
        lvl_col.addWidget(QLabel("CEFR Level"))
        self.level_combo = QComboBox()
        self.level_combo.addItems(LEVELS)
        self.level_combo.setCurrentText("B1")
        self.level_combo.setFixedWidth(120)
        lvl_col.addWidget(self.level_combo)
        row1.addLayout(lvl_col)

        # Total words
        cnt_col = QVBoxLayout()
        cnt_col.addWidget(QLabel("Number of words"))
        self.count_spin = QSpinBox()
        self.count_spin.setRange(10, 5000)
        self.count_spin.setValue(100)
        self.count_spin.setSingleStep(50)
        self.count_spin.setFixedWidth(130)
        self.count_spin.setStyleSheet(f"""
            QSpinBox {{ background:{BG_MAIN}; color:{TEXT_MAIN};
                border:1.5px solid {BORDER}; border-radius:8px;
                padding:8px 12px; font-size:13px; }}
            QSpinBox::up-button, QSpinBox::down-button {{ width:22px; }}
        """)
        cnt_col.addWidget(self.count_spin)
        row1.addLayout(cnt_col)

        # Batch size
        batch_col = QVBoxLayout()
        batch_col.addWidget(QLabel("Batch size (words/call)"))
        self.batch_spin = QSpinBox()
        self.batch_spin.setRange(20, 150)
        self.batch_spin.setValue(80)
        self.batch_spin.setSingleStep(10)
        self.batch_spin.setFixedWidth(150)
        self.batch_spin.setStyleSheet(self.count_spin.styleSheet())
        batch_col.addWidget(self.batch_spin)
        row1.addLayout(batch_col)

        # Output format
        fmt_col = QVBoxLayout()
        fmt_col.addWidget(QLabel("Output format"))
        self.fmt_combo = QComboBox()
        self.fmt_combo.addItems(["JSON", "CSV", "Markdown"])
        self.fmt_combo.setFixedWidth(130)
        fmt_col.addWidget(self.fmt_combo)
        row1.addLayout(fmt_col)

        mode_col = QVBoxLayout()
        mode_col.addWidget(QLabel("Study pack mode"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(BUILD_MODES)
        self.mode_combo.setFixedWidth(190)
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        mode_col.addWidget(self.mode_combo)
        row1.addLayout(mode_col)

        row1.addStretch()
        cfg_lay.addLayout(row1)

        # Topics
        row2 = QVBoxLayout()
        row2.setSpacing(6)
        row2_h = QHBoxLayout()
        row2_h.addWidget(QLabel("Topic (used for both generation and saving)"))
        self.all_topics_cb = QCheckBox("All topics")
        self.all_topics_cb.setChecked(True)
        self.all_topics_cb.toggled.connect(self._toggle_topics)
        row2_h.addWidget(self.all_topics_cb)
        row2_h.addStretch()
        row2.addLayout(row2_h)

        self.topic_input = QComboBox()
        self.topic_input.setEditable(True)
        self.topic_input.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.topic_input.setMinimumWidth(320)
        self.topic_input.lineEdit().setPlaceholderText("Choose a topic or type a new one")
        self.topic_input.setEnabled(False)
        row2.addWidget(self.topic_input)
        topic_note = QLabel("Custom topics are allowed. Gemini Web can build flashcard and quiz material for medical and academic subjects too.")
        topic_note.setWordWrap(True)
        topic_note.setStyleSheet(f"color:{TEXT_DIM}; font-size:12px;")
        row2.addWidget(topic_note)
        cfg_lay.addLayout(row2)

        save_row = QHBoxLayout()
        save_row.setSpacing(16)

        save_topic_col = QVBoxLayout()
        save_topic_col.addWidget(QLabel("Topic sync"))
        self.save_topic_input = self.topic_input
        self.save_topic_note = QLabel(
            "The Topic field above is also used when saving. If All topics is enabled, each generated word keeps its own source topic."
        )
        self.save_topic_note.setWordWrap(True)
        self.save_topic_note.setStyleSheet(f"color:{TEXT_DIM}; font-size:12px;")
        save_topic_col.addWidget(self.save_topic_note)
        save_row.addLayout(save_topic_col, 2)

        daily_new_col = QVBoxLayout()
        daily_new_col.addWidget(QLabel("Daily new words"))
        self.daily_new_spin = QSpinBox()
        self.daily_new_spin.setRange(5, 100)
        self.daily_new_spin.setValue(10)
        self.daily_new_spin.setFixedWidth(130)
        self.daily_new_spin.setStyleSheet(self.count_spin.styleSheet())
        daily_new_col.addWidget(self.daily_new_spin)
        save_row.addLayout(daily_new_col)

        daily_review_col = QVBoxLayout()
        daily_review_col.addWidget(QLabel("Daily reviews"))
        self.daily_review_spin = QSpinBox()
        self.daily_review_spin.setRange(5, 200)
        self.daily_review_spin.setValue(15)
        self.daily_review_spin.setFixedWidth(130)
        self.daily_review_spin.setStyleSheet(self.count_spin.styleSheet())
        daily_review_col.addWidget(self.daily_review_spin)
        save_row.addLayout(daily_review_col)
        save_row.addStretch()
        cfg_lay.addLayout(save_row)

        outer.addWidget(cfg_card)

        # ── Control buttons ───────────────────────────────────────────
        ctrl = QHBoxLayout()
        ctrl.setSpacing(12)

        self.start_btn = QPushButton("Start Build")
        self.start_btn.setObjectName("btnPrimary")
        self.start_btn.setFixedHeight(44)
        self.start_btn.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.start_btn.clicked.connect(self._start)
        ctrl.addWidget(self.start_btn)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setObjectName("btnDanger")
        self.stop_btn.setFixedHeight(44)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop)
        ctrl.addWidget(self.stop_btn)

        self.save_btn = QPushButton("Save File")
        self.save_btn.setFixedHeight(44)
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self._save)
        ctrl.addWidget(self.save_btn)

        self.import_btn = QPushButton("Import JSON")
        self.import_btn.setFixedHeight(44)
        self.import_btn.clicked.connect(self._import)
        ctrl.addWidget(self.import_btn)

        self.save_db_btn = QPushButton("Save to Vocabulary")
        self.save_db_btn.setObjectName("btnSuccess")
        self.save_db_btn.setFixedHeight(44)
        self.save_db_btn.setEnabled(False)
        self.save_db_btn.setToolTip("Lưu tất cả từ hiện tại vào Vocabulary để dùng trong Flashcard & Quiz")
        self.save_db_btn.clicked.connect(self._save_to_db)
        ctrl.addWidget(self.save_db_btn)

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setFixedHeight(44)
        self.clear_btn.clicked.connect(self._clear)
        ctrl.addWidget(self.clear_btn)

        ctrl.addStretch()

        self.word_count_lbl = QLabel("0 words")
        self.word_count_lbl.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.word_count_lbl.setStyleSheet(f"color:{ACCENT2};")
        ctrl.addWidget(self.word_count_lbl)

        outer.addLayout(ctrl)

        # ── Progress ──────────────────────────────────────────────────
        prog_card = _card()
        prog_lay  = QVBoxLayout(prog_card)
        prog_lay.setContentsMargins(16, 12, 16, 12)
        prog_lay.setSpacing(6)

        self.status_lbl = QLabel("Ready to build a vocabulary set.")
        self.status_lbl.setStyleSheet(f"color:{TEXT_DIM}; font-size:12px;")
        prog_lay.addWidget(self.status_lbl)
        self.progress_hint_lbl = QLabel("Large targets are collected over multiple Gemini Web calls, then merged into one deduplicated list.")
        self.progress_hint_lbl.setWordWrap(True)
        self.progress_hint_lbl.setStyleSheet(f"color:{TEXT_DIM}; font-size:12px;")
        prog_lay.addWidget(self.progress_hint_lbl)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFixedHeight(10)
        prog_lay.addWidget(self.progress_bar)

        outer.addWidget(prog_card)

        # ── Word table ────────────────────────────────────────────────
        tbl_label = QLabel("Generated Words")
        tbl_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        outer.addWidget(tbl_label)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Word", "IPA", "POS", "Vietnamese", "Example Sentence"])
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.setFont(QFont("Segoe UI", 12))
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background: {BG_CARD}; border: 1.5px solid {BORDER};
                border-radius: 10px; gridline-color: {BORDER};
                font-size: 13px;
            }}
            QTableWidget::item {{ padding: 6px 10px; color: {TEXT_MAIN}; }}
            QTableWidget::item:alternate {{ background: #191c28; }}
            QTableWidget::item:selected {{ background: {ACCENT}33; color: white; }}
            QHeaderView::section {{
                background: #13151f; color: {TEXT_DIM};
                border: none; border-bottom: 1.5px solid {BORDER};
                padding: 8px 10px; font-size: 12px; font-weight: 600;
            }}
        """)
        outer.addWidget(self.table, stretch=1)
        self._load_learning_settings()

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _toggle_topics(self, checked: bool):
        self.topic_input.setEnabled(not checked)

    def _apply_preset(self, preset: dict):
        self.all_topics_cb.setChecked(False)
        self.topic_input.setEnabled(True)
        self.topic_input.setEditText(preset["topic"])
        self.mode_combo.setCurrentText(preset["mode"])
        self.level_combo.setCurrentText(preset["level"])
        self.count_spin.setValue(preset["target"])
        self.batch_spin.setValue(preset["batch"])
        self.status_lbl.setText(
            f"Loaded preset: {preset['label']}  |  {preset['topic']}  |  {preset['mode']}"
        )
        self.status_lbl.setStyleSheet(f"color:{ACCENT}; font-size:12px; font-weight:600;")

    def _load_learning_settings(self):
        from src.english_learning_app.modules import database as db
        settings = db.get_vocab_learning_settings()
        self.daily_new_spin.setValue(settings.get("daily_new_words", 10))
        self.daily_review_spin.setValue(settings.get("daily_reviews", 15))
        mode = settings.get("build_mode", "General English")
        index = self.mode_combo.findText(mode)
        if index >= 0:
            self.mode_combo.setCurrentIndex(index)
        self._refresh_save_topics(settings.get("default_topic", ""))

    def _topics_for_mode(self, mode: str | None = None) -> list[str]:
        current_mode = mode or self.mode_combo.currentText()
        if current_mode == "General English":
            return GENERAL_ENGLISH_TOPICS
        return SPECIALIZED_TOPICS

    def _on_mode_changed(self, mode: str):
        self._refresh_save_topics(self.topic_input.currentText().strip())

    def _default_topic_for_mode(self, mode: str | None = None) -> str:
        topics = self._topics_for_mode(mode)
        return topics[0] if topics else "general english"

    def _refresh_save_topics(self, current_topic: str = ""):
        from src.english_learning_app.modules import database as db

        mode_topics = self._topics_for_mode()
        saved_topics = [
            topic for topic in db.get_topics()
            if topic and topic != "All" and topic.lower() != "vocabulary builder"
        ]
        suggestions = list(dict.fromkeys(SAVE_TOPIC_SUGGESTIONS + mode_topics + saved_topics))
        topics = [topic for topic in suggestions if topic and topic != "All"]

        self.topic_input.blockSignals(True)
        self.topic_input.clear()
        self.topic_input.addItems(topics)
        self.topic_input.blockSignals(False)

        target = (current_topic or "").strip()
        if target:
            index = self.topic_input.findText(target)
            if index >= 0:
                self.topic_input.setCurrentIndex(index)
            else:
                self.topic_input.setEditText(target)
        elif topics:
            self.topic_input.setCurrentIndex(0)
        else:
            self.topic_input.setEditText(self._default_topic_for_mode())

    def _start(self):
        from src.english_learning_app.modules.ai_module import _use_web, get_web_job_status
        if not _use_web():
            QMessageBox.warning(
                self,
                "No AI",
                "Gemini Web is not connected.\n\nOpen the Gemini Web page and start the browser first.",
            )
            return

        busy_job = get_web_job_status()
        if busy_job:
            QMessageBox.information(
                self,
                "Gemini Web Busy",
                f"Gemini Web is still handling: {busy_job}\n\nCancel or wait for the current task before starting a new vocabulary build.",
            )
            return

        self._all_words.clear()
        self.table.setRowCount(0)
        self.save_btn.setEnabled(False)
        self.word_count_lbl.setText("0 words")

        level  = self.level_combo.currentText()
        total  = self.count_spin.value()
        batch  = self.batch_spin.value()
        build_mode = self.mode_combo.currentText()

        if self.all_topics_cb.isChecked():
            topics = self._topics_for_mode(build_mode)
        else:
            raw = self.topic_input.currentText().strip()
            topics = [raw] if raw else self._topics_for_mode(build_mode)

        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(0)

        self._worker = VocabGenWorker(level, total, topics, batch, build_mode=build_mode)
        self._worker.progress.connect(self._on_progress)
        self._worker.word_batch.connect(self._on_batch)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status_lbl.setText(f"Generating {total} {level} words in {build_mode} mode...")
        self.status_lbl.setStyleSheet(f"color:{ACCENT}; font-size:12px; font-weight:600;")

    def _stop(self):
        if self._worker:
            self._worker.stop()
        self.stop_btn.setEnabled(False)
        self.status_lbl.setText("Stopped by user")
        self.status_lbl.setStyleSheet(f"color:#f87171; font-size:12px;")

    def _on_progress(self, done: int, total: int, topic: str):
        self.progress_bar.setValue(done)
        self.status_lbl.setText(
            f"{done}/{total} words  |  Current topic: {topic}"
        )

    def _on_batch(self, words: list[dict]):
        self._all_words.extend(words)
        start_row = self.table.rowCount()
        self.table.setRowCount(start_row + len(words))
        for i, w in enumerate(words):
            row = start_row + i
            self.table.setItem(row, 0, QTableWidgetItem(w.get("word", "")))
            self.table.setItem(row, 1, QTableWidgetItem(w.get("ipa", "")))
            self.table.setItem(row, 2, QTableWidgetItem(w.get("pos", "")))
            self.table.setItem(row, 3, QTableWidgetItem(w.get("vi", "")))
            self.table.setItem(row, 4, QTableWidgetItem(w.get("sentence", "")))
        self.word_count_lbl.setText(f"{len(self._all_words)} words")
        # Scroll to bottom
        self.table.scrollToBottom()

    def _on_finished(self, words: list[dict]):
        self._all_words = words
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.save_btn.setEnabled(bool(words))
        self.save_db_btn.setEnabled(bool(words))
        self.progress_bar.setValue(len(words))
        if self._worker and len(words) < self._worker.total and len(words) >= self._worker.min_acceptable:
            self.status_lbl.setText(
                f"Acceptable result reached: {len(words)}/{self._worker.total} words."
            )
        else:
            self.status_lbl.setText(
                f"Done. Generated {len(words)} unique words."
            )
        self.status_lbl.setStyleSheet(f"color:{ACCENT2}; font-size:12px; font-weight:600;")
        self.word_count_lbl.setText(f"{len(words)} words")
        self._refresh_ai_buttons()

    def _on_error(self, msg: str):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_lbl.setText(f"Error: {msg}")
        self.status_lbl.setStyleSheet("color:#f87171; font-size:12px;")
        QMessageBox.critical(self, "Error", msg)
        self._refresh_ai_buttons()

    def _refresh_ai_buttons(self):
        from src.english_learning_app.modules.ai_module import get_web_job_status

        busy_job = get_web_job_status()
        running = bool(self._worker and self._worker.isRunning())
        self.start_btn.setEnabled(not running and not busy_job)
        if busy_job and not running:
            self.start_btn.setToolTip(f"Gemini Web is busy: {busy_job}")
            if self.status_lbl.text().startswith("Ready") or self.status_lbl.text().startswith("Done.") or self.status_lbl.text().startswith("Acceptable"):
                self.status_lbl.setText(f"Gemini Web is busy: {busy_job}")
                self.status_lbl.setStyleSheet("color:#f59e0b; font-size:12px; font-weight:600;")
        else:
            self.start_btn.setToolTip("")

    def _save(self):
        if not self._all_words:
            return
        fmt = self.fmt_combo.currentText().lower()
        ext = {"json": "*.json", "csv": "*.csv", "markdown": "*.md"}[fmt]
        level = self.level_combo.currentText()
        default_name = f"vocab_{level.lower()}_{len(self._all_words)}"

        path, _ = QFileDialog.getSaveFileName(
            self, "Save Vocabulary List",
            str(Path.home() / "Downloads" / default_name),
            f"{fmt.upper()} Files ({ext});;All Files (*)"
        )
        if not path:
            return

        if fmt == "json":
            text = json.dumps(self._all_words, ensure_ascii=False, indent=2)
        elif fmt == "csv":
            lines = ["word,ipa,pos,vietnamese,example_sentence"]
            for w in self._all_words:
                def esc(s): return f'"{str(s).replace(chr(34), chr(34)*2)}"'
                lines.append(",".join(esc(w.get(k,"")) for k in ["word","ipa","pos","vi","sentence"]))
            text = "\n".join(lines)
        else:  # markdown
            lines = ["| # | Word | IPA | POS | Vietnamese | Example |",
                     "|---|------|-----|-----|------------|---------|"]
            for i, w in enumerate(self._all_words, 1):
                lines.append(f"| {i} | {w.get('word','')} | {w.get('ipa','')} | "
                              f"{w.get('pos','')} | {w.get('vi','')} | {w.get('sentence','')} |")
            text = "\n".join(lines)

        Path(path).write_text(text, encoding="utf-8")
        QMessageBox.information(self, "Saved",
            f"✅ Saved {len(self._all_words)} words to:\n{path}")

    def _import(self):
        """Import từ JSON — hỗ trợ nhiều format: array thẳng, {items:[...]}, {words:[...]}, CSV."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Vocabulary",
            str(Path.home() / "Downloads"),
            "JSON Files (*.json);;CSV Files (*.csv);;All Files (*)"
        )
        if not path:
            return

        try:
            file_path = Path(path)
            suffix = file_path.suffix.lower()

            if suffix == ".csv":
                words = self._parse_csv(file_path)
            else:
                words = self._parse_json_file(file_path)

            if not words:
                QMessageBox.warning(self, "No Data",
                    "Không tìm thấy từ vựng hợp lệ trong file.\n\n"
                    "File JSON phải là array [{word, ipa, pos, vi, sentence}]\n"
                    "hoặc object có key 'items'/'words'/'vocabulary'.\n"
                    "File CSV phải có header: word,ipa,pos,vietnamese,example_sentence")
                return

            # Dedup với danh sách hiện tại
            existing = {w["word"].lower() for w in self._all_words}
            new_words = [w for w in words if w["word"].lower() not in existing]
            dupes = len(words) - len(new_words)

            if not new_words:
                QMessageBox.information(self, "All Duplicates",
                    f"Tất cả {len(words)} từ đã có trong danh sách hiện tại.")
                return

            # Thêm vào bảng
            self._on_batch(new_words)
            self.save_btn.setEnabled(True)
            self.save_db_btn.setEnabled(True)
            self.progress_bar.setMaximum(max(self.progress_bar.maximum(), len(self._all_words)))
            self.progress_bar.setValue(len(self._all_words))

            msg = f"✅ Imported {len(new_words)} words from {file_path.name}"
            if dupes:
                msg += f"  ({dupes} duplicates skipped)"
            self.status_lbl.setText(msg)
            self.status_lbl.setStyleSheet(f"color:{ACCENT2}; font-size:12px; font-weight:600;")

        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Lỗi đọc file:\n{e}")

    def _parse_json_file(self, file_path: Path) -> list[dict]:
        """Parse JSON với nhiều cấu trúc khác nhau."""
        raw = file_path.read_text(encoding="utf-8")
        data = json.loads(raw)

        # Unwrap object nếu cần
        if isinstance(data, dict):
            # Thử các key phổ biến
            for key in ("items", "words", "vocabulary", "data", "vocab"):
                if key in data and isinstance(data[key], list):
                    data = data[key]
                    break
            else:
                # Nếu không tìm được key, lấy value đầu tiên là list
                for v in data.values():
                    if isinstance(v, list):
                        data = v
                        break
                else:
                    data = [data]  # wrap thành list 1 item

        if not isinstance(data, list):
            return []

        return _parse_vocab_list(data)

    def _parse_csv(self, file_path: Path) -> list[dict]:
        """Parse CSV — hỗ trợ header: word,ipa,pos,vietnamese,example_sentence."""
        import csv
        results = []
        text = file_path.read_text(encoding="utf-8-sig")  # utf-8-sig để bỏ BOM
        reader = csv.DictReader(text.splitlines())

        # Map các tên cột có thể khác nhau
        col_map = {
            "word":     ["word", "Word", "english", "English", "term"],
            "ipa":      ["ipa", "IPA", "phonetic", "pronunciation"],
            "pos":      ["pos", "POS", "type", "part_of_speech"],
            "vi":       ["vi", "vietnamese", "Vietnamese", "meaning", "definition"],
            "sentence": ["sentence", "example", "example_sentence", "Example"],
        }

        def find_col(row, candidates):
            for c in candidates:
                if c in row:
                    return row[c]
            return ""

        for row in reader:
            word = find_col(row, col_map["word"]).strip()
            if not word:
                continue
            results.append({
                "word":     word,
                "ipa":      find_col(row, col_map["ipa"]),
                "pos":      find_col(row, col_map["pos"]),
                "vi":       find_col(row, col_map["vi"]),
                "sentence": find_col(row, col_map["sentence"]),
                "definition": find_col(row, ["definition", "meaning_en", "english_definition"]),
                "study_note": find_col(row, ["study_note", "note", "clinical_note"]),
                "memory_hint": find_col(row, ["memory_hint", "hint", "memory_tip"]),
                "difficulty": find_col(row, ["difficulty", "Difficulty"]),
            })
        return results

    def _save_to_db(self):
        """Lưu tất cả words hiện tại vào SQLite vocabulary DB."""
        if not self._all_words:
            return
        from src.english_learning_app.modules import database as db

        # Lấy danh sách từ đã có trong DB để dedup
        db.save_vocab_learning_settings(
            {
                "default_topic": self.topic_input.currentText().strip() or self._default_topic_for_mode(),
                "daily_new_words": self.daily_new_spin.value(),
                "daily_reviews": self.daily_review_spin.value(),
                "build_mode": self.mode_combo.currentText(),
            }
        )
        conn = db.get_connection()
        c = conn.cursor()
        c.execute("SELECT LOWER(word) FROM vocabulary")
        existing = {row[0] for row in c.fetchall()}
        conn.close()

        added = 0
        skipped = 0
        for w in self._all_words:
            word = w.get("word", "").strip()
            if not word or word.lower() in existing:
                skipped += 1
                continue
            db.add_word(
                word=word,
                meaning_vi=w.get("vi", ""),
                example=w.get("sentence", ""),
                topic=w.get("topic") or self.topic_input.currentText().strip() or self._default_topic_for_mode(),
                phonetic=w.get("ipa", ""),
                part_of_speech=w.get("pos", ""),
                level=self.level_combo.currentText(),
                meaning_en=w.get("definition", ""),
                study_note=w.get("study_note", ""),
                memory_hint=w.get("memory_hint", ""),
            )
            existing.add(word.lower())
            added += 1

        db.update_today_progress(words_learned=added, xp_earned=added)
        self._refresh_save_topics(self.topic_input.currentText().strip() or self._default_topic_for_mode())
        msg = f"✅ Saved {added} new words to Vocabulary!"
        if skipped:
            msg += f"\n({skipped} duplicates skipped)"
        self.status_lbl.setText(msg)
        self.status_lbl.setStyleSheet(f"color:{ACCENT2}; font-size:12px; font-weight:600;")
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(self, "Saved to Vocabulary",
            f"{msg}\n\nGo to Vocabulary page to see your words in Flashcard & Quiz.")

    def _clear(self):
        self._all_words.clear()
        self.table.setRowCount(0)
        self.progress_bar.setValue(0)
        self.word_count_lbl.setText("0 words")
        self.save_btn.setEnabled(False)
        self.save_db_btn.setEnabled(False)
        self.status_lbl.setText("Cleared")
        self.status_lbl.setStyleSheet(f"color:{TEXT_DIM}; font-size:12px;")
