"""
Gemini Web Bridge — gọi GeminiWebClient từ WebCrawlerGemini thay vì API key.
Tất cả các hàm AI trong ai_module giờ route qua Gemini Web (Chrome).
"""
from __future__ import annotations
import asyncio
import threading
import sys
from pathlib import Path

# Thêm path tới WebCrawlerGemini để import GeminiWebClient
_WEBCRAWLER_ROOT = Path(__file__).parent.parent.parent.parent.parent / "WebCrawlerGemini"
if str(_WEBCRAWLER_ROOT) not in sys.path:
    sys.path.insert(0, str(_WEBCRAWLER_ROOT))


# ── Singleton bridge ──────────────────────────────────────────────────────────

class GeminiWebBridge:
    """
    Singleton wrapper quanh GeminiWebClient.
    Dùng chung 1 instance Chrome cho toàn app.
    """
    _instance: "GeminiWebBridge | None" = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._client = None
            cls._instance._loop = None
            cls._instance._thread = None
            cls._instance._ready = False
        return cls._instance

    # ── lifecycle ────────────────────────────────────────────────────────────

    def set_client(self, client, loop):
        """Được gọi từ GeminiWebTab sau khi Chrome đã mở thành công."""
        self._client = client
        self._loop = loop
        self._ready = True

    def clear_client(self):
        """Được gọi khi browser đóng."""
        self._client = None
        self._loop = None
        self._ready = False

    @property
    def is_ready(self) -> bool:
        return self._ready and self._client is not None

    # ── core send ────────────────────────────────────────────────────────────

    def ask(self, prompt: str, timeout: int = 90) -> str:
        """
        Gửi prompt tới Gemini Web và trả về response (blocking).
        Ném RuntimeError nếu browser chưa mở hoặc timeout.
        """
        if not self.is_ready:
            raise RuntimeError(
                "Gemini Web chưa được mở.\n"
                "Vào tab 'Gemini Web' → nhấn 'Open Browser' trước."
            )

        result_holder = []
        error_holder  = []
        done_event    = threading.Event()

        async def _send():
            try:
                full = ""
                async for chunk in self._client.stream_response(prompt):
                    full += chunk
                result_holder.append(full)
            except Exception as e:
                error_holder.append(e)
            finally:
                done_event.set()

        asyncio.run_coroutine_threadsafe(_send(), self._loop)

        if not done_event.wait(timeout=timeout):
            raise TimeoutError(f"Gemini không phản hồi sau {timeout}s")

        if error_holder:
            raise RuntimeError(str(error_holder[0]))

        return result_holder[0] if result_holder else ""


# Global singleton
_bridge = GeminiWebBridge()


def get_bridge() -> GeminiWebBridge:
    return _bridge


# ── Public AI functions (thay thế ai_module) ─────────────────────────────────

def is_available() -> bool:
    """Trả về True nếu Gemini Web đang sẵn sàng."""
    return _bridge.is_ready


def check_writing(topic: str, content: str) -> dict:
    prompt = f"""You are an English teacher for B1-level Vietnamese students.
Check the following writing on topic: "{topic}"

Student writing:
{content}

Please provide:
1. A score out of 10
2. Grammar errors (list each error and correction)
3. Vocabulary suggestions (better word choices)
4. Structure feedback
5. Overall encouragement

Format your response as:
SCORE: X/10
GRAMMAR:
- [error] → [correction]
VOCABULARY:
- [suggestion]
STRUCTURE: [feedback]
ENCOURAGEMENT: [positive message]"""

    text = _bridge.ask(prompt)
    score = 7
    for line in text.split("\n"):
        if line.startswith("SCORE:"):
            try:
                score = int(line.split(":")[1].strip().split("/")[0])
            except Exception:
                pass
    return {"feedback": text, "score": score}


def explain_word(word: str) -> str:
    prompt = f"""Explain the English word "{word}" for a Vietnamese B1-level learner. Include:
1. Pronunciation (IPA)
2. Part of speech
3. Meaning in Vietnamese
4. 3 example sentences at B1 level
5. Common collocations
6. A memory tip

Keep it concise and friendly."""
    return _bridge.ask(prompt)


def generate_reading_passage(topic: str, level: str = "B1") -> dict:
    prompt = f"""Create a reading comprehension exercise at {level} level about "{topic}".

Format exactly as:
PASSAGE:
[Write a 150-200 word passage here]

QUESTIONS:
1. [Question 1]
2. [Question 2]
3. [Question 3]
4. [Question 4]
5. [Question 5]

ANSWERS:
1. [Answer 1]
2. [Answer 2]
3. [Answer 3]
4. [Answer 4]
5. [Answer 5]"""

    text = _bridge.ask(prompt)
    passage, questions, answers = "", [], []
    section = None
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("PASSAGE:"):
            section = "passage"
        elif line.startswith("QUESTIONS:"):
            section = "questions"
        elif line.startswith("ANSWERS:"):
            section = "answers"
        elif line and section == "passage":
            passage += line + " "
        elif line and section == "questions" and line[0].isdigit():
            questions.append(line[2:].strip() if ". " in line else line)
        elif line and section == "answers" and line[0].isdigit():
            answers.append(line[2:].strip() if ". " in line else line)
    return {"passage": passage.strip(), "questions": questions, "answers": answers}


def generate_grammar_exercise(grammar_point: str) -> list:
    prompt = f"""Create 5 fill-in-the-blank grammar exercises focusing on "{grammar_point}" for B1 level.

Format each as:
Q: [sentence with _____ for the blank]
A: [correct answer]
EXPLANATION: [brief explanation]
---"""
    text = _bridge.ask(prompt)
    exercises, current = [], {}
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("Q:"):
            current = {"question": line[2:].strip()}
        elif line.startswith("A:") and current:
            current["answer"] = line[2:].strip()
        elif line.startswith("EXPLANATION:") and current:
            current["explanation"] = line[12:].strip()
            exercises.append(current)
            current = {}
    return exercises


def get_speaking_topic(level: str = "B1") -> str:
    prompt = f"""Give me one interesting speaking/writing topic for a {level} English learner.
Include:
- The topic
- 3-4 guiding questions to help structure the answer
- Key vocabulary (5 words) to use

Keep it motivating and relevant to daily life."""
    return _bridge.ask(prompt)


def chat_practice(history: list, user_message: str) -> str:
    system = """You are a friendly English conversation partner for a Vietnamese learner at B1 level.
- Respond naturally but correct any grammar mistakes gently at the end of your response
- Use vocabulary appropriate for B1 level
- Encourage the learner
- Format corrections as: [Correction: 'their mistake' → 'correct form']"""

    # Build conversation context
    history_text = ""
    for msg in history[-10:]:  # Chỉ lấy 10 tin nhắn gần nhất
        role = "Student" if msg["role"] == "user" else "Teacher"
        history_text += f"{role}: {msg['content']}\n"

    prompt = f"""{system}

Previous conversation:
{history_text}
Student: {user_message}

Teacher:"""
    return _bridge.ask(prompt)
