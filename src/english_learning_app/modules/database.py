"""Database module - SQLite for local storage"""
import sqlite3
import json
from pathlib import Path
from datetime import datetime, date, timedelta


APP_DATA_DIR = Path.home() / ".english_learning_app"
DB_PATH = APP_DATA_DIR / "data.db"
IMAGE_HISTORY_JSON = APP_DATA_DIR / "image_description_history.json"


def get_connection():
    APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize all database tables"""
    conn = get_connection()
    c = conn.cursor()

    # Vocabulary words table
    c.execute("""
        CREATE TABLE IF NOT EXISTS vocabulary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT NOT NULL,
            meaning_vi TEXT,
            meaning_en TEXT,
            example TEXT,
            study_note TEXT,
            memory_hint TEXT,
            topic TEXT,
            phonetic TEXT,
            part_of_speech TEXT,
            level TEXT DEFAULT 'B1',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Flashcard progress (Spaced Repetition)
    c.execute("""
        CREATE TABLE IF NOT EXISTS flashcard_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word_id INTEGER,
            ease_factor REAL DEFAULT 2.5,
            interval INTEGER DEFAULT 1,
            repetitions INTEGER DEFAULT 0,
            next_review TEXT,
            last_review TEXT,
            FOREIGN KEY(word_id) REFERENCES vocabulary(id)
        )
    """)
    c.execute(
        """
        DELETE FROM flashcard_progress
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM flashcard_progress
            GROUP BY word_id
        )
        """
    )
    c.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_flashcard_progress_word
        ON flashcard_progress (word_id)
    """)

    # Writing practice history
    c.execute("""
        CREATE TABLE IF NOT EXISTS writing_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT,
            content TEXT,
            feedback TEXT,
            score INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Listening practice history
    c.execute("""
        CREATE TABLE IF NOT EXISTS listening_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_text TEXT,
            user_answer TEXT,
            accuracy REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Daily progress tracking
    c.execute("""
        CREATE TABLE IF NOT EXISTS daily_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT UNIQUE,
            words_learned INTEGER DEFAULT 0,
            words_reviewed INTEGER DEFAULT 0,
            writing_sessions INTEGER DEFAULT 0,
            listening_sessions INTEGER DEFAULT 0,
            reading_sessions INTEGER DEFAULT 0,
            speaking_sessions INTEGER DEFAULT 0,
            grammar_sessions INTEGER DEFAULT 0,
            streak_days INTEGER DEFAULT 0,
            xp_earned INTEGER DEFAULT 0
        )
    """)

    # User settings
    c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    # Reading comprehension history
    c.execute("""
        CREATE TABLE IF NOT EXISTS reading_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            passage TEXT,
            topic TEXT,
            questions TEXT,
            answers TEXT,
            score INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Grammar exercises
    c.execute("""
        CREATE TABLE IF NOT EXISTS grammar_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exercise_type TEXT,
            question TEXT,
            user_answer TEXT,
            correct_answer TEXT,
            explanation TEXT,
            is_correct INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS grammar_library (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            grammar_point TEXT,
            question TEXT,
            answer TEXT,
            explanation TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(grammar_point, question, answer)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS image_description_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            image_path TEXT,
            level TEXT DEFAULT 'B1',
            focus TEXT,
            ai_notes TEXT,
            user_description TEXT,
            feedback TEXT,
            score INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS speaking_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            level TEXT DEFAULT 'B1',
            topic_text TEXT,
            user_text TEXT,
            coach_feedback TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("PRAGMA table_info(daily_progress)")
    cols = {row[1] for row in c.fetchall()}
    if "speaking_sessions" not in cols:
        c.execute("ALTER TABLE daily_progress ADD COLUMN speaking_sessions INTEGER DEFAULT 0")
    c.execute("PRAGMA table_info(grammar_history)")
    grammar_cols = {row[1] for row in c.fetchall()}
    if "explanation" not in grammar_cols:
        c.execute("ALTER TABLE grammar_history ADD COLUMN explanation TEXT DEFAULT ''")
    c.execute("PRAGMA table_info(vocabulary)")
    vocab_cols = {row[1] for row in c.fetchall()}
    if "study_note" not in vocab_cols:
        c.execute("ALTER TABLE vocabulary ADD COLUMN study_note TEXT DEFAULT ''")
    if "memory_hint" not in vocab_cols:
        c.execute("ALTER TABLE vocabulary ADD COLUMN memory_hint TEXT DEFAULT ''")
    c.execute("DROP INDEX IF EXISTS idx_grammar_unique_question")

    conn.commit()
    conn.close()
    _seed_vocabulary()


def _seed_vocabulary():
    """Seed initial vocabulary if empty"""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM vocabulary")
    count = c.fetchone()[0]
    if count == 0:
        sample_words = [
            ("achieve", "đạt được", "To achieve a goal means to succeed in doing it.", "Achievement", "/əˈtʃiːv/", "verb", "B1"),
            ("adventure", "cuộc phiêu lưu", "She went on an adventure to Southeast Asia.", "Travel", "/ədˈventʃər/", "noun", "B1"),
            ("ambitious", "có tham vọng", "He is ambitious and works very hard.", "Character", "/æmˈbɪʃəs/", "adjective", "B1"),
            ("ancient", "cổ đại", "The ancient temple attracted many tourists.", "History", "/ˈeɪnʃənt/", "adjective", "B1"),
            ("benefit", "lợi ích", "Exercise has many health benefits.", "Health", "/ˈbenɪfɪt/", "noun", "B1"),
            ("challenge", "thách thức", "Learning English is a great challenge.", "Education", "/ˈtʃælɪndʒ/", "noun", "B1"),
            ("community", "cộng đồng", "We should help our local community.", "Society", "/kəˈmjuːnɪti/", "noun", "B1"),
            ("confident", "tự tin", "You should be confident in yourself.", "Character", "/ˈkɒnfɪdənt/", "adjective", "B1"),
            ("culture", "văn hóa", "Vietnamese culture is very rich.", "Culture", "/ˈkʌltʃər/", "noun", "B1"),
            ("determine", "quyết tâm", "She determined to pass the exam.", "Character", "/dɪˈtɜːmɪn/", "verb", "B1"),
            ("develop", "phát triển", "Reading helps develop your vocabulary.", "Education", "/dɪˈveləp/", "verb", "B1"),
            ("economy", "nền kinh tế", "The economy is growing rapidly.", "Economy", "/ɪˈkɒnəmi/", "noun", "B2"),
            ("environment", "môi trường", "We must protect our environment.", "Environment", "/ɪnˈvaɪrənmənt/", "noun", "B1"),
            ("experience", "kinh nghiệm", "Travel gives you new experiences.", "Travel", "/ɪkˈspɪəriəns/", "noun", "B1"),
            ("fluent", "thông thạo", "She speaks fluent English.", "Language", "/ˈfluːənt/", "adjective", "B1"),
            ("grateful", "biết ơn", "I am grateful for your help.", "Character", "/ˈɡreɪtfəl/", "adjective", "B1"),
            ("improve", "cải thiện", "Practice every day to improve your skills.", "Education", "/ɪmˈpruːv/", "verb", "B1"),
            ("opportunity", "cơ hội", "This job is a great opportunity.", "Work", "/ˌɒpəˈtjuːnɪti/", "noun", "B1"),
            ("traditional", "truyền thống", "Vietnam has many traditional festivals.", "Culture", "/trəˈdɪʃənəl/", "adjective", "B1"),
            ("vocabulary", "từ vựng", "Expanding vocabulary is essential for B1.", "Language", "/vəˈkæbjʊləri/", "noun", "B1"),
        ]
        for w in sample_words:
            c.execute("""
                INSERT INTO vocabulary (word, meaning_vi, example, topic, phonetic, part_of_speech, level)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (w[0], w[1], w[2], w[3], w[4], w[5], w[6]))
    conn.commit()
    conn.close()


def get_setting(key, default=None):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = c.fetchone()
    conn.close()
    return row["value"] if row else default


def get_json_setting(key: str, default=None):
    raw = get_setting(key)
    if raw is None:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


def reset_all_progress():
    """Xóa toàn bộ lịch sử tiến trình học (daily_progress, flashcard_progress).
    Không xóa từ vựng hay lịch sử bài đọc/viết."""
    from datetime import date as _date
    conn = get_connection()
    c = conn.cursor()
    # Xóa toàn bộ daily progress
    c.execute("DELETE FROM daily_progress")
    # Reset flashcard progress
    c.execute("DELETE FROM flashcard_progress")
    conn.commit()
    # Tạo lại row hôm nay với streak = 1
    today = _date.today().isoformat()
    c.execute("INSERT OR IGNORE INTO daily_progress (date, streak_days) VALUES (?, 1)", (today,))
    conn.commit()
    conn.close()




def set_setting(key, value):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()


def set_json_setting(key: str, value):
    set_setting(key, json.dumps(value, ensure_ascii=False))


def get_daily_plan_targets() -> dict:
    return get_json_setting(
        "daily_plan_targets",
        {
            "words": 10,
            "review": 15,
            "reading": 2,
            "listening": 2,
            "output": 2,
            "speaking": 1,
        },
    )


def get_vocab_learning_settings() -> dict:
    return get_json_setting(
        "vocab_learning_settings",
        {
            "daily_new_words": 10,
            "daily_reviews": 15,
            "default_topic": "Vocabulary Builder",
            "build_mode": "General English",
        },
    )


def save_vocab_learning_settings(settings: dict):
    current = get_vocab_learning_settings()
    current.update(settings)
    set_json_setting("vocab_learning_settings", current)


def get_today_progress():
    today = date.today().isoformat()
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM daily_progress WHERE date=?", (today,))
    row = c.fetchone()
    if not row:
        # calculate streak
        c.execute("SELECT streak_days FROM daily_progress ORDER BY date DESC LIMIT 1")
        prev = c.fetchone()
        streak = (prev["streak_days"] + 1) if prev else 1
        c.execute("""
            INSERT INTO daily_progress (date, streak_days) VALUES (?, ?)
        """, (today, streak))
        conn.commit()
        c.execute("SELECT * FROM daily_progress WHERE date=?", (today,))
        row = c.fetchone()
    conn.close()
    return dict(row)


def update_today_progress(**kwargs):
    today = date.today().isoformat()
    get_today_progress()  # ensure row exists
    conn = get_connection()
    c = conn.cursor()
    for key, val in kwargs.items():
        c.execute(f"UPDATE daily_progress SET {key} = {key} + ? WHERE date=?", (val, today))
    conn.commit()
    conn.close()


def _vocab_kind_condition(vocab_kind: str = "all") -> str:
    if vocab_kind == "study":
        return (
            "("
            "TRIM(COALESCE(meaning_en, '')) != '' OR "
            "TRIM(COALESCE(study_note, '')) != '' OR "
            "TRIM(COALESCE(memory_hint, '')) != ''"
            ")"
        )
    if vocab_kind == "general":
        return (
            "TRIM(COALESCE(meaning_en, '')) = '' AND "
            "TRIM(COALESCE(study_note, '')) = '' AND "
            "TRIM(COALESCE(memory_hint, '')) = ''"
        )
    return "1=1"


def get_words_by_topic(topic=None, limit=20, vocab_kind: str = "all"):
    conn = get_connection()
    c = conn.cursor()
    kind_condition = _vocab_kind_condition(vocab_kind)
    if topic and topic != "All":
        c.execute(
            f"SELECT * FROM vocabulary WHERE topic=? AND {kind_condition} ORDER BY RANDOM() LIMIT ?",
            (topic, limit),
        )
    else:
        c.execute(
            f"SELECT * FROM vocabulary WHERE {kind_condition} ORDER BY RANDOM() LIMIT ?",
            (limit,),
        )
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_topics(vocab_kind: str = "all"):
    conn = get_connection()
    c = conn.cursor()
    kind_condition = _vocab_kind_condition(vocab_kind)
    c.execute(
        f"SELECT DISTINCT topic FROM vocabulary WHERE {kind_condition} ORDER BY topic"
    )
    topics = ["All"] + [r["topic"] for r in c.fetchall()]
    conn.close()
    return topics


def get_vocab_stats():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT topic, COUNT(*) as count FROM vocabulary GROUP BY topic ORDER BY count DESC")
    rows = [{"topic": r["topic"], "count": r["count"]} for r in c.fetchall()]
    conn.close()
    return rows


def add_word(
    word,
    meaning_vi,
    example,
    topic,
    phonetic="",
    part_of_speech="noun",
    level="B1",
    meaning_en="",
    study_note="",
    memory_hint="",
):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT id FROM vocabulary
        WHERE LOWER(word) = LOWER(?) AND COALESCE(topic, '') = COALESCE(?, '')
        LIMIT 1
        """,
        (word.strip(), topic),
    )
    row = c.fetchone()
    if row:
        conn.close()
        return row["id"]
    c.execute("""
        INSERT INTO vocabulary (word, meaning_vi, meaning_en, example, study_note, memory_hint, topic, phonetic, part_of_speech, level)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (word, meaning_vi, meaning_en, example, study_note, memory_hint, topic, phonetic, part_of_speech, level))
    word_id = c.lastrowid
    conn.commit()
    conn.close()
    if word_id:
        init_flashcard_progress(word_id)
    return word_id


def init_flashcard_progress(word_id: int):
    today = date.today().isoformat()
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        INSERT OR IGNORE INTO flashcard_progress
            (word_id, ease_factor, interval, repetitions, next_review, last_review)
        VALUES (?, 2.5, 1, 0, ?, ?)
        """,
        (word_id, today, today),
    )
    conn.commit()
    conn.close()


def review_flashcard(word_id: int, correct: bool):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM flashcard_progress WHERE word_id=?", (word_id,))
    row = c.fetchone()
    if not row:
        init_flashcard_progress(word_id)
        c.execute("SELECT * FROM flashcard_progress WHERE word_id=?", (word_id,))
        row = c.fetchone()
    ease = float(row["ease_factor"])
    interval = int(row["interval"])
    repetitions = int(row["repetitions"])
    if correct:
        repetitions += 1
        interval = 1 if repetitions == 1 else 3 if repetitions == 2 else max(4, int(interval * ease))
        ease = min(3.0, ease + 0.05)
    else:
        repetitions = 0
        interval = 1
        ease = max(1.8, ease - 0.2)
    next_review = (date.today() + timedelta(days=interval)).isoformat()
    c.execute(
        """
        UPDATE flashcard_progress
        SET ease_factor=?, interval=?, repetitions=?, next_review=?, last_review=?
        WHERE word_id=?
        """,
        (ease, interval, repetitions, next_review, date.today().isoformat(), word_id),
    )
    conn.commit()
    conn.close()


def get_due_flashcards(topic: str = "All", limit: int | None = None, vocab_kind: str = "all") -> list[dict]:
    settings = get_vocab_learning_settings()
    limit = limit or settings.get("daily_reviews", 15)
    today = date.today().isoformat()
    conn = get_connection()
    c = conn.cursor()
    kind_condition = _vocab_kind_condition(vocab_kind)
    query = """
        SELECT v.*, fp.next_review, fp.repetitions
        FROM vocabulary v
        LEFT JOIN flashcard_progress fp ON fp.word_id = v.id
        WHERE (? = 'All' OR v.topic = ?)
          AND ({kind_condition})
          AND (fp.next_review IS NULL OR fp.next_review <= ?)
        ORDER BY COALESCE(fp.next_review, ''), v.created_at DESC
        LIMIT ?
    """.format(kind_condition=kind_condition)
    c.execute(query, (topic or "All", topic or "All", today, limit))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def save_writing(topic, content, feedback, score):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO writing_history (topic, content, feedback, score) VALUES (?, ?, ?, ?)",
              (topic, content, feedback, score))
    conn.commit()
    conn.close()
    update_today_progress(writing_sessions=1, xp_earned=10)


def save_listening(original, user_answer, accuracy):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO listening_history (original_text, user_answer, accuracy) VALUES (?, ?, ?)",
              (original, user_answer, accuracy))
    conn.commit()
    conn.close()
    update_today_progress(listening_sessions=1, xp_earned=5)


def save_speaking_session(level: str, topic_text: str, user_text: str, coach_feedback: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO speaking_history (level, topic_text, user_text, coach_feedback)
        VALUES (?, ?, ?, ?)
        """,
        (level, topic_text, user_text, coach_feedback),
    )
    conn.commit()
    conn.close()
    update_today_progress(speaking_sessions=1, xp_earned=6)


def get_weekly_stats():
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT date, words_learned, words_reviewed, writing_sessions,
               listening_sessions, reading_sessions, speaking_sessions, xp_earned, streak_days
        FROM daily_progress
        ORDER BY date DESC LIMIT 7
    """)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


# ─── Reading ──────────────────────────────────────────────────────────────────

def save_reading_item(passage: str, topic: str, questions: list, answers: list,
                      level: str = "B1", score: int = 0):
    """Lưu một reading passage vào DB."""
    import json as _json
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO reading_history (passage, topic, questions, answers, score)
        VALUES (?, ?, ?, ?, ?)
    """, (passage, topic,
          _json.dumps(questions, ensure_ascii=False),
          _json.dumps(answers, ensure_ascii=False),
          score))
    conn.commit()
    conn.close()
    update_today_progress(reading_sessions=1, xp_earned=5)


def get_reading_items(topic: str = None, limit: int = 50) -> list[dict]:
    """Lấy reading items từ DB."""
    import json as _json
    conn = get_connection()
    c = conn.cursor()
    if topic and topic != "All":
        c.execute("SELECT * FROM reading_history WHERE topic=? ORDER BY created_at DESC LIMIT ?",
                  (topic, limit))
    else:
        c.execute("SELECT * FROM reading_history ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d["questions"] = _json.loads(d.get("questions") or "[]")
            d["answers"]   = _json.loads(d.get("answers")   or "[]")
        except Exception:
            d["questions"] = []
            d["answers"]   = []
        result.append(d)
    return result


def get_reading_topics() -> list[str]:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT DISTINCT topic FROM reading_history ORDER BY topic")
    topics = ["All"] + [r["topic"] for r in c.fetchall() if r["topic"]]
    conn.close()
    return topics


# ─── Grammar ─────────────────────────────────────────────────────────────────

def save_grammar_set(grammar_point: str, exercises: list, level: str = "B1"):
    """Lưu một bộ grammar exercises vào DB."""
    conn = get_connection()
    c = conn.cursor()
    for ex in exercises:
        c.execute("""
            INSERT INTO grammar_history (exercise_type, question, correct_answer, user_answer, explanation, is_correct)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            grammar_point,
            ex.get("question", ""),
            ex.get("answer", ""),
            "",
            ex.get("explanation", ""),
            0,
        ))
    conn.commit()
    conn.close()
    update_today_progress(grammar_sessions=1, xp_earned=3)


def get_grammar_sets(grammar_point: str = None, limit: int = 100) -> list[dict]:
    """Lấy grammar exercises từ DB, group theo exercise_type."""
    conn = get_connection()
    c = conn.cursor()
    if grammar_point and grammar_point != "All":
        c.execute("""SELECT * FROM grammar_history WHERE exercise_type=?
                     ORDER BY created_at DESC LIMIT ?""", (grammar_point, limit))
    else:
        c.execute("SELECT * FROM grammar_history ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    # Group thành sets
    sets: dict[str, dict] = {}
    for r in rows:
        pt = r.get("exercise_type", "General")
        if pt not in sets:
            sets[pt] = {"grammar_point": pt, "exercises": [], "created_at": r.get("created_at", "")}
        sets[pt]["exercises"].append({
            "question":    r.get("question", ""),
            "answer":      r.get("correct_answer", ""),
            "explanation": r.get("explanation", ""),
        })
    return list(sets.values())


def get_grammar_points() -> list[str]:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT DISTINCT exercise_type FROM grammar_history ORDER BY exercise_type")
    pts = ["All"] + [r["exercise_type"] for r in c.fetchall() if r["exercise_type"]]
    conn.close()
    return pts


def save_grammar_library_set(grammar_point: str, exercises: list) -> int:
    conn = get_connection()
    c = conn.cursor()
    inserted = 0
    for ex in exercises:
        c.execute(
            """
            INSERT OR IGNORE INTO grammar_library (grammar_point, question, answer, explanation)
            VALUES (?, ?, ?, ?)
            """,
            (
                grammar_point,
                ex.get("question", ""),
                ex.get("answer", ""),
                ex.get("explanation", ""),
            ),
        )
        inserted += c.rowcount
    conn.commit()
    conn.close()
    return inserted


def save_grammar_attempt(
    grammar_point: str,
    question: str,
    user_answer: str,
    correct_answer: str,
    explanation: str = "",
    is_correct: bool = False,
):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO grammar_history
            (exercise_type, question, user_answer, correct_answer, explanation, is_correct)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (grammar_point, question, user_answer, correct_answer, explanation, int(is_correct)),
    )
    conn.commit()
    conn.close()


def get_grammar_library_sets(grammar_point: str = None, limit: int = 150) -> list[dict]:
    conn = get_connection()
    c = conn.cursor()
    if grammar_point and grammar_point != "All":
        c.execute(
            """
            SELECT * FROM grammar_library
            WHERE grammar_point=?
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (grammar_point, limit),
        )
    else:
        c.execute(
            "SELECT * FROM grammar_library ORDER BY created_at DESC, id DESC LIMIT ?",
            (limit,),
        )
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    grouped: dict[str, dict] = {}
    for row in rows:
        point = row.get("grammar_point") or "General"
        if point not in grouped:
            grouped[point] = {
                "grammar_point": point,
                "exercises": [],
                "created_at": row.get("created_at", ""),
            }
        grouped[point]["exercises"].append(
            {
                "question": row.get("question", ""),
                "answer": row.get("answer", ""),
                "explanation": row.get("explanation", ""),
            }
        )
    return list(grouped.values())


def get_grammar_library_count(grammar_point: str = None) -> int:
    conn = get_connection()
    c = conn.cursor()
    if grammar_point and grammar_point != "All":
        c.execute("SELECT COUNT(*) FROM grammar_library WHERE grammar_point=?", (grammar_point,))
    else:
        c.execute("SELECT COUNT(*) FROM grammar_library")
    count = c.fetchone()[0]
    conn.close()
    return int(count)


# ─── Writing Library ──────────────────────────────────────────────────────────

def save_writing_prompt(topic: str, prompt: str, guide: str = "",
                        vocabulary: list = None, level: str = "B1"):
    """Lưu writing prompt vào writing_history (content = prompt JSON)."""
    import json as _json
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT id FROM writing_history WHERE topic=? AND content LIKE ? AND score=-1 LIMIT 1",
        (topic, f"%{prompt[:80]}%"),
    )
    if c.fetchone():
        conn.close()
        return
    data = _json.dumps({
        "prompt": prompt, "guide": guide,
        "vocabulary": vocabulary or [], "level": level
    }, ensure_ascii=False)
    c.execute("INSERT INTO writing_history (topic, content, feedback, score) VALUES (?, ?, ?, ?)",
              (topic, data, "prompt", -1))
    conn.commit()
    conn.close()


def get_writing_prompts(limit: int = 50) -> list[dict]:
    """Lấy writing prompts (score=-1) từ DB."""
    import json as _json
    conn = get_connection()
    c = conn.cursor()
    c.execute("""SELECT * FROM writing_history WHERE score=-1
                 ORDER BY created_at DESC LIMIT ?""", (limit,))
    rows = c.fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        try:
            extra = _json.loads(d.get("content") or "{}")
            d.update(extra)
        except Exception:
            pass
        result.append(d)
    return result


# ─── Listening Library ────────────────────────────────────────────────────────

def save_listening_set(topic: str, sentences: list, level: str = "B1"):
    """Lưu một bộ listening sentences vào DB."""
    conn = get_connection()
    c = conn.cursor()
    for s in sentences:
        original = f"[{level}] [{topic}] {s}"
        c.execute(
            "SELECT id FROM listening_history WHERE original_text=? AND accuracy=-1 LIMIT 1",
            (original,),
        )
        if c.fetchone():
            continue
        c.execute(
            """INSERT INTO listening_history (original_text, user_answer, accuracy)
                     VALUES (?, ?, ?)""",
            (original, "", -1),
        )
    conn.commit()
    conn.close()


def get_listening_sets(topic: str = None, limit: int = 200) -> list[str]:
    """Lấy listening sentences từ DB (chưa luyện tập: accuracy=-1)."""
    import re as _re
    conn = get_connection()
    c = conn.cursor()
    c.execute("""SELECT original_text FROM listening_history
                 WHERE accuracy=-1 ORDER BY created_at DESC LIMIT ?""", (limit,))
    rows = c.fetchall()
    conn.close()
    sentences = []
    for r in rows:
        text = r["original_text"]
        if topic and topic != "All" and f"[{topic}]" not in text:
            continue
        # Bỏ prefix [level] [topic]
        clean = _re.sub(r'^\[.*?\]\s*\[.*?\]\s*', '', text).strip()
        if clean:
            sentences.append(clean)
    return sentences


# ─── DB Manager CRUD ─────────────────────────────────────────────────────────

def get_all_words(search: str = "", topic: str = "All", limit: int = 500) -> list[dict]:
    """Lấy tất cả từ vựng, hỗ trợ lọc và tìm kiếm."""
    conn = get_connection()
    c = conn.cursor()
    filters, params = [], []
    if search:
        filters.append("(word LIKE ? OR meaning_vi LIKE ? OR example LIKE ?)")
        params += [f"%{search}%", f"%{search}%", f"%{search}%"]
    if topic and topic != "All":
        filters.append("topic=?")
        params.append(topic)
    where = ("WHERE " + " AND ".join(filters)) if filters else ""
    params.append(limit)
    c.execute(f"SELECT * FROM vocabulary {where} ORDER BY word ASC LIMIT ?", params)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def update_word(word_id: int, **kwargs):
    """Cập nhật một từ vựng theo id."""
    if not kwargs:
        return
    conn = get_connection()
    c = conn.cursor()
    sets = ", ".join(f"{k}=?" for k in kwargs)
    params = list(kwargs.values()) + [word_id]
    c.execute(f"UPDATE vocabulary SET {sets} WHERE id=?", params)
    conn.commit()
    conn.close()


def delete_word(word_id: int):
    """Xóa một từ vựng và flashcard progress liên quan."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM flashcard_progress WHERE word_id=?", (word_id,))
    c.execute("DELETE FROM vocabulary WHERE id=?", (word_id,))
    conn.commit()
    conn.close()


def get_all_reading(search: str = "", limit: int = 200) -> list[dict]:
    """Lấy toàn bộ lịch sử bài đọc."""
    import json as _json
    conn = get_connection()
    c = conn.cursor()
    if search:
        c.execute("SELECT * FROM reading_history WHERE topic LIKE ? OR passage LIKE ? ORDER BY created_at DESC LIMIT ?",
                  (f"%{search}%", f"%{search}%", limit))
    else:
        c.execute("SELECT * FROM reading_history ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d["questions"] = _json.loads(d.get("questions") or "[]")
            d["answers"] = _json.loads(d.get("answers") or "[]")
        except Exception:
            d["questions"], d["answers"] = [], []
        result.append(d)
    return result


def delete_reading(reading_id: int):
    """Xóa một bài đọc."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM reading_history WHERE id=?", (reading_id,))
    conn.commit()
    conn.close()


def get_all_writing(search: str = "", limit: int = 200) -> list[dict]:
    """Lấy toàn bộ lịch sử bài viết."""
    conn = get_connection()
    c = conn.cursor()
    if search:
        c.execute(
            """
            SELECT * FROM writing_history
            WHERE score != -1 AND (topic LIKE ? OR content LIKE ?)
            ORDER BY created_at DESC LIMIT ?
            """,
            (f"%{search}%", f"%{search}%", limit),
        )
    else:
        c.execute(
            "SELECT * FROM writing_history WHERE score != -1 ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def delete_writing(writing_id: int):
    """Xóa một bài viết."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM writing_history WHERE id=?", (writing_id,))
    conn.commit()
    conn.close()


def get_all_grammar(search: str = "", limit: int = 300) -> list[dict]:
    """Lấy toàn bộ lịch sử luyện ngữ pháp."""
    conn = get_connection()
    c = conn.cursor()
    if search:
        c.execute("SELECT * FROM grammar_history WHERE exercise_type LIKE ? OR question LIKE ? ORDER BY created_at DESC LIMIT ?",
                  (f"%{search}%", f"%{search}%", limit))
    else:
        c.execute("SELECT * FROM grammar_history ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_all_grammar_library(search: str = "", limit: int = 300) -> list[dict]:
    conn = get_connection()
    c = conn.cursor()
    if search:
        c.execute(
            """
            SELECT * FROM grammar_library
            WHERE grammar_point LIKE ? OR question LIKE ? OR answer LIKE ? OR explanation LIKE ?
            ORDER BY created_at DESC, id DESC LIMIT ?
            """,
            (f"%{search}%", f"%{search}%", f"%{search}%", f"%{search}%", limit),
        )
    else:
        c.execute(
            "SELECT * FROM grammar_library ORDER BY created_at DESC, id DESC LIMIT ?",
            (limit,),
        )
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_all_listening(search: str = "", limit: int = 200) -> list[dict]:
    conn = get_connection()
    c = conn.cursor()
    if search:
        c.execute(
            """
            SELECT * FROM listening_history
            WHERE original_text LIKE ? OR user_answer LIKE ?
            ORDER BY created_at DESC LIMIT ?
            """,
            (f"%{search}%", f"%{search}%", limit),
        )
    else:
        c.execute("SELECT * FROM listening_history ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_all_speaking(search: str = "", limit: int = 200) -> list[dict]:
    conn = get_connection()
    c = conn.cursor()
    if search:
        c.execute(
            """
            SELECT * FROM speaking_history
            WHERE topic_text LIKE ? OR user_text LIKE ? OR coach_feedback LIKE ?
            ORDER BY created_at DESC LIMIT ?
            """,
            (f"%{search}%", f"%{search}%", f"%{search}%", limit),
        )
    else:
        c.execute("SELECT * FROM speaking_history ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def delete_grammar(grammar_id: int):
    """Xóa một bài ngữ pháp."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM grammar_history WHERE id=?", (grammar_id,))
    conn.commit()
    conn.close()


def delete_grammar_library(grammar_id: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM grammar_library WHERE id=?", (grammar_id,))
    conn.commit()
    conn.close()


def delete_listening(listening_id: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM listening_history WHERE id=?", (listening_id,))
    conn.commit()
    conn.close()


def delete_speaking(speaking_id: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM speaking_history WHERE id=?", (speaking_id,))
    conn.commit()
    conn.close()


def clear_practice_history():
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM daily_progress")
    c.execute("DELETE FROM flashcard_progress")
    c.execute("DELETE FROM reading_history")
    c.execute("DELETE FROM grammar_history")
    c.execute("DELETE FROM speaking_history")
    c.execute("DELETE FROM image_description_history")
    c.execute("DELETE FROM listening_history WHERE accuracy != -1")
    c.execute("DELETE FROM writing_history WHERE score != -1")
    conn.commit()
    conn.close()


def clear_library_data():
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM grammar_library")
    c.execute("DELETE FROM listening_history WHERE accuracy = -1")
    c.execute("DELETE FROM writing_history WHERE score = -1")
    c.execute("DELETE FROM flashcard_progress")
    c.execute("DELETE FROM vocabulary")
    conn.commit()
    conn.close()
    if IMAGE_HISTORY_JSON.exists():
        IMAGE_HISTORY_JSON.write_text("[]", encoding="utf-8")


def clear_all_learning_data(include_settings: bool = False):
    vocab_settings = None
    daily_targets = None
    if not include_settings:
        vocab_settings = get_json_setting("vocab_learning_settings")
        daily_targets = get_json_setting("daily_plan_targets")
    clear_practice_history()
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM grammar_library")
    c.execute("DELETE FROM listening_history")
    c.execute("DELETE FROM writing_history")
    c.execute("DELETE FROM vocabulary")
    c.execute("DELETE FROM flashcard_progress")
    if include_settings:
        c.execute("DELETE FROM settings")
    conn.commit()
    conn.close()
    if IMAGE_HISTORY_JSON.exists():
        IMAGE_HISTORY_JSON.write_text("[]", encoding="utf-8")
    if not include_settings:
        if vocab_settings is not None:
            set_json_setting("vocab_learning_settings", vocab_settings)
        if daily_targets is not None:
            set_json_setting("daily_plan_targets", daily_targets)


def save_image_description_session(
    image_path: str,
    level: str,
    focus: str,
    ai_notes: str,
    user_description: str,
    feedback: str,
    score: int = 0,
):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO image_description_history
            (image_path, level, focus, ai_notes, user_description, feedback, score)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (image_path, level, focus, ai_notes, user_description, feedback, score),
    )
    conn.commit()
    conn.close()
    append_image_description_json(
        {
            "image_path": image_path,
            "level": level,
            "focus": focus,
            "ai_notes": ai_notes,
            "user_description": user_description,
            "feedback": feedback,
            "score": score,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
    )
    update_today_progress(writing_sessions=1, xp_earned=8)


def append_image_description_json(item: dict):
    APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        records = json.loads(IMAGE_HISTORY_JSON.read_text(encoding="utf-8")) if IMAGE_HISTORY_JSON.exists() else []
    except Exception:
        records = []
    if not isinstance(records, list):
        records = []
    records.insert(0, item)
    IMAGE_HISTORY_JSON.write_text(
        json.dumps(records[:300], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_image_description_history(limit: int = 50) -> list[dict]:
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT * FROM image_description_history
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_all_image_descriptions(search: str = "", limit: int = 200) -> list[dict]:
    conn = get_connection()
    c = conn.cursor()
    if search:
        c.execute(
            """
            SELECT * FROM image_description_history
            WHERE image_path LIKE ? OR user_description LIKE ? OR feedback LIKE ?
            ORDER BY created_at DESC LIMIT ?
            """,
            (f"%{search}%", f"%{search}%", f"%{search}%", limit),
        )
    else:
        c.execute(
            "SELECT * FROM image_description_history ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def delete_image_description(item_id: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM image_description_history WHERE id=?", (item_id,))
    conn.commit()
    conn.close()

