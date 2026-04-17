"""Gemini Web browser automation client."""
from __future__ import annotations

import base64
import json
import mimetypes
import time
from pathlib import Path
from typing import AsyncGenerator


GEMINI_URL = "https://gemini.google.com"

CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Users\hipy\AppData\Local\Google\Chrome\Application\chrome.exe",
]

_JS_GET_RESPONSE = """
() => {
    const selectors = [
        '[data-test-id="conversation-turn"] model-response',
        '[data-turn-role="model"]',
        'message-content .markdown',
        '.conversation-container model-response',
        'model-response',
        'response-container',
        '.response-container-content',
        'message-content',
        '[data-role="model"]',
        '.model-response-text',
        '.markdown',
    ];
    const seen = new Set();
    const candidates = [];
    for (const sel of selectors) {
        const els = document.querySelectorAll(sel);
        for (const el of els) {
            if (seen.has(el)) continue;
            seen.add(el);
            const text = (el.innerText || el.textContent || '').trim();
            if (text.length <= 10) continue;
            const rect = el.getBoundingClientRect();
            const style = window.getComputedStyle(el);
            const visible = rect.width > 0
                && rect.height > 0
                && style.visibility !== 'hidden'
                && style.display !== 'none';
            candidates.push({ el, text, visible });
        }
    }
    if (candidates.length > 0) {
        candidates.sort((a, b) => {
            if (a.el === b.el) return 0;
            const pos = a.el.compareDocumentPosition(b.el);
            if (pos & Node.DOCUMENT_POSITION_FOLLOWING) return -1;
            if (pos & Node.DOCUMENT_POSITION_PRECEDING) return 1;
            return 0;
        });
        const visible = candidates.filter((item) => item.visible);
        const source = visible.length > 0 ? visible : candidates;
        return source[source.length - 1].text;
    }
    return '';
}
"""

_JS_IS_DONE = """
() => {
    const stopBtn = document.querySelector(
        'button[aria-label*="Stop"], button[aria-label*="stop"], button[aria-label*="Dừng"]'
    );
    if (stopBtn && stopBtn.offsetParent !== null) return false;

    const sendBtn = document.querySelector(
        'button[aria-label*="Send"], button[aria-label*="send"]'
    );
    if (sendBtn) return !sendBtn.disabled;

    const input = document.querySelector(
        'rich-textarea div[contenteditable], div[contenteditable="true"]'
    );
    if (input) {
        const disabled = input.getAttribute('aria-disabled') === 'true'
            || input.getAttribute('disabled') != null;
        return !disabled;
    }
    return true;
}
"""


def find_chrome() -> str | None:
    for path in CHROME_PATHS:
        if Path(path).exists():
            return path
    return None


class GeminiWebClient:
    def __init__(self, profile_dir: str = "Default", headless: bool = False, slow_mo: int = 30):
        self.profile_dir = profile_dir
        self.headless = headless
        self.slow_mo = slow_mo
        self._playwright = None
        self._context = None
        self._page = None
        self._is_ready = False

    async def start(self) -> bool:
        from playwright.async_api import async_playwright

        chrome_exe = find_chrome()
        project_root = Path(__file__).parent.parent.parent
        user_data_dir = project_root / "chrome_profile" / "GeminiSession"
        user_data_dir.mkdir(parents=True, exist_ok=True)

        for lock_name in ["LOCK", "SingletonLock"]:
            for item in user_data_dir.rglob(lock_name):
                try:
                    item.unlink()
                except Exception:
                    pass

        self._playwright = await async_playwright().start()
        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            executable_path=chrome_exe,
            headless=self.headless,
            slow_mo=self.slow_mo,
            args=[
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-blink-features=AutomationControlled",
                "--exclude-switches=enable-automation",
                "--disable-infobars",
                "--lang=en-US",
            ],
            ignore_default_args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--enable-automation",
            ],
            ignore_https_errors=True,
            viewport={"width": 1280, "height": 800},
            locale="en-US",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/146.0.0.0 Safari/537.36"
            ),
        )
        await self._context.grant_permissions(["clipboard-read", "clipboard-write"], origin=GEMINI_URL)
        self._page = self._context.pages[0] if self._context.pages else await self._context.new_page()
        await self._context.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            delete navigator.__proto__.webdriver;
            window.chrome = {
                app: { isInstalled: false },
                runtime: { onConnect: { addListener: () => {} }, onMessage: { addListener: () => {} } },
                loadTimes: function() {}, csi: function() {},
            };
            Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US','en'] });
            """
        )
        return True

    async def stop(self):
        if self._context:
            await self._context.close()
        if self._playwright:
            await self._playwright.stop()
        self._is_ready = False

    async def navigate_to_gemini(self) -> bool:
        try:
            await self._page.goto(GEMINI_URL, wait_until="load", timeout=45000)
        except Exception:
            pass
        await self._page.wait_for_timeout(4000)
        if await self._is_logged_in():
            self._is_ready = True
            return True
        return False

    async def _is_logged_in(self) -> bool:
        selectors = [
            "rich-textarea",
            'div[contenteditable="true"]',
            "textarea[placeholder]",
            'div[aria-label*="message"]',
            'div[aria-label*="Enter"]',
            'div[aria-label*="prompt"]',
        ]
        for selector in selectors:
            try:
                await self._page.wait_for_selector(selector, timeout=4000)
                return True
            except Exception:
                continue
        url = self._page.url
        if "gemini.google.com" in url and "accounts.google.com" not in url:
            await self._page.wait_for_timeout(3000)
            for selector in selectors:
                try:
                    await self._page.wait_for_selector(selector, timeout=3000)
                    return True
                except Exception:
                    continue
        return False

    async def wait_for_login(self, timeout_seconds: int = 180) -> bool:
        start = time.time()
        while time.time() - start < timeout_seconds:
            await self._page.wait_for_timeout(2000)
            if await self._is_logged_in():
                self._is_ready = True
                return True
        return False

    async def _get_chat_input(self):
        for selector in [
            'rich-textarea div[contenteditable="true"]',
            'div[contenteditable="true"][data-placeholder]',
            'div[contenteditable="true"]',
            "textarea",
        ]:
            try:
                element = await self._page.wait_for_selector(selector, timeout=3000)
                if element:
                    return element
            except Exception:
                continue
        return None

    async def send_message(self, message: str) -> bool:
        if not self._is_ready:
            raise RuntimeError("Gemini Web chua san sang.")
        input_el = await self._get_chat_input()
        if not input_el:
            raise RuntimeError("Khong tim thay o nhap.")

        await input_el.click()
        await self._page.wait_for_timeout(200)
        await self._page.keyboard.press("Control+a")
        await self._page.keyboard.press("Delete")
        await self._page.wait_for_timeout(100)

        is_editable = await input_el.evaluate("el => el.getAttribute('contenteditable')")
        if is_editable == "true":
            escaped = json.dumps(message)
            await self._page.evaluate(
                f"""
                async () => {{
                    const text = {escaped};
                    await navigator.clipboard.writeText(text);
                }}
                """
            )
            await input_el.click()
            await self._page.wait_for_timeout(100)
            await self._page.keyboard.press("Control+a")
            await self._page.keyboard.press("Delete")
            await self._page.wait_for_timeout(100)
            await self._page.keyboard.press("Control+v")
        else:
            await input_el.fill(message)
        await self._page.wait_for_timeout(400)

        for selector in [
            'button[aria-label*="Send"]',
            'button[aria-label*="send"]',
            'button[data-testid="send-button"]',
            "button.send-button",
        ]:
            try:
                button = await self._page.query_selector(selector)
                if button and await button.is_enabled():
                    await button.click()
                    return True
            except Exception:
                continue

        await self._page.keyboard.press("Enter")
        return True

    async def _paste_image(self, image_path: str) -> bool:
        path = str(Path(image_path).resolve())
        if not Path(path).exists():
            raise FileNotFoundError(path)
        input_el = await self._get_chat_input()
        if not input_el:
            raise RuntimeError("Khong tim thay o nhap de dan anh.")

        mime_type, _ = mimetypes.guess_type(path)
        mime_type = mime_type or "image/png"
        encoded = base64.b64encode(Path(path).read_bytes()).decode("ascii")

        await input_el.click()
        await self._page.wait_for_timeout(150)
        pasted = await self._page.evaluate(
            """
            async ({ selector, encoded, mimeType, fileName }) => {
                const host = document.querySelector(selector);
                if (!host) return false;

                const binary = atob(encoded);
                const bytes = new Uint8Array(binary.length);
                for (let i = 0; i < binary.length; i += 1) {
                    bytes[i] = binary.charCodeAt(i);
                }

                const file = new File([bytes], fileName, { type: mimeType });
                const dataTransfer = new DataTransfer();
                dataTransfer.items.add(file);

                const pasteEvent = new ClipboardEvent('paste', {
                    clipboardData: dataTransfer,
                    bubbles: true,
                    cancelable: true,
                });

                const target = host.matches('[contenteditable="true"], textarea, input')
                    ? host
                    : host.querySelector('[contenteditable="true"], textarea, input');

                if (!target) return false;
                target.focus();
                return target.dispatchEvent(pasteEvent);
            }
            """,
            {
                "selector": 'rich-textarea div[contenteditable="true"], '
                            'div[contenteditable="true"][data-placeholder], '
                            'div[contenteditable="true"], textarea',
                "encoded": encoded,
                "mimeType": mime_type,
                "fileName": Path(path).name,
            },
        )
        if not pasted:
            return False

        await self._page.wait_for_timeout(2200)
        return True

    def _clean(self, text: str, *, trim_edges: bool = True) -> str:
        import re

        for pattern in [
            r"You stopped this response",
            r"Gemini said",
            r"Copy\s*Share",
            r"Thumbs up\s*Thumbs down",
            r"More options",
            r"content_copy",
            r"thumb_up\s*thumb_down",
            r"Run in Google Colab",
            r"Export to Sheets?",
            r"Open in Sheets?",
        ]:
            text = re.sub(pattern, " ", text, flags=re.IGNORECASE)

        text = re.sub(r"^\s*\|[\s\-\|:]+\|\s*$", "", text, flags=re.MULTILINE)
        text = re.sub(r"([.!?])([A-Za-z\d])", r"\1 \2", text)
        text = re.sub(r"[ \t]{2,}", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip() if trim_edges else text

    async def _get_raw_response(self) -> str:
        try:
            return await self._page.evaluate(_JS_GET_RESPONSE) or ""
        except Exception:
            return ""

    async def _wait_until_done(self, timeout_ms: int = 90000, previous_text: str = "") -> str:
        start_wait = time.time()
        while time.time() - start_wait < 8:
            await self._page.wait_for_timeout(300)
            current = await self._get_raw_response()
            if current and current != previous_text:
                break

        try:
            await self._page.wait_for_function(_JS_IS_DONE, timeout=timeout_ms, polling=200)
        except Exception:
            pass

        last_text = ""
        stable_count = 0
        deadline = time.time() + 15
        while time.time() < deadline:
            await self._page.wait_for_timeout(500)
            try:
                current = await self._get_raw_response()
            except Exception:
                current = last_text

            if current == last_text and current and current != previous_text:
                stable_count += 1
                if stable_count >= 3:
                    break
            else:
                stable_count = 0
                if current and current != previous_text:
                    last_text = current
        final = await self._get_raw_response()
        if final and final != previous_text:
            return final
        return last_text

    async def chat(self, message: str) -> str:
        previous_text = await self._get_raw_response()
        await self.send_message(message)
        return self._clean(await self._wait_until_done(previous_text=previous_text))

    async def chat_about_image(self, image_path: str, message: str) -> str:
        if not self._is_ready:
            raise RuntimeError("Gemini Web chua san sang.")
        attached = await self._paste_image(image_path)
        if not attached:
            raise RuntimeError("Khong the dan anh vao Gemini Web.")
        return await self.chat(message)

    async def stream_response(self, message: str) -> AsyncGenerator[str, None]:
        await self.send_message(message)
        await self._page.wait_for_timeout(1000)

        last_raw_len = 0
        start = time.time()
        done = False

        while not done and time.time() - start < 120:
            await self._page.wait_for_timeout(350)
            try:
                if self._page.is_closed():
                    break
            except Exception:
                break

            try:
                raw = await self._get_raw_response()
            except Exception:
                break

            if raw and len(raw) > last_raw_len:
                new_chunk = raw[last_raw_len:]
                cleaned = self._clean(new_chunk, trim_edges=False)
                if cleaned:
                    yield cleaned
                last_raw_len = len(raw)

            try:
                is_done = await self._page.evaluate(_JS_IS_DONE)
            except Exception:
                break

            if is_done and raw:
                await self._page.wait_for_timeout(400)
                try:
                    final_raw = await self._get_raw_response()
                    if final_raw and len(final_raw) > last_raw_len:
                        remainder = self._clean(final_raw[last_raw_len:], trim_edges=False)
                        if remainder:
                            yield remainder
                except Exception:
                    pass
                done = True

    async def new_conversation(self):
        for selector in [
            'button[aria-label*="New chat"]',
            'button[aria-label*="New Chat"]',
            'a[aria-label*="New chat"]',
        ]:
            try:
                element = await self._page.query_selector(selector)
                if element:
                    await element.click()
                    await self._page.wait_for_timeout(800)
                    return True
            except Exception:
                continue
        try:
            await self._page.goto(GEMINI_URL, wait_until="domcontentloaded", timeout=10000)
            await self._page.wait_for_timeout(1500)
        except Exception:
            pass
        return True

    async def take_screenshot(self, path: str = "gemini_screenshot.png") -> str:
        await self._page.screenshot(path=path)
        return path

    async def is_alive(self) -> bool:
        try:
            return not self._page.is_closed()
        except Exception:
            return False
