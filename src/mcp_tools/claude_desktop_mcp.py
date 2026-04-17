"""
Claude Desktop MCP Server — WebCrawlerGemini
=============================================
Tools cho Claude Desktop:

[WEB SCRAPING]
  scrape_url          — Fetch nội dung trang web (text + links + title)
  scrape_browser      — Fetch trang JS-heavy bằng Playwright headless
  scrape_shopee       — Tìm sản phẩm Shopee theo từ khóa
  extract_table       — Trích bảng dữ liệu từ trang
  css_query           — Tìm elements bằng CSS selector

[GEMINI WEB]
  gemini_open         — Mở Chrome → Gemini.google.com (lưu session)
  gemini_chat         — Gửi prompt, nhận phản hồi đầy đủ
  gemini_screenshot   — Chụp màn hình Gemini
  gemini_new_chat     — Bắt đầu conversation mới
  gemini_close        — Đóng browser

[ENGLISH LEARNING]
  english_reading     — Tạo N bài reading comprehension về một chủ đề
  english_grammar     — Tạo bài tập grammar fill-in-blank
  english_writing     — Chấm điểm và nhận xét bài viết
  english_vocab       — Giải thích từ vựng chi tiết
  english_speaking    — Lấy chủ đề speaking/writing practice
"""

import asyncio
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any

# ── Thêm project root vào sys.path ───────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

app = Server("webcrawler-gemini")

# ── Singleton Gemini client ───────────────────────────────────────────────────
_gemini_client = None
_gemini_loop: asyncio.AbstractEventLoop | None = None
_gemini_thread = None


def _ensure_gemini_loop():
    """Đảm bảo event loop Gemini đang chạy trong thread riêng."""
    global _gemini_loop, _gemini_thread
    import threading
    if _gemini_loop is None or not _gemini_loop.is_running():
        _gemini_loop = asyncio.new_event_loop()
        _gemini_thread = threading.Thread(
            target=lambda: _gemini_loop.run_forever(),
            daemon=True, name="GeminiLoop"
        )
        _gemini_thread.start()
    return _gemini_loop


def _run_gemini(coro, timeout=90):
    """Chạy coroutine Gemini trong thread riêng, blocking."""
    loop = _ensure_gemini_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result(timeout=timeout)


# ─────────────────────────────────────────────────────────────────────────────
# TOOL DEFINITIONS
# ─────────────────────────────────────────────────────────────────────────────

@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [

        # ── WEB SCRAPING ─────────────────────────────────────────────────────

        types.Tool(
            name="scrape_url",
            description=(
                "Fetch nội dung trang web: title, text, links. "
                "Dùng cho trang HTML tĩnh (không cần JS). "
                "Ví dụ: đọc tin tức, blog, wiki, trang sản phẩm đơn giản."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL cần fetch"},
                    "max_text": {
                        "type": "integer",
                        "description": "Giới hạn số ký tự text trả về (default 5000)",
                        "default": 5000,
                    },
                },
                "required": ["url"],
            },
        ),

        types.Tool(
            name="scrape_browser",
            description=(
                "Fetch trang web cần JavaScript (SPA, lazy load, infinite scroll). "
                "Chậm hơn scrape_url nhưng xử lý được Shopee, Lazada, TikTok, v.v."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL cần fetch"},
                    "wait_seconds": {
                        "type": "number",
                        "description": "Chờ thêm sau khi load (giây, default 2)",
                        "default": 2,
                    },
                    "max_text": {"type": "integer", "default": 8000},
                },
                "required": ["url"],
            },
        ),

        types.Tool(
            name="scrape_shopee",
            description=(
                "Tìm kiếm sản phẩm trên Shopee.vn theo từ khóa. "
                "Trả về danh sách sản phẩm với tên, giá, lượt bán, rating, link. "
                "Có thể sort theo: relevance (mặc định), sales (bán chạy), price_asc, price_desc."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "Từ khóa tìm kiếm"},
                    "sort_by": {
                        "type": "string",
                        "enum": ["relevance", "sales", "price_asc", "price_desc"],
                        "default": "sales",
                        "description": "Cách sắp xếp kết quả",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Số sản phẩm tối đa (default 10)",
                        "default": 10,
                    },
                },
                "required": ["keyword"],
            },
        ),

        types.Tool(
            name="extract_table",
            description="Trích xuất bảng dữ liệu (table HTML) từ trang web.",
            inputSchema={
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
        ),

        types.Tool(
            name="css_query",
            description="Tìm nội dung elements theo CSS selector trên trang web.",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "selector": {"type": "string", "description": "CSS selector, ví dụ: 'h1', '.price', '#product-name'"},
                },
                "required": ["url", "selector"],
            },
        ),

        # ── GEMINI WEB ───────────────────────────────────────────────────────

        types.Tool(
            name="gemini_open",
            description=(
                "Mở Chrome và vào Gemini.google.com. "
                "Session được lưu — lần sau không cần login lại. "
                "Phải gọi tool này trước khi dùng gemini_chat."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "headless": {
                        "type": "boolean",
                        "description": "Ẩn cửa sổ Chrome (default false = hiện browser)",
                        "default": False,
                    },
                },
            },
        ),

        types.Tool(
            name="gemini_chat",
            description=(
                "Gửi prompt tới Gemini Web, chờ phản hồi đầy đủ, trả về text. "
                "Cần gọi gemini_open trước. "
                "Ví dụ: hỏi phân tích dữ liệu, viết nội dung, dịch thuật, v.v."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "Nội dung gửi cho Gemini"},
                    "new_conversation": {
                        "type": "boolean",
                        "description": "Bắt đầu chat mới trước khi gửi (default false)",
                        "default": False,
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Timeout giây (default 90)",
                        "default": 90,
                    },
                },
                "required": ["prompt"],
            },
        ),

        types.Tool(
            name="gemini_new_chat",
            description="Bắt đầu conversation mới với Gemini (xóa lịch sử chat hiện tại).",
            inputSchema={"type": "object", "properties": {}},
        ),

        types.Tool(
            name="gemini_screenshot",
            description="Chụp màn hình trạng thái hiện tại của browser Gemini.",
            inputSchema={
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Tên file (default: gemini_screenshot.png)",
                        "default": "gemini_screenshot.png",
                    },
                },
            },
        ),

        types.Tool(
            name="gemini_close",
            description="Đóng browser Gemini.",
            inputSchema={"type": "object", "properties": {}},
        ),

        # ── ENGLISH LEARNING ─────────────────────────────────────────────────

        types.Tool(
            name="english_reading",
            description=(
                "Tạo bài reading comprehension tiếng Anh bằng Gemini Web. "
                "Trả về passage + câu hỏi + đáp án. "
                "Cần gemini_open trước. "
                "Ví dụ: 'Tạo 5 bài reading về technology cho trình độ B1'."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "Chủ đề bài đọc"},
                    "level": {
                        "type": "string",
                        "enum": ["A1", "A2", "B1", "B2", "C1"],
                        "default": "B1",
                        "description": "Trình độ CEFR",
                    },
                    "count": {
                        "type": "integer",
                        "description": "Số bài cần tạo (default 1, max 10)",
                        "default": 1,
                    },
                },
                "required": ["topic"],
            },
        ),

        types.Tool(
            name="english_grammar",
            description=(
                "Tạo bài tập grammar fill-in-the-blank bằng Gemini Web. "
                "Cần gemini_open trước."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "grammar_point": {
                        "type": "string",
                        "description": "Điểm ngữ pháp cần luyện, ví dụ: 'present perfect', 'conditional type 2'",
                    },
                    "count": {"type": "integer", "default": 5, "description": "Số câu bài tập"},
                },
                "required": ["grammar_point"],
            },
        ),

        types.Tool(
            name="english_writing",
            description=(
                "Chấm điểm và nhận xét bài viết tiếng Anh bằng Gemini Web. "
                "Trả về điểm số, lỗi ngữ pháp, gợi ý từ vựng. "
                "Cần gemini_open trước."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "Chủ đề bài viết"},
                    "content": {"type": "string", "description": "Nội dung bài viết cần chấm"},
                },
                "required": ["topic", "content"],
            },
        ),

        types.Tool(
            name="english_vocab",
            description=(
                "Giải thích từ vựng tiếng Anh chi tiết bằng Gemini Web: "
                "phát âm IPA, nghĩa tiếng Việt, ví dụ câu, collocations. "
                "Cần gemini_open trước."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "word": {"type": "string", "description": "Từ hoặc cụm từ cần giải thích"},
                },
                "required": ["word"],
            },
        ),

        types.Tool(
            name="english_speaking",
            description=(
                "Lấy chủ đề speaking/writing practice phù hợp trình độ. "
                "Cần gemini_open trước."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "level": {
                        "type": "string",
                        "enum": ["A1", "A2", "B1", "B2", "C1"],
                        "default": "B1",
                    },
                },
            },
        ),
        types.Tool(
            name="english_vocab_list",
            description=(
                "Tạo danh sách từ vựng tiếng Anh theo trình độ CEFR và chủ đề. "
                "Mỗi từ có: từ, phiên âm IPA, loại từ, nghĩa tiếng Việt, ví dụ câu. "
                "Có thể tạo nhiều lượt để đạt số lượng lớn (vd: 3000 từ B1). "
                "Cần gemini_open trước. "
                "Ví dụ: 'Tạo 3000 từ vựng B1 tiếng Anh thông dụng nhất'."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "level": {
                        "type": "string",
                        "enum": ["A1", "A2", "B1", "B2", "C1", "C2"],
                        "default": "B1",
                        "description": "Trình độ CEFR",
                    },
                    "count": {
                        "type": "integer",
                        "description": "Tổng số từ cần tạo (default 100, có thể đến 3000+)",
                        "default": 100,
                    },
                    "topics": {
                        "type": "string",
                        "description": (
                            "Chủ đề cần bao gồm, phân cách bằng dấu phẩy. "
                            "Để trống = tổng hợp tất cả chủ đề thông dụng. "
                            "Ví dụ: 'technology, health, business, travel'"
                        ),
                        "default": "",
                    },
                    "output_format": {
                        "type": "string",
                        "enum": ["json", "csv", "markdown"],
                        "default": "json",
                        "description": "Định dạng output",
                    },
                    "save_file": {
                        "type": "string",
                        "description": (
                            "Tên file để lưu kết quả (vd: 'vocab_b1.json'). "
                            "Để trống = chỉ trả về text."
                        ),
                        "default": "",
                    },
                },
                "required": [],
            },
        ),

    ]


# ─────────────────────────────────────────────────────────────────────────────
# TOOL HANDLERS
# ─────────────────────────────────────────────────────────────────────────────

@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    try:
        return await _dispatch(name, arguments)
    except Exception as e:
        logger.exception(f"Tool error [{name}]")
        return [types.TextContent(type="text", text=json.dumps(
            {"success": False, "error": str(e)}, ensure_ascii=False
        ))]


async def _dispatch(name: str, args: dict) -> list[types.TextContent]:
    global _gemini_client

    def ok(data) -> list[types.TextContent]:
        if isinstance(data, str):
            return [types.TextContent(type="text", text=data)]
        return [types.TextContent(type="text", text=json.dumps(data, ensure_ascii=False, indent=2))]

    def err(msg: str) -> list[types.TextContent]:
        return ok({"success": False, "error": msg})

    # ── scrape_url ────────────────────────────────────────────────────────────
    if name == "scrape_url":
        from src.crawler.crawler import WebCrawler
        result = WebCrawler().fetch(args["url"])
        if result["success"]:
            max_t = args.get("max_text", 5000)
            result["text"] = result["text"][:max_t]
            result.pop("html", None)
        return ok(result)

    # ── scrape_browser ────────────────────────────────────────────────────────
    elif name == "scrape_browser":
        from playwright.async_api import async_playwright
        url = args["url"]
        wait_sec = args.get("wait_seconds", 2)
        max_t = args.get("max_text", 8000)
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(int(wait_sec * 1000))
            text = await page.evaluate("() => document.body.innerText")
            title = await page.title()
            links = await page.evaluate(
                "() => [...document.querySelectorAll('a[href]')].map(a=>a.href).slice(0,50)"
            )
            await browser.close()
        return ok({
            "success": True, "url": url, "title": title,
            "text": (text or "")[:max_t], "links": links,
        })

    # ── scrape_shopee ─────────────────────────────────────────────────────────
    elif name == "scrape_shopee":
        keyword = args["keyword"]
        sort_by = args.get("sort_by", "sales")
        limit = min(args.get("limit", 10), 30)

        # Shopee API công khai (không cần auth)
        sort_map = {"relevance": 0, "sales": 2, "price_asc": 1, "price_desc": 3}
        sort_val = sort_map.get(sort_by, 2)
        api_url = (
            f"https://shopee.vn/api/v4/search/search_items"
            f"?by=sales&keyword={keyword}&limit={limit}&newest=0"
            f"&order=desc&page_type=search&scenario=PAGE_GLOBAL_SEARCH"
            f"&version=2&match_id=0&sortBy={sort_val}"
        )

        from playwright.async_api import async_playwright
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            ctx = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                locale="vi-VN",
            )
            page = await ctx.new_page()
            # Vào trang chủ Shopee trước để lấy cookie
            await page.goto("https://shopee.vn", wait_until="domcontentloaded", timeout=20000)
            await page.wait_for_timeout(1500)
            # Gọi API search
            resp = await page.evaluate(f"""
                async () => {{
                    const r = await fetch('{api_url}', {{
                        headers: {{
                            'referer': 'https://shopee.vn/search?keyword={keyword}',
                            'x-requested-with': 'XMLHttpRequest',
                        }}
                    }});
                    return await r.json();
                }}
            """)
            await browser.close()

        products = []
        items = resp.get("items") or resp.get("data", {}).get("items", [])
        for item in items[:limit]:
            info = item.get("item_basic") or item
            name_p = info.get("name", "")
            price = info.get("price", 0) // 100000  # Shopee dùng đơn vị 1/100000 VNĐ
            price_min = info.get("price_min", 0) // 100000
            sold = info.get("sold", info.get("historical_sold", 0))
            rating = round(info.get("item_rating", {}).get("rating_star", 0), 1)
            shop_id = info.get("shopid", "")
            item_id = info.get("itemid", "")
            link = f"https://shopee.vn/product/{shop_id}/{item_id}"
            products.append({
                "name": name_p,
                "price_vnd": f"{price:,}đ" if price == price_min else f"{price_min:,}đ - {price:,}đ",
                "sold": sold,
                "rating": rating,
                "link": link,
            })

        return ok({
            "success": True, "keyword": keyword, "sort_by": sort_by,
            "total_found": len(products), "products": products,
        })

    # ── extract_table ─────────────────────────────────────────────────────────
    elif name == "extract_table":
        from src.crawler.crawler import WebCrawler
        tables = WebCrawler().extract_tables(args["url"])
        return ok({"success": True, "url": args["url"], "tables": tables})

    # ── css_query ─────────────────────────────────────────────────────────────
    elif name == "css_query":
        from src.crawler.crawler import WebCrawler
        wc = WebCrawler()
        result = wc.fetch(args["url"])
        if not result["success"]:
            return err(result.get("error", "Fetch failed"))
        elements = wc.search_elements(result["html"], args["selector"])
        return ok({"success": True, "selector": args["selector"], "results": elements})

    # ── gemini_open ───────────────────────────────────────────────────────────
    elif name == "gemini_open":
        from src.gemini.gemini_web_client import GeminiWebClient
        headless = args.get("headless", False)
        _gemini_client = GeminiWebClient(headless=headless)
        loop = _ensure_gemini_loop()

        import concurrent.futures
        fut = asyncio.run_coroutine_threadsafe(_gemini_client.start(), loop)
        fut.result(timeout=60)

        fut2 = asyncio.run_coroutine_threadsafe(_gemini_client.navigate_to_gemini(), loop)
        logged_in = fut2.result(timeout=60)

        if not logged_in:
            fut3 = asyncio.run_coroutine_threadsafe(
                _gemini_client.wait_for_login(timeout_seconds=120), loop
            )
            logged_in = fut3.result(timeout=130)

        return ok({
            "success": logged_in,
            "status": "✅ Sẵn sàng chat!" if logged_in else "⚠️ Chưa đăng nhập — hãy login trong browser",
        })

    # ── gemini_chat ───────────────────────────────────────────────────────────
    elif name == "gemini_chat":
        if not _gemini_client:
            return err("Chưa mở Gemini. Gọi gemini_open trước!")
        import concurrent.futures
        loop = _ensure_gemini_loop()
        prompt = args["prompt"]
        timeout = args.get("timeout", 90)

        if args.get("new_conversation", False):
            asyncio.run_coroutine_threadsafe(
                _gemini_client.new_conversation(), loop
            ).result(timeout=10)

        fut = asyncio.run_coroutine_threadsafe(_gemini_client.chat(prompt), loop)
        try:
            response = fut.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            return err(f"Gemini không phản hồi sau {timeout}s")
        return ok({"success": True, "prompt": prompt, "response": response})

    # ── gemini_new_chat ───────────────────────────────────────────────────────
    elif name == "gemini_new_chat":
        if not _gemini_client:
            return err("Chưa mở Gemini. Gọi gemini_open trước!")
        _ensure_gemini_loop()
        asyncio.run_coroutine_threadsafe(
            _gemini_client.new_conversation(), _gemini_loop
        ).result(timeout=15)
        return ok({"success": True, "status": "Đã bắt đầu conversation mới"})

    # ── gemini_screenshot ─────────────────────────────────────────────────────
    elif name == "gemini_screenshot":
        if not _gemini_client:
            return err("Chưa mở Gemini.")
        fname = args.get("filename", "gemini_screenshot.png")
        save_path = str(PROJECT_ROOT / "screenshots" / fname)
        Path(save_path).parent.mkdir(exist_ok=True)
        asyncio.run_coroutine_threadsafe(
            _gemini_client.take_screenshot(save_path), _ensure_gemini_loop()
        ).result(timeout=15)
        return ok({"success": True, "saved": save_path})

    # ── gemini_close ──────────────────────────────────────────────────────────
    elif name == "gemini_close":
        if _gemini_client:
            asyncio.run_coroutine_threadsafe(
                _gemini_client.stop(), _ensure_gemini_loop()
            ).result(timeout=10)
            _gemini_client = None
        return ok({"success": True, "status": "Browser đã đóng"})

    # ── english_reading ───────────────────────────────────────────────────────
    elif name == "english_reading":
        if not _gemini_client:
            return err("Cần gọi gemini_open trước!")
        topic = args["topic"]
        level = args.get("level", "B1")
        count = min(args.get("count", 1), 10)

        import concurrent.futures
        loop = _ensure_gemini_loop()

        results = []
        for i in range(count):
            prompt = f"""Create a reading comprehension exercise #{i+1} at {level} level about "{topic}".

Use EXACTLY this plain text format (no markdown, no bold):

PASSAGE:
Write a 150-200 word passage here.

QUESTIONS:
1. First question?
2. Second question?
3. Third question?
4. Fourth question?
5. Fifth question?

ANSWERS:
1. Answer 1
2. Answer 2
3. Answer 3
4. Answer 4
5. Answer 5"""

            if i > 0:
                # New conversation cho mỗi bài tiếp theo
                asyncio.run_coroutine_threadsafe(
                    _gemini_client.new_conversation(), loop
                ).result(timeout=10)

            fut = asyncio.run_coroutine_threadsafe(_gemini_client.chat(prompt), loop)
            try:
                text = fut.result(timeout=90) or ""
            except concurrent.futures.TimeoutError:
                text = ""

            parsed = _parse_reading(text)
            parsed["index"] = i + 1
            parsed["topic"] = topic
            parsed["level"] = level
            results.append(parsed)

        return ok({
            "success": True,
            "topic": topic, "level": level, "count": count,
            "readings": results,
        })

    # ── english_grammar ───────────────────────────────────────────────────────
    elif name == "english_grammar":
        if not _gemini_client:
            return err("Cần gọi gemini_open trước!")
        grammar_point = args["grammar_point"]
        count = args.get("count", 5)

        import concurrent.futures
        prompt = f"""Create {count} fill-in-the-blank grammar exercises for "{grammar_point}" at B1 level.

Use EXACTLY this format (no markdown):

Q: Sentence with _____ for the blank.
A: correct answer
EXPLANATION: Brief explanation.
---"""
        fut = asyncio.run_coroutine_threadsafe(
            _gemini_client.chat(prompt), _ensure_gemini_loop()
        )
        try:
            text = fut.result(timeout=90) or ""
        except concurrent.futures.TimeoutError:
            return err("Gemini timeout")

        exercises = _parse_grammar(text)
        return ok({
            "success": True, "grammar_point": grammar_point,
            "count": len(exercises), "exercises": exercises,
        })

    # ── english_writing ───────────────────────────────────────────────────────
    elif name == "english_writing":
        if not _gemini_client:
            return err("Cần gọi gemini_open trước!")
        import concurrent.futures
        prompt = f"""You are an English teacher for B1-level Vietnamese students.
Check this writing on topic: "{args['topic']}"

Student writing:
{args['content']}

Provide feedback in this EXACT format (plain text, no markdown):

SCORE: X/10
GRAMMAR:
- error -> correction
VOCABULARY:
- suggestion
STRUCTURE: feedback here
ENCOURAGEMENT: positive message here"""

        fut = asyncio.run_coroutine_threadsafe(
            _gemini_client.chat(prompt), _ensure_gemini_loop()
        )
        try:
            text = fut.result(timeout=90) or ""
        except concurrent.futures.TimeoutError:
            return err("Gemini timeout")

        score = 7
        m = re.search(r'SCORE[:\s]+(\d+)', text, re.IGNORECASE)
        if m:
            score = int(m.group(1))
        return ok({"success": True, "score": score, "feedback": text})

    # ── english_vocab ─────────────────────────────────────────────────────────
    elif name == "english_vocab":
        if not _gemini_client:
            return err("Cần gọi gemini_open trước!")
        import concurrent.futures
        word = args["word"]
        prompt = f"""Explain the English word/phrase "{word}" for a Vietnamese B1 learner.
Include: IPA pronunciation, part of speech, Vietnamese meaning, 3 example sentences, collocations, memory tip.
Plain text only, no markdown."""
        fut = asyncio.run_coroutine_threadsafe(
            _gemini_client.chat(prompt), _ensure_gemini_loop()
        )
        try:
            text = fut.result(timeout=60) or ""
        except concurrent.futures.TimeoutError:
            return err("Gemini timeout")
        return ok({"success": True, "word": word, "explanation": text})

    # ── english_speaking ──────────────────────────────────────────────────────
    elif name == "english_speaking":
        if not _gemini_client:
            return err("Cần gọi gemini_open trước!")
        import concurrent.futures
        level = args.get("level", "B1")
        prompt = f"""Give one interesting speaking/writing topic for a {level} English learner.
Include: the topic, 3-4 guiding questions, 5 key vocabulary words.
Plain text only."""
        fut = asyncio.run_coroutine_threadsafe(
            _gemini_client.chat(prompt), _ensure_gemini_loop()
        )
        try:
            text = fut.result(timeout=60) or ""
        except concurrent.futures.TimeoutError:
            return err("Gemini timeout")
        return ok({"success": True, "level": level, "topic_suggestion": text})

    # ── english_vocab_list ───────────────────────────────────────────────────
    elif name == "english_vocab_list":
        if not _gemini_client:
            return err("Cần gọi gemini_open trước!")

        import concurrent.futures
        level        = args.get("level", "B1")
        total        = max(10, args.get("count", 100))
        topics_str   = args.get("topics", "").strip()
        out_fmt      = args.get("output_format", "json")
        save_file    = args.get("save_file", "").strip()
        loop         = _ensure_gemini_loop()

        # Gemini trả về ~100 từ mỗi lần → cần nhiều lượt nếu count lớn
        BATCH = 100
        all_words: list[dict] = []
        batch_num = 0
        topics_list = [t.strip() for t in topics_str.split(",") if t.strip()] or [
            "daily life", "travel", "food", "health", "technology",
            "education", "work", "environment", "culture", "sport",
            "shopping", "family", "emotions", "transport", "weather",
            "money", "media", "government", "science", "art",
            "animals", "nature", "body", "clothes", "housing",
            "relationships", "time", "numbers", "colors", "jobs",
        ]

        while len(all_words) < total:
            remaining = total - len(all_words)
            batch_size = min(BATCH, remaining)
            # Chọn topic xoay vòng
            topic = topics_list[batch_num % len(topics_list)]
            batch_num += 1

            already = len(all_words)
            prompt = f"""Generate exactly {batch_size} unique {level} level English vocabulary words related to topic: "{topic}".
These are for Vietnamese learners. Do NOT repeat words already given.

Return ONLY a JSON array (no markdown, no explanation) like this:
[
  {{"word": "example", "ipa": "/ɪɡˈzɑːmpl/", "pos": "noun", "vi": "ví dụ", "sentence": "This is an example sentence."}},
  ...
]

Rules:
- words must be appropriate for {level} CEFR level
- all {batch_size} entries must be unique
- no markdown, return raw JSON array only"""

            # New conversation mỗi batch để tránh context limit
            if batch_num > 1:
                try:
                    asyncio.run_coroutine_threadsafe(
                        _gemini_client.new_conversation(), loop
                    ).result(timeout=10)
                except Exception:
                    pass

            fut = asyncio.run_coroutine_threadsafe(
                _gemini_client.chat(prompt), loop
            )
            try:
                raw = fut.result(timeout=90) or ""
            except concurrent.futures.TimeoutError:
                raw = ""

            # Parse JSON từ response
            batch_words = _parse_vocab_json(raw)
            # Dedup theo từ
            existing_words = {w["word"].lower() for w in all_words}
            for w in batch_words:
                if w.get("word", "").lower() not in existing_words:
                    all_words.append(w)
                    existing_words.add(w["word"].lower())

            if not batch_words:
                break  # Gemini không trả về gì → dừng

        all_words = all_words[:total]

        # Format output
        if out_fmt == "csv":
            lines = ["word,ipa,pos,vietnamese,example_sentence"]
            for w in all_words:
                word    = str(w.get("word", "")).replace('"', '""')
                ipa     = str(w.get("ipa",  "")).replace('"', '""')
                pos     = str(w.get("pos",  "")).replace('"', '""')
                vi      = str(w.get("vi",   "")).replace('"', '""')
                sent    = str(w.get("sentence", "")).replace('"', '""')
                lines.append(f'"{word}","{ipa}","{pos}","{vi}","{sent}"')
            output_text = "\n".join(lines)
        elif out_fmt == "markdown":
            lines = ["| # | Word | IPA | POS | Vietnamese | Example |",
                     "|---|------|-----|-----|------------|---------|"]
            for i, w in enumerate(all_words, 1):
                lines.append(
                    f"| {i} | {w.get('word','')} | {w.get('ipa','')} | "
                    f"{w.get('pos','')} | {w.get('vi','')} | {w.get('sentence','')} |"
                )
            output_text = "\n".join(lines)
        else:  # json
            output_text = json.dumps(all_words, ensure_ascii=False, indent=2)

        # Lưu file nếu được yêu cầu
        saved_path = ""
        if save_file:
            save_dir = PROJECT_ROOT / "vocab_exports"
            save_dir.mkdir(exist_ok=True)
            save_path_obj = save_dir / save_file
            save_path_obj.write_text(output_text, encoding="utf-8")
            saved_path = str(save_path_obj)

        return ok({
            "success": True,
            "level": level,
            "requested": total,
            "generated": len(all_words),
            "format": out_fmt,
            "saved_to": saved_path or "(not saved)",
            "data": all_words if out_fmt == "json" else output_text,
        })

    else:
        return [types.TextContent(type="text", text=f'{{"error": "Unknown tool: {name}"}}'  )]


# ─────────────────────────────────────────────────────────────────────────────
# PARSE HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _strip_md(text: str) -> str:
    text = re.sub(r'\*{1,3}([^*\n]+)\*{1,3}', r'\1', text)
    text = re.sub(r'^#{1,4}\s*', '', text, flags=re.MULTILINE)
    return text


def _section_header(line: str) -> str | None:
    clean = re.sub(r'^[#*\-_>\s]+', '', line)
    clean = re.sub(r'[*_:\s]+$', '', clean).upper().strip()
    if clean in ("PASSAGE", "TEXT", "READING PASSAGE", "READING TEXT"):
        return "passage"
    if clean in ("QUESTIONS", "COMPREHENSION QUESTIONS", "EXERCISE"):
        return "questions"
    if clean in ("ANSWERS", "ANSWER KEY", "KEYS", "KEY"):
        return "answers"
    return None


def _parse_reading(text: str) -> dict:
    text = _strip_md(text)
    passage, questions, answers = "", [], []
    section = None
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        h = _section_header(line)
        if h:
            section = h
            continue
        if section == "passage":
            passage += line + " "
        elif section == "questions":
            m = re.match(r'^\d+[\.\)]\s*(.+)', line)
            if m:
                questions.append(m.group(1).strip())
        elif section == "answers":
            m = re.match(r'^\d+[\.\)]\s*(.+)', line)
            if m:
                answers.append(m.group(1).strip())
    if not passage.strip():
        passage = text[:500]
    return {"passage": passage.strip(), "questions": questions, "answers": answers}


def _parse_grammar(text: str) -> list:
    text = _strip_md(text)
    exercises, current = [], {}
    for line in text.split("\n"):
        line = line.strip()
        mq = re.match(r'^Q[:\s]+(.+)', line, re.IGNORECASE)
        ma = re.match(r'^A[:\s]+(.+)', line, re.IGNORECASE)
        me = re.match(r'^EXPLANATION[:\s]+(.+)', line, re.IGNORECASE)
        if mq:
            current = {"question": mq.group(1).strip()}
        elif ma and current:
            current["answer"] = ma.group(1).strip()
        elif me and current:
            current["explanation"] = me.group(1).strip()
            if "question" in current and "answer" in current:
                exercises.append(current)
            current = {}
    return exercises


def _parse_vocab_json(raw: str) -> list[dict]:
    """Parse JSON array từ vựng từ Gemini response — xử lý markdown wrapper."""
    # Bỏ markdown code block nếu có
    raw = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()

    # Tìm JSON array trong text (Gemini đôi khi thêm text trước/sau)
    start = raw.find("[")
    end   = raw.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return []

    try:
        data = json.loads(raw[start:end + 1])
        if not isinstance(data, list):
            return []
        # Chuẩn hóa keys
        result = []
        for item in data:
            if not isinstance(item, dict):
                continue
            word = (
                item.get("word") or item.get("Word") or
                item.get("english") or item.get("English") or ""
            ).strip()
            if not word:
                continue
            result.append({
                "word":     word,
                "ipa":      item.get("ipa") or item.get("IPA") or item.get("pronunciation") or "",
                "pos":      item.get("pos") or item.get("type") or item.get("part_of_speech") or "",
                "vi":       item.get("vi") or item.get("vietnamese") or item.get("meaning") or item.get("definition") or "",
                "sentence": item.get("sentence") or item.get("example") or item.get("example_sentence") or "",
            })
        return result
    except json.JSONDecodeError:
        return []


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
