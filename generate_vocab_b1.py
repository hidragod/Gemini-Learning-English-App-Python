"""
generate_vocab_b1.py
====================
Tạo 3000 từ vựng B1 tiếng Anh bằng Gemini Web, lưu ra JSON.
Chạy: uv run python generate_vocab_b1.py

Mỗi từ gồm: word, ipa, pos, vietnamese meaning, example sentence.
Tiến trình được lưu tạm sau mỗi batch — nếu bị gián đoạn, chạy lại sẽ tiếp tục từ chỗ dở.
"""

import asyncio
import json
import re
import sys
import time
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
TARGET       = 3000          # tổng số từ cần tạo
BATCH_SIZE   = 100           # số từ mỗi lần hỏi Gemini
OUT_FILE     = Path(__file__).parent / "vocab_exports" / "vocab_b1_3000.json"
TEMP_FILE    = Path(__file__).parent / "vocab_exports" / "vocab_b1_temp.json"
HEADLESS     = False         # True = ẩn browser, False = hiện để theo dõi

# 30 chủ đề xoay vòng → đảm bảo đa dạng
TOPICS = [
    "daily life and routines", "travel and tourism", "food and cooking",
    "health and medicine", "technology and internet", "education and study",
    "work and career", "environment and nature", "culture and traditions",
    "sport and fitness", "shopping and money", "family and relationships",
    "emotions and personality", "transport and directions", "weather and seasons",
    "media and entertainment", "government and society", "science and discovery",
    "art and music", "animals and wildlife", "body and appearance",
    "clothes and fashion", "housing and furniture", "time and schedules",
    "numbers and measurements", "colors and shapes", "social issues",
    "business and economy", "language and communication", "hobbies and free time",
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def parse_vocab(raw: str) -> list[dict]:
    """Parse JSON array từ Gemini — xử lý markdown wrapper và key khác nhau."""
    raw = re.sub(r"```(?:json)?\s*", "", raw, flags=re.IGNORECASE).strip().rstrip("`").strip()
    start, end = raw.find("["), raw.rfind("]")
    if start == -1 or end <= start:
        return []
    try:
        data = json.loads(raw[start:end + 1])
    except json.JSONDecodeError:
        # Thử fix JSON bị cắt cụt
        try:
            data = json.loads(raw[start:end + 1].rsplit(",", 1)[0] + "]")
        except Exception:
            return []
    result = []
    for item in data:
        if not isinstance(item, dict):
            continue
        word = (
            item.get("word") or item.get("Word") or
            item.get("english") or item.get("term") or ""
        ).strip()
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
        })
    return result


def save_progress(words: list[dict], path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(words, ensure_ascii=False, indent=2), encoding="utf-8")


def load_progress(path: Path) -> list[dict]:
    if path.exists():
        try:
            return json.loads(path.read_text("utf-8"))
        except Exception:
            pass
    return []


def make_prompt(topic: str, batch_size: int, batch_index: int) -> str:
    return f"""Generate exactly {batch_size} unique B1-level English vocabulary words about "{topic}".
These words are for Vietnamese learners. Make sure words are common and useful at B1 CEFR level.

Return ONLY a raw JSON array — no markdown, no explanation, no code block wrapper.
Each object must have exactly these keys:

[
  {{"word": "...", "ipa": "/…/", "pos": "noun|verb|adj|adv|prep|conj", "vi": "nghĩa tiếng Việt", "sentence": "Example sentence using the word."}},
  ...
]

Requirements:
- Exactly {batch_size} entries
- All words must be different from each other
- Words appropriate for B1 level (not too simple A1, not too advanced C1)
- Vietnamese meaning must be accurate
- Example sentence must be natural B1-level English
- Return raw JSON array only, starting with [ and ending with ]"""


# ── Main async flow ───────────────────────────────────────────────────────────

async def main():
    sys.path.insert(0, str(Path(__file__).parent))
    from src.gemini.gemini_web_client import GeminiWebClient

    # Load progress nếu đã chạy dở
    all_words = load_progress(TEMP_FILE)
    existing_set = {w["word"].lower() for w in all_words}

    if all_words:
        print(f"▶ Tiếp tục từ checkpoint: đã có {len(all_words)} từ")
    else:
        print("▶ Bắt đầu mới")

    # Mở Gemini
    print("\n🌐 Đang mở Gemini Web...")
    client = GeminiWebClient(headless=HEADLESS)
    await client.start()
    logged_in = await client.navigate_to_gemini()

    if not logged_in:
        print("⚠️  Chưa đăng nhập. Hãy đăng nhập Google trong browser (tối đa 2 phút)...")
        logged_in = await client.wait_for_login(timeout_seconds=120)

    if not logged_in:
        print("❌ Không đăng nhập được. Thoát.")
        await client.stop()
        return

    print("✅ Đã đăng nhập Gemini!\n")

    batch_num = len(all_words) // BATCH_SIZE  # batch tiếp theo
    total_batches = (TARGET + BATCH_SIZE - 1) // BATCH_SIZE

    try:
        while len(all_words) < TARGET:
            remaining = TARGET - len(all_words)
            this_batch = min(BATCH_SIZE, remaining)
            topic = TOPICS[batch_num % len(TOPICS)]

            print(f"📦 Batch {batch_num + 1}/{total_batches} | Topic: {topic} | "
                  f"Đang lấy {this_batch} từ... [{len(all_words)}/{TARGET}]")

            # New conversation mỗi batch để tránh context quá dài
            if batch_num > 0:
                await client.new_conversation()
                await asyncio.sleep(0.5)

            prompt = make_prompt(topic, this_batch, batch_num)
            t0 = time.time()
            raw = await client.chat(prompt)
            elapsed = time.time() - t0

            words = parse_vocab(raw)
            # Dedup
            new_words = []
            for w in words:
                if w["word"].lower() not in existing_set:
                    new_words.append(w)
                    existing_set.add(w["word"].lower())

            all_words.extend(new_words)
            save_progress(all_words, TEMP_FILE)

            print(f"   ✓ Nhận {len(new_words)} từ mới (unique) | {elapsed:.1f}s | "
                  f"Tổng: {len(all_words)}/{TARGET}")

            if not new_words:
                print("   ⚠️  Batch rỗng — đổi topic và thử lại...")

            batch_num += 1

    except KeyboardInterrupt:
        print("\n⏸  Bị dừng. Progress đã lưu tạm.")
    except Exception as e:
        print(f"\n❌ Lỗi: {e}")
        import traceback; traceback.print_exc()
    finally:
        await client.stop()

    # Lưu file kết quả cuối
    final = all_words[:TARGET]
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8")

    # Xóa file tạm
    if TEMP_FILE.exists():
        TEMP_FILE.unlink()

    print(f"\n{'='*60}")
    print(f"✅ HOÀN THÀNH!")
    print(f"   Tổng từ: {len(final)}")
    print(f"   File: {OUT_FILE}")
    print(f"   Size: {OUT_FILE.stat().st_size / 1024:.1f} KB")
    print(f"{'='*60}")

    # Preview 3 từ đầu
    print("\nPreview:")
    for w in final[:3]:
        print(f"  {w['word']:15} {w['ipa']:20} [{w['pos']:5}] {w['vi']}")
        print(f"  → {w['sentence']}")


if __name__ == "__main__":
    asyncio.run(main())
