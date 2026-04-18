"""
AI module cho English Learning — dùng GeminiWebClient trực tiếp (same process).
_call_web dùng chat() → wait_for_function (browser tự báo khi xong).
Parser robust: xử lý mọi format markdown Gemini trả về.
"""
from __future__ import annotations
import base64
import json
import mimetypes
import re
import asyncio
import concurrent.futures
import threading
from pathlib import Path

import requests

# ── Global client + loop ──────────────────────────────────────────────────────
_gemini_client = None
_gemini_loop: asyncio.AbstractEventLoop | None = None
_web_job_lock = threading.Lock()
_web_job_name = ""
_web_job_future = None


def set_gemini(client, loop):
    global _gemini_client, _gemini_loop
    _gemini_client = client
    _gemini_loop   = loop


def clear_gemini():
    global _gemini_client, _gemini_loop
    _gemini_client = None
    _gemini_loop   = None


def _use_web() -> bool:
    return _gemini_client is not None and _gemini_loop is not None


def _claim_web_job(job_name: str):
    global _web_job_name
    if not _web_job_lock.acquire(blocking=False):
        active = _web_job_name or "another Gemini Web task"
        raise RuntimeError(f"Gemini Web is busy with {active}. Wait for it to finish before starting a new task.")
    _web_job_name = job_name


def _release_web_job():
    global _web_job_name, _web_job_future
    _web_job_name = ""
    _web_job_future = None
    if _web_job_lock.locked():
        _web_job_lock.release()


def get_web_job_status() -> str:
    return _web_job_name if _web_job_lock.locked() else ""


def cancel_web_job() -> bool:
    future = _web_job_future
    if future is None:
        return False
    try:
        future.cancel()
        return True
    except Exception:
        return False


# ── _call_web ─────────────────────────────────────────────────────────────────

def _call_web(prompt: str, timeout: int = 90, job_name: str = "a Gemini Web task") -> str:
    """Gửi prompt → Gemini Web, trả về full text (blocking)."""
    if not _use_web():
        raise RuntimeError(
            "Gemini Web chưa sẵn sàng.\n"
            "Vào tab 'Gemini Web' → nhấn 'Open Browser' trước."
        )
    _claim_web_job(job_name)
    future = asyncio.run_coroutine_threadsafe(
        _gemini_client.chat(prompt),
        _gemini_loop,
    )
    global _web_job_future
    _web_job_future = future
    try:
        return future.result(timeout=timeout) or ""
    except concurrent.futures.TimeoutError:
        future.cancel()
        raise TimeoutError(f"Gemini không phản hồi sau {timeout}s — thử lại")
    except Exception as e:
        raise RuntimeError(str(e))
    finally:
        _release_web_job()


def _call_web_with_image(image_path: str, prompt: str, timeout: int = 120) -> str:
    if not _use_web():
        raise RuntimeError("Gemini Web chua san sang.")
    _claim_web_job("an image Gemini Web task")
    future = asyncio.run_coroutine_threadsafe(
        _gemini_client.chat_about_image(image_path, prompt),
        _gemini_loop,
    )
    global _web_job_future
    _web_job_future = future
    try:
        return future.result(timeout=timeout) or ""
    except concurrent.futures.TimeoutError:
        future.cancel()
        raise TimeoutError(f"Gemini khong phan hoi sau {timeout}s")
    except Exception as e:
        raise RuntimeError(str(e))
    finally:
        _release_web_job()


# ── Fallback: API key ─────────────────────────────────────────────────────────

def _is_gemini_key(key: str) -> bool:
    return key.startswith("AIza")


def _gemini_generate(api_key: str, parts: list[dict], system: str = "", max_tokens: int = 1024) -> str:
    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": max_tokens,
        },
    }
    if system:
        payload["system_instruction"] = {"parts": [{"text": system}]}

    response = requests.post(
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-2.0-flash:generateContent",
        params={"key": api_key},
        headers={"Content-Type": "application/json"},
        data=json.dumps(payload),
        timeout=90,
    )
    response.raise_for_status()

    data = response.json()
    candidates = data.get("candidates") or []
    if not candidates:
        prompt_feedback = data.get("promptFeedback", {})
        reason = prompt_feedback.get("blockReason") or data
        raise RuntimeError(f"Gemini returned no content: {reason}")

    text_parts = []
    for part in candidates[0].get("content", {}).get("parts", []):
        if "text" in part:
            text_parts.append(part["text"])
    text = "\n".join(text_parts).strip()
    if not text:
        raise RuntimeError("Gemini returned an empty response.")
    return text


def _call_api(api_key: str, prompt: str, system: str = "", max_tokens: int = 1024) -> str:
    if _is_gemini_key(api_key):
        full = f"{system}\n\n{prompt}" if system else prompt
        return _gemini_generate(api_key, [{"text": full}], max_tokens=max_tokens)
    else:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        kw = dict(model="claude-opus-4-6", max_tokens=max_tokens,
                  messages=[{"role": "user", "content": prompt}])
        if system:
            kw["system"] = system
        return client.messages.create(**kw).content[0].text


def _call_ai(api_key: str, prompt: str, system: str = "", max_tokens: int = 1024) -> str:
    if _use_web():
        full = f"{system}\n\n{prompt}" if system else prompt
        return _call_web(full)
    if not api_key:
        raise RuntimeError(
            "Chưa có AI.\nVào tab 'Gemini Web' → 'Open Browser'\nhoặc nhập API key."
        )
    return _call_api(api_key, prompt, system, max_tokens)


# ── Shared parser helpers ─────────────────────────────────────────────────────

def _strip_markdown(text: str) -> str:
    """Bỏ markdown formatting để parse section headers dễ hơn."""
    text = re.sub(r'\*{1,3}([^*\n]+)\*{1,3}', r'\1', text)   # **x** / *x*
    text = re.sub(r'^#{1,4}\s*', '', text, flags=re.MULTILINE) # ## heading
    text = re.sub(r'^_{1,2}([^_\n]+)_{1,2}', r'\1', text, flags=re.MULTILINE)  # __x__
    return text


def _section_header(line: str) -> str | None:
    """Nhận dạng section header linh hoạt, trả về tên section hoặc None."""
    # Bỏ ký tự đặc biệt đầu/cuối và ở giữa nếu là gạch ngang
    clean = re.sub(r'^[#*\-=>\s]+', '', line)
    clean = re.sub(r'[*_:\-=>\s]+$', '', clean).upper().strip()
    if clean in ("PASSAGE", "TEXT", "READING PASSAGE", "READING TEXT"):
        return "passage"
    if clean in ("QUESTIONS", "COMPREHENSION QUESTIONS", "EXERCISE"):
        return "questions"
    if clean in ("ANSWERS", "ANSWER KEY", "KEYS", "KEY"):
        return "answers"
    return None


# ── Public API ────────────────────────────────────────────────────────────────

def get_provider_name(api_key: str) -> str:
    if _use_web():
        return "Gemini Web"
    if not api_key:
        return "No AI"
    return "Google Gemini" if _is_gemini_key(api_key) else "Anthropic Claude"


def describe_image(api_key: str, image_path: str, level: str = "B1", focus: str = "general") -> str:
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {path}")

    prompt = f"""You are helping a Vietnamese English learner at level {level}.
Analyze this image for English speaking practice with focus: {focus}.

Return plain text with EXACT sections:
TITLE:
SCENE:
KEY VOCABULARY:
- word: short explanation in Vietnamese
USEFUL SENTENCES:
1.
2.
3.
MODEL DESCRIPTION:
QUESTIONS TO PRACTICE:
1.
2.
3.
"""

    if _use_web():
        return _call_web_with_image(str(path), prompt)

    if not api_key:
        raise RuntimeError("Image analysis needs Gemini Web or a Gemini API key.")
    if not _is_gemini_key(api_key):
        raise RuntimeError("Image analysis currently supports Gemini Web or Gemini API keys only.")

    mime_type, _ = mimetypes.guess_type(path.name)
    mime_type = mime_type or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")

    return _gemini_generate(
        api_key,
        [
            {"text": prompt},
            {"inline_data": {"mime_type": mime_type, "data": encoded}},
        ],
        max_tokens=1400,
    )


def review_image_description(api_key: str, image_notes: str, user_description: str, level: str = "B1") -> dict:
    prompt = f"""You are an English speaking and writing coach for a Vietnamese learner at level {level}.

Reference notes about the image:
{image_notes}

Student description:
{user_description}

Evaluate the student's English description.
Format exactly like this:
SCORE: X/10
STRENGTHS:
- ...
CORRECTIONS:
- original -> improved
BETTER VERSION:
...
NEXT STEP:
...
"""
    text = _call_ai(api_key, prompt)
    score = 7
    for line in text.splitlines():
        m = re.search(r"SCORE[:\s]+(\d+)", line, re.IGNORECASE)
        if m:
            score = int(m.group(1))
            break
    return {"feedback": text, "score": score}


def check_writing(api_key: str, topic: str, content: str) -> dict:
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
- [error] -> [correction]
VOCABULARY:
- [suggestion]
STRUCTURE: [feedback]
ENCOURAGEMENT: [positive message]"""
    text = _call_ai(api_key, prompt)
    score = 7
    for line in text.split("\n"):
        # match "SCORE: 8/10" hoặc "**SCORE:** 8/10"
        m = re.search(r'SCORE[:\s]+(\d+)', line, re.IGNORECASE)
        if m:
            try:
                score = int(m.group(1))
            except Exception:
                pass
    return {"feedback": text, "score": score}


def generate_writing_support(api_key: str, topic: str, level: str = "B1", mode: str = "paragraph") -> dict:
    prompt = f"""You are a writing coach for a Vietnamese learner at level {level}.
Create a writing support pack for topic "{topic}" in mode "{mode}".

Return plain text with EXACT sections:
TASK:
OUTLINE:
1.
2.
3.
USEFUL VOCABULARY:
- word: Vietnamese meaning
SENTENCE STARTERS:
- ...
CHECKLIST:
- ...
MODEL IDEAS:
- ...
"""
    text = _call_ai(api_key, prompt)
    return {"pack": text}


def check_reading_translation(passage: str, user_translation: str, level: str = "B1") -> str:
    """Dùng Gemini Web để kiểm tra bản dịch tiếng Việt của user và gợi ý nội dung."""
    prompt = f"""Bạn là giáo viên tiếng Anh cho học viên Việt Nam trình độ {level}.

Dưới đây là bài đọc tiếng Anh và bản dịch tiếng Việt của học viên. Hãy đánh giá:

📄 BÀI ĐỌC GỐC (TIẾNG ANH):
{passage}

📝 BẢN DỊCH CỦA HỌC VIÊN (TIẾNG VIỆT):
{user_translation}

Hãy trả lời bằng tiếng Việt với format sau:

## 📊 ĐÁNH GIÁ TỔNG QUAN
- Điểm hiểu bài: X/10
- Nhận xét ngắn gọn về mức độ hiểu bài

## ✅ PHẦN DỊCH ĐÚNG
- Liệt kê các ý chính mà học viên đã hiểu đúng

## ❌ PHẦN CẦN SỬA
- Liệt kê các câu/đoạn dịch sai hoặc chưa chính xác
- Chỉ rõ: [Câu gốc] → [Dịch sai] → [Dịch đúng nên là]

## 💡 GỢI Ý VỀ NỘI DUNG BÀI ĐỌC
- Tóm tắt nội dung chính của bài đọc
- Các ý quan trọng mà học viên có thể đã bỏ sót
- Từ vựng quan trọng trong bài cần chú ý (liệt kê 5-8 từ kèm nghĩa)
- Câu hỏi gợi ý để hiểu sâu hơn về chủ đề bài đọc

## 🌟 LỜI KHUYÊN
- Gợi ý cách cải thiện kỹ năng đọc hiểu cho lần sau"""

    return _call_web(prompt)


def explain_word(api_key: str, word: str) -> str:
    prompt = f"""Explain the English word "{word}" for a Vietnamese B1-level learner. Include:
1. Pronunciation (IPA)
2. Part of speech
3. Meaning in Vietnamese
4. 3 example sentences at B1 level
5. Common collocations
6. A memory tip
Keep it concise and friendly."""
    return _call_ai(api_key, prompt)


def generate_reading_passage(api_key: str, topic: str, level: str = "B1") -> dict:
    prompt = f"""Create an engaging, informative, and structurally clear reading passage at {level} level about "{topic}".
IMPORTANT: Do NOT include any questions or answers inside the passage text itself.

Use EXACTLY this format (plain text, no markdown formatting like bold/italics):

---PASSAGE---
(Write a 150-250 word passage here. ONLY the text, absolutely no questions or exercises)

---QUESTIONS---
1. (First question)
2. (Second question)
3. (Third question)
4. (Fourth question)
5. (Fifth question)

---ANSWERS---
1. (Answer to question 1)
2. (Answer to question 2)
3. (Answer to question 3)
4. (Answer to question 4)
5. (Answer to question 5)"""

    text = _call_ai(api_key, prompt)
    # Strip markdown trước khi parse
    text = _strip_markdown(text)
    
    # Đôi khi AI trả về trên 1 dòng duy nhất và dính liền với ---
    # Thay thế ---SECTION--- bằng \n---SECTION---\n để dễ parse hơn
    text = re.sub(r'(---[A-Z]+---)', r'\n\1\n', text)

    passage, questions, answers = "", [], []
    section = None

    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue

        header = _section_header(line)
        if header:
            section = header
            continue

        if section == "passage":
            passage += line + " "
        elif section == "questions":
            # Extract questions if inline (e.g. "1. Q1? 2. Q2?")
            parts = re.split(r'(?=\b\d+[\.\)])', line)
            if len(parts) <= 1 and "?" in line:
                # If no numbers found but there are questions marks, split by ?
                parts = [q + "?" for q in line.split("?") if q.strip()]
            for q_str in parts:
                q_str = q_str.strip()
                # Remove leading numbers if present, or just use the string
                m = re.match(r'^\d+[\.\)]\s*(.+)', q_str)
                if m:
                    questions.append(m.group(1).strip())
                elif q_str and len(q_str) > 5:
                    questions.append(q_str.strip())
        elif section == "answers":
            parts = re.split(r'(?=\b\d+[\.\)])', line)
            if len(parts) <= 1 and "." in line:
                # If no numbers, split by sentences
                 parts = [a + "." for a in line.split(".") if a.strip()]
            for a_str in parts:
                a_str = a_str.strip()
                m = re.match(r'^\d+[\.\)]\s*(.+)', a_str)
                if m:
                    answers.append(m.group(1).strip())
                elif a_str and len(a_str) > 5:
                    answers.append(a_str.strip())

    # Fallback: nếu parse sạch vẫn trống → trả về toàn bộ text làm passage
    if not passage.strip() and text.strip():
        passage = text.strip()

    return {
        "passage": passage.strip(),
        "questions": questions,
        "answers": answers,
    }


def generate_grammar_exercise(api_key: str, grammar_point: str) -> list:
    prompt = f"""Create exactly 1 fill-in-the-blank grammar exercise focusing on "{grammar_point}" for level B1-B2.
Return ONLY 1 raw JSON object, no markdown, no code fences, no extra text:
{{
  "question": "A sentence with _____ for the blank",
  "answer": "the correct answer only",
  "explanation": "Detailed explanation in Vietnamese: why the answer is correct, what grammar rule is used, and 1-2 extra examples"
}}"""
    text = _call_ai(api_key, prompt)
    text = _strip_markdown(text)

    exercises = []
    json_match = re.search(r"\{.*\}", text, re.DOTALL)
    if json_match:
        try:
            item = json.loads(json_match.group(0))
            question = str(item.get("question", "")).strip()
            answer = str(item.get("answer", "")).strip()
            explanation = str(item.get("explanation", "")).strip()
            if question and answer:
                return [{"question": question, "answer": answer, "explanation": explanation}]
        except Exception:
            pass

    normalized_text = re.sub(r"(?im)^\s*(?:exercise|question)\s+\d+[:.)-]?\s*", "### Q: ", text)
    normalized_text = re.sub(r"(?im)^\s*\*+\s*(?:q|question)\s*[:\-]?\s*", "### Q: ", normalized_text)
    normalized_text = re.sub(r"(?im)^\s*(?:answer|dap an)\s*[:.)-]?\s*", "### A: ", normalized_text)
    normalized_text = re.sub(r"(?im)^\s*\*+\s*(?:a|answer)\s*[:\-]?\s*", "### A: ", normalized_text)
    normalized_text = re.sub(r"(?im)^\s*(?:explanation|giai thich)\s*[:.)-]?\s*", "### E: ", normalized_text)
    normalized_text = re.sub(r"(?im)^\s*\*+\s*(?:e|explanation|giai thich)\s*[:\-]?\s*", "### E: ", normalized_text)
    blocks = [b.strip() for b in re.split(r"\n?---+\n?|(?=###\s*Q[:\s])", normalized_text) if b.strip()]

    def _clean_field(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()

    def _extract_block(block: str) -> dict:
        patterns = {
            "question": [
                r"(?:###\s*)?Q(?:UESTION)?[:\s]+(.*?)(?=(?:###\s*)?A(?:NSWER)?[:\s]+|(?:###\s*)?E(?:XPLANATION)?[:\s]+|$)",
                r"(?:Cau hoi|Question)[:\s]+(.*?)(?=(?:Dap an|Answer)[:\s]+|(?:Giai thich|Explanation)[:\s]+|$)",
            ],
            "answer": [
                r"(?:###\s*)?A(?:NSWER)?[:\s]+(.*?)(?=(?:###\s*)?Q(?:UESTION)?[:\s]+|(?:###\s*)?E(?:XPLANATION)?[:\s]+|$)",
                r"(?:Dap an|Answer)[:\s]+(.*?)(?=(?:Cau hoi|Question)[:\s]+|(?:Giai thich|Explanation)[:\s]+|$)",
            ],
            "explanation": [
                r"(?:###\s*)?E(?:XPLANATION)?[:\s]+(.*?)(?=(?:###\s*)?Q(?:UESTION)?[:\s]+|(?:###\s*)?A(?:NSWER)?[:\s]+|$)",
                r"(?:Giai thich|Explanation)[:\s]+(.*?)(?=(?:Cau hoi|Question)[:\s]+|(?:Dap an|Answer)[:\s]+|$)",
            ],
        }
        current = {}
        for field, field_patterns in patterns.items():
            for pattern in field_patterns:
                match = re.search(pattern, block, re.DOTALL | re.IGNORECASE)
                if match:
                    current[field] = _clean_field(match.group(1))
                    break
        return current

    for block in blocks:
        current = _extract_block(block)
        if current.get("question") and current.get("answer"):
            exercises.append(current)

    if exercises:
        return exercises

    inline_chunks = re.split(r"(?=(?:\d+[\.\)]\s*)?Q(?:uestion)?[:\s])", normalized_text, flags=re.IGNORECASE)
    for chunk in inline_chunks:
        current = _extract_block(chunk)
        if current.get("question") and current.get("answer"):
            exercises.append(current)
    if exercises:
        return exercises

    line_based = []
    current = {}
    for raw_line in text.splitlines():
        line = raw_line.strip(" -*\t")
        if not line:
            continue
        if re.match(r"^(?:\d+[\.\)]\s*)?(?:Q|Question)[:\s]", line, re.IGNORECASE):
            if current.get("question") and current.get("answer"):
                line_based.append(current)
            current = {"question": _clean_field(re.sub(r"^(?:\d+[\.\)]\s*)?(?:Q|Question)[:\s]+", "", line, flags=re.IGNORECASE))}
        elif re.match(r"^(?:A|Answer)[:\s]", line, re.IGNORECASE):
            current["answer"] = _clean_field(re.sub(r"^(?:A|Answer)[:\s]+", "", line, flags=re.IGNORECASE))
        elif re.match(r"^(?:E|Explanation|Giai thich)[:\s]", line, re.IGNORECASE):
            current["explanation"] = _clean_field(re.sub(r"^(?:E|Explanation|Giai thich)[:\s]+", "", line, flags=re.IGNORECASE))
        elif current.get("explanation"):
            current["explanation"] = f"{current['explanation']} {line}".strip()
        elif current.get("question") and not current.get("answer"):
            current["question"] = f"{current['question']} {line}".strip()
        elif current.get("answer") and not current.get("explanation"):
            current["answer"] = f"{current['answer']} {line}".strip()

    if current.get("question") and current.get("answer"):
        line_based.append(current)

    return line_based



def get_speaking_topic(api_key: str, level: str = "B1") -> str:
    prompt = f"""Give me one interesting speaking/writing topic for a {level} English learner.
Include:
- The topic
- 3-4 guiding questions to help structure the answer
- Key vocabulary (5 words) to use
Keep it motivating and relevant to daily life."""
    return _call_ai(api_key, prompt)


def chat_practice(api_key: str, history: list, user_message: str) -> str:
    system = """You are a friendly English conversation partner for a Vietnamese learner at B1 level.
- Respond naturally but correct any grammar mistakes gently at the end of your response
- Use vocabulary appropriate for B1 level
- Encourage the learner
- Format corrections as: [Correction: 'their mistake' -> 'correct form']"""

    if _use_web():
        history_text = ""
        for msg in history[-10:]:
            role = "Student" if msg["role"] == "user" else "Teacher"
            history_text += f"{role}: {msg['content']}\n"
        prompt = f"""{system}

Previous conversation:
{history_text}
Student: {user_message}

Teacher:"""
        return _call_web(prompt)

    if not api_key:
        raise RuntimeError("Chưa có AI. Mở Gemini Web hoặc nhập API key.")

    if _is_gemini_key(api_key):
        history_text = ""
        for msg in history[-10:]:
            role = "Student" if msg["role"] == "user" else "Teacher"
            history_text += f"{role}: {msg['content']}\n"
        prompt = f"""Previous conversation:
{history_text}
Student: {user_message}

Teacher:"""
        return _gemini_generate(
            api_key,
            [{"text": prompt}],
            system=system,
            max_tokens=512,
        )
    else:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        messages = history + [{"role": "user", "content": user_message}]
        resp = client.messages.create(
            model="claude-opus-4-6", max_tokens=512,
            system=system, messages=messages,
        )
        return resp.content[0].text
