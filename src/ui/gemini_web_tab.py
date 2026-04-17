"""
Gemini Web Tab - Chat với Gemini.google.com qua Playwright
"""
import asyncio
import threading
import datetime
import html
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QTextBrowser,
    QPushButton, QLabel, QGroupBox, QFrame, QCheckBox, QProgressBar, QComboBox
)
from PySide6.QtCore import Qt, Signal, QObject, QTimer
from PySide6.QtGui import QFont, QShortcut, QKeySequence


# ─── Worker ─────────────────────────────────────────────────────────────────

class GeminiWorker(QObject):
    """
    Chạy toàn bộ Playwright trong một background thread có event loop riêng.
    Thread start loop.run_forever() → các coroutine được submit qua
    asyncio.run_coroutine_threadsafe().
    """
    status_signal  = Signal(str)
    chunk_signal   = Signal(str)
    done_signal    = Signal(str)
    error_signal   = Signal(str)
    login_needed   = Signal()
    login_ok       = Signal()
    browser_closed = Signal()
    task_cancelled = Signal(str)

    def __init__(self):
        super().__init__()
        self._loop: asyncio.AbstractEventLoop = None
        self._thread: threading.Thread = None
        self._client = None
        self._ready = False
        self._current_future = None
        self._start_event_loop()   # ← khởi động ngay khi tạo

    # ── Event loop management ────────────────────────────────────────────────

    def _start_event_loop(self):
        """Tạo thread riêng chạy asyncio event loop mãi mãi."""
        self._loop = asyncio.new_event_loop()

        def run_loop():
            asyncio.set_event_loop(self._loop)
            self._loop.run_forever()

        self._thread = threading.Thread(target=run_loop, daemon=True, name="GeminiEventLoop")
        self._thread.start()

    def _submit(self, coro):
        """Submit coroutine vào event loop và trả về Future."""
        return asyncio.run_coroutine_threadsafe(coro, self._loop)

    def _run_sync(self, coro, timeout=120):
        """Submit và chờ kết quả (blocking, dùng trong worker threads)."""
        return self._submit(coro).result(timeout=timeout)

    # ── Public actions (gọi từ UI thread qua threading.Thread) ──────────────

    def open_browser(self, headless: bool = True, profile_dir: str = "Default"):
        from src.gemini.gemini_web_client import GeminiWebClient
        try:
            self.status_signal.emit(f"🌐 Đang mở Chrome (profile: {profile_dir})...")
            self._client = GeminiWebClient(profile_dir=profile_dir, headless=headless)
            self.status_signal.emit("🔧 Đang khởi động Playwright...")
            self._run_sync(self._client.start(), timeout=60)
            self.status_signal.emit("🔍 Đang điều hướng đến Gemini...")
            logged_in = self._run_sync(self._client.navigate_to_gemini(), timeout=60)
            if logged_in:
                self._ready = True
                self.login_ok.emit()
                self.status_signal.emit("✅ Sẵn sàng chat với Gemini!")
                try:
                    from src.english_learning_app.modules.ai_module import set_gemini
                    set_gemini(self._client, self._loop)
                except Exception as _e:
                    print(f"set_gemini warning: {_e}")
            else:
                self.login_needed.emit()
                self.status_signal.emit("⚠️ Vui lòng đăng nhập Google trong browser...")
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            # Hiển thị 3 dòng cuối của traceback để dễ debug
            short_tb = "\n".join(tb.strip().splitlines()[-6:])
            self.error_signal.emit(f"Lỗi mở browser:\n{short_tb}")

    def wait_for_login(self):
        try:
            ok = self._run_sync(self._client.wait_for_login(timeout_seconds=180), timeout=200)
            if ok:
                self._ready = True
                self.login_ok.emit()
                self.status_signal.emit("✅ Đăng nhập thành công!")
            else:
                self.error_signal.emit("Hết thời gian chờ đăng nhập (3 phút)")
        except Exception as e:
            self.error_signal.emit(f"Lỗi chờ login: {e}")

    def send_message(self, message: str):
        if not self._ready or not self._client:
            self.error_signal.emit("Chưa kết nối! Mở browser trước.")
            return
        try:
            self.status_signal.emit("⏳ Đang gửi tin nhắn...")

            async def _do_stream():
                full = ""
                async for chunk in self._client.stream_response(message):
                    self.chunk_signal.emit(chunk)
                    full += chunk
                return full

            self._current_future = self._submit(_do_stream())
            full = self._current_future.result(timeout=120)
            self._current_future = None
            self.done_signal.emit(full)
            self.status_signal.emit("✅ Gemini đã trả lời")
        except Exception as e:
            if self._current_future and self._current_future.cancelled():
                self._current_future = None
                self.task_cancelled.emit("Gemini task cancelled.")
                self.status_signal.emit("Gemini task cancelled.")
                return
            self._current_future = None
            err_str = str(e)
            # Phát hiện browser bị đóng thủ công — reset trạng thái thay vì báo lỗi
            browser_closed_keywords = [
                "Target page, context or browser has been closed",
                "Browser has been closed",
                "Connection closed",
                "Target closed",
                "page has been closed",
            ]
            if any(k.lower() in err_str.lower() for k in browser_closed_keywords):
                self._ready = False
                self._client = None
                self.browser_closed.emit()
                try:
                    from src.english_learning_app.modules.ai_module import clear_gemini
                    clear_gemini()
                except Exception:
                    pass
                self.status_signal.emit("🔴 Browser đã bị đóng")
            else:
                self.error_signal.emit(f"Lỗi gửi tin: {e}")

    def new_conversation(self):
        if not self._client:
            return
        try:
            self._run_sync(self._client.new_conversation())
            self.status_signal.emit("🔄 New conversation started")
        except Exception as e:
            self.error_signal.emit(f"Lỗi new chat: {e}")

    def cancel_current_task(self):
        cancelled = False
        had_stream_future = False
        try:
            if self._current_future and not self._current_future.done():
                had_stream_future = True
                self._current_future.cancel()
                cancelled = True
        except Exception:
            pass
        try:
            from src.english_learning_app.modules.ai_module import cancel_web_job
            cancelled = cancel_web_job() or cancelled
        except Exception:
            pass
        if cancelled:
            if not had_stream_future:
                self.task_cancelled.emit("Gemini task cancelled.")
            self.status_signal.emit("Gemini task cancelled.")
        else:
            self.status_signal.emit("No Gemini Web task is running.")

    def refresh_browser(self, headless: bool = True, profile_dir: str = "Default"):
        self.cancel_current_task()
        self.close_browser()
        self.open_browser(headless=headless, profile_dir=profile_dir)

    def restart_runtime(self, headless: bool = True, profile_dir: str = "Default"):
        self.cancel_current_task()
        try:
            if self._client:
                self._run_sync(self._client.stop(), timeout=10)
        except Exception:
            pass
        self._client = None
        self._ready = False
        try:
            if self._loop and self._loop.is_running():
                self._loop.call_soon_threadsafe(self._loop.stop)
        except Exception:
            pass
        self._start_event_loop()
        self.open_browser(headless=headless, profile_dir=profile_dir)

    def close_browser(self):
        if self._client:
            try:
                self._run_sync(self._client.stop(), timeout=10)
            except Exception:
                pass
            self._client = None
            self._ready = False
        self.browser_closed.emit()
        self.status_signal.emit("🔴 Browser đã đóng")

    def take_screenshot(self, path: str):
        if not self._client:
            return
        try:
            saved = self._run_sync(self._client.take_screenshot(path), timeout=15)
            self.status_signal.emit(f"📸 Đã lưu: {saved}")
        except Exception as e:
            self.error_signal.emit(f"Lỗi screenshot: {e}")


# ─── UI Tab ──────────────────────────────────────────────────────────────────

class GeminiWebTab(QWidget):
    def __init__(self, signals):
        super().__init__()
        self.signals = signals
        self._worker = GeminiWorker()   # event loop đã chạy
        self._messages = []
        self._active_reply_index = None
        self._request_timer = QTimer(self)
        self._request_timer.setSingleShot(True)
        self._request_timer.timeout.connect(self._on_request_timeout)

        self._connect_signals()
        self._setup_ui()


    def _connect_signals(self):
        self._worker.status_signal.connect(self.signals.status_changed)
        self._worker.chunk_signal.connect(self._on_chunk)
        self._worker.done_signal.connect(self._on_done)
        self._worker.error_signal.connect(self._on_error)
        self._worker.login_needed.connect(self._on_login_needed)
        self._worker.login_ok.connect(self._on_login_ok)
        self._worker.browser_closed.connect(self._on_browser_closed)
        self._worker.task_cancelled.connect(self._on_task_cancelled)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        # ── Browser Control ──
        ctrl_group = QGroupBox("🌐 Gemini Web Browser Control")
        ctrl_layout = QHBoxLayout(ctrl_group)

        self.open_btn = QPushButton("🚀 Open Browser & Login")
        self.open_btn.setFixedHeight(36)
        self.open_btn.setStyleSheet(
            "QPushButton{background:#27ae60;color:white;border-radius:6px;"
            "font-weight:bold;font-size:11pt;padding:0 16px;}"
            "QPushButton:hover{background:#2ecc71;}")
        self.open_btn.clicked.connect(self._open_browser)
        ctrl_layout.addWidget(self.open_btn)

        self.headless_cb = QCheckBox("Headless")
        self.headless_cb.setToolTip("Hide the browser window")
        self.headless_cb.setChecked(True)
        ctrl_layout.addWidget(self.headless_cb)

        ctrl_layout.addSpacing(8)

        self.new_chat_btn = QPushButton("🔄 New Chat")
        self.new_chat_btn.setFixedHeight(36)
        self.new_chat_btn.setEnabled(False)
        self.new_chat_btn.clicked.connect(self._new_conversation)
        ctrl_layout.addWidget(self.new_chat_btn)

        self.cancel_btn = QPushButton("Cancel Task")
        self.cancel_btn.setFixedHeight(36)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel_task)
        ctrl_layout.addWidget(self.cancel_btn)

        self.refresh_btn = QPushButton("Refresh Browser")
        self.refresh_btn.setFixedHeight(36)
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.clicked.connect(self._refresh_browser)
        ctrl_layout.addWidget(self.refresh_btn)

        self.restart_btn = QPushButton("Restart Runtime")
        self.restart_btn.setFixedHeight(36)
        self.restart_btn.setEnabled(False)
        self.restart_btn.clicked.connect(self._restart_runtime)
        ctrl_layout.addWidget(self.restart_btn)

        self.screenshot_btn = QPushButton("📸 Screenshot")
        self.screenshot_btn.setFixedHeight(36)
        self.screenshot_btn.setEnabled(False)
        self.screenshot_btn.clicked.connect(self._take_screenshot)
        ctrl_layout.addWidget(self.screenshot_btn)

        self.open_folder_btn = QPushButton("📂 Open Folder")
        self.open_folder_btn.setFixedHeight(36)
        self.open_folder_btn.setToolTip("Mở thư mục chứa ảnh screenshot")
        self.open_folder_btn.clicked.connect(self._open_screenshot_folder)
        ctrl_layout.addWidget(self.open_folder_btn)

        ctrl_layout.addStretch()

        self.close_btn = QPushButton("❌ Close Browser")
        self.close_btn.setFixedHeight(36)
        self.close_btn.setEnabled(False)
        self.close_btn.setStyleSheet(
            "QPushButton{background:#c0392b;color:white;border-radius:6px;padding:0 12px;}"
            "QPushButton:disabled{background:#333;color:#666;}")
        self.close_btn.clicked.connect(self._close_browser)
        ctrl_layout.addWidget(self.close_btn)
        layout.addWidget(ctrl_group)

        # ── Status Banner ──
        self.status_banner = QLabel("🔴 Browser chưa mở  |  Nhấn 'Open Browser' để bắt đầu")
        self.status_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_banner.setFixedHeight(32)
        self.status_banner.setStyleSheet(
            "background:#1a1a2e;color:#e74c3c;border-radius:6px;"
            "font-weight:bold;padding:4px;font-size:10pt;")
        layout.addWidget(self.status_banner)

        # ── Login waiting panel ──
        self.login_panel = QFrame()
        self.login_panel.setStyleSheet(
            "QFrame{background:#2a1a00;border:2px solid #f39c12;border-radius:8px;padding:12px;}")
        login_layout = QVBoxLayout(self.login_panel)
        login_info = QLabel(
            "⚠️  <b>Chưa đăng nhập Google</b><br><br>"
            "Chrome đã mở. Hãy:<br>"
            "1. Đăng nhập tài khoản Google trong browser<br>"
            "2. Truy cập <b>gemini.google.com</b><br>"
            "3. App sẽ tự động tiếp tục khi bạn đăng nhập xong")
        login_info.setTextFormat(Qt.TextFormat.RichText)
        login_info.setStyleSheet("color:#f39c12;font-size:11pt;")
        login_layout.addWidget(login_info)
        wait_prog = QProgressBar()
        wait_prog.setRange(0, 0)
        wait_prog.setFixedHeight(6)
        wait_prog.setStyleSheet(
            "QProgressBar{border:none;background:#333;border-radius:3px;}"
            "QProgressBar::chunk{background:#f39c12;border-radius:3px;}")
        login_layout.addWidget(wait_prog)
        self.login_panel.hide()
        layout.addWidget(self.login_panel)

        # ── Chat Display ──
        self.chat_display = QTextBrowser()
        self.chat_display.setReadOnly(True)
        self.chat_display.setFont(QFont("Segoe UI", 11))
        self.chat_display.setStyleSheet(
            "QTextBrowser{background:#0d1117;color:#e6edf3;"
            "border-radius:8px;padding:8px 10px;border:1px solid #21262d;}"
            "QScrollBar:vertical{background:#0d1117;width:12px;margin:6px 0;}"
            "QScrollBar::handle:vertical{background:#30363d;min-height:28px;border-radius:6px;}"
            "QScrollBar::handle:vertical:hover{background:#484f58;}"
            "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}"
            "QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical{background:transparent;}")
        self.chat_display.document().setDocumentMargin(14)
        self.chat_display.setOpenExternalLinks(True)
        layout.addWidget(self.chat_display, stretch=1)

        # ── Input Area ──
        input_frame = QFrame()
        input_frame.setStyleSheet(
            "QFrame{background:#161b22;border-radius:10px;border:1px solid #30363d;}")
        input_layout = QHBoxLayout(input_frame)
        input_layout.setContentsMargins(8, 8, 8, 8)

        self.msg_input = QTextEdit()
        self.msg_input.setFixedHeight(90)
        self.msg_input.setPlaceholderText(
            "💬 Nhập tin nhắn gửi Gemini Web...  (Ctrl+Enter để gửi)\n\n"
            "Lưu ý: Cần mở browser và đăng nhập trước")
        self.msg_input.setFont(QFont("Segoe UI", 11))
        self.msg_input.setStyleSheet(
            "QTextEdit{background:transparent;color:#e6edf3;border:none;}")
        input_layout.addWidget(self.msg_input)

        self.send_btn = QPushButton("Send\n▶")
        self.send_btn.setFixedSize(72, 90)
        self.send_btn.setEnabled(False)
        self.send_btn.setStyleSheet(
            "QPushButton{background:#238636;color:white;border-radius:8px;"
            "font-size:14px;font-weight:bold;}"
            "QPushButton:hover{background:#2ea043;}"
            "QPushButton:disabled{background:#21262d;color:#484f58;}")
        self.send_btn.clicked.connect(self._send_message)
        input_layout.addWidget(self.send_btn)
        layout.addWidget(input_frame)

        # Ctrl+Enter shortcut
        sc = QShortcut(QKeySequence("Ctrl+Return"), self)
        sc.activated.connect(self._send_message)

    # ── Actions ─────────────────────────────────────────────────────────────

    def _open_browser(self):
        self.open_btn.setEnabled(False)
        self._set_status("⏳ Đang mở Chrome...", "#f39c12", "#2a1a00")
        headless = self.headless_cb.isChecked()
        threading.Thread(target=self._worker.open_browser,
                         args=(headless,), daemon=True).start()

    def _send_message(self):
        msg = self.msg_input.toPlainText().strip()
        if not msg:
            return
        self.msg_input.clear()
        self.send_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self._request_timer.start(90000)
        self._append_msg("You", msg, "#58a6ff")
        self._active_reply_index = self._append_msg("Gemini", "", "#3fb950")
        threading.Thread(target=self._worker.send_message,
                         args=(msg,), daemon=True).start()

    def _new_conversation(self):
        self._messages.clear()
        self._active_reply_index = None
        self._render_chat()
        threading.Thread(target=self._worker.new_conversation, daemon=True).start()

    def _close_browser(self):
        self._request_timer.stop()
        threading.Thread(target=self._worker.close_browser, daemon=True).start()

    def _cancel_task(self):
        threading.Thread(target=self._worker.cancel_current_task, daemon=True).start()

    def _refresh_browser(self):
        self._request_timer.stop()
        self.cancel_btn.setEnabled(False)
        self.send_btn.setEnabled(False)
        headless = self.headless_cb.isChecked()
        threading.Thread(target=self._worker.refresh_browser, args=(headless,), daemon=True).start()

    def _restart_runtime(self):
        self._request_timer.stop()
        self.cancel_btn.setEnabled(False)
        self.send_btn.setEnabled(False)
        headless = self.headless_cb.isChecked()
        threading.Thread(target=self._worker.restart_runtime, args=(headless,), daemon=True).start()

    def _take_screenshot(self):
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        # Lưu vào thư mục screenshots trong project
        import os
        from pathlib import Path
        project_root = Path(__file__).parent.parent.parent
        screenshots_dir = project_root / "screenshots"
        screenshots_dir.mkdir(exist_ok=True)
        path = str(screenshots_dir / f"gemini_{ts}.png")
        threading.Thread(target=self._worker.take_screenshot,
                         args=(path,), daemon=True).start()

    def _open_screenshot_folder(self):
        """Mở thư mục screenshots trong File Explorer."""
        import os, subprocess
        from pathlib import Path
        project_root = Path(__file__).parent.parent.parent
        screenshots_dir = project_root / "screenshots"
        screenshots_dir.mkdir(exist_ok=True)
        subprocess.Popen(f'explorer "{screenshots_dir}"')

    # ── Slots ────────────────────────────────────────────────────────────────

    def _on_login_needed(self):
        self.login_panel.show()
        self._set_status("⚠️ Chờ đăng nhập Google...", "#f39c12", "#2a1a00")
        threading.Thread(target=self._worker.wait_for_login, daemon=True).start()

    def _on_login_ok(self):
        self.login_panel.hide()
        self.send_btn.setEnabled(True)
        self.new_chat_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.refresh_btn.setEnabled(True)
        self.restart_btn.setEnabled(True)
        self.screenshot_btn.setEnabled(True)
        self.close_btn.setEnabled(True)
        self.open_btn.setEnabled(False)
        self._set_status(
            "✅ Đã kết nối Gemini Web  |  Ctrl+Enter để gửi tin nhắn",
            "#3fb950", "#0d2818")
        self._append_system(
            "🟢 Kết nối thành công! Đang chat với Gemini.google.com\n"
            "Không cần API key — dùng tài khoản Google của bạn.")

    def _on_browser_closed(self):
        self._request_timer.stop()
        self.send_btn.setEnabled(False)
        self.new_chat_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        self.refresh_btn.setEnabled(False)
        self.restart_btn.setEnabled(False)
        self.screenshot_btn.setEnabled(False)
        self.close_btn.setEnabled(False)
        self.open_btn.setEnabled(True)
        self._active_reply_index = None
        self.login_panel.hide()
        self._set_status(
            "🔴 Browser đã đóng  |  Nhấn 'Open Browser' để mở lại",
            "#e74c3c", "#1a1a2e")

    def _on_chunk(self, chunk: str):
        if self._active_reply_index is None:
            self._active_reply_index = self._append_msg("Gemini", "", "#3fb950")
        self._messages[self._active_reply_index]["text"] += chunk
        self._render_chat()

    def _on_done(self, _full: str):
        self._request_timer.stop()
        self.send_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self._active_reply_index = None

    def _on_error(self, error: str):
        self._request_timer.stop()
        self.send_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.open_btn.setEnabled(True)
        self._active_reply_index = None
        self._append_system(f"❌ Lỗi: {error}")
        self.signals.status_changed.emit(f"❌ {error}")

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _on_task_cancelled(self, text: str):
        self._request_timer.stop()
        self.send_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self._active_reply_index = None
        self._append_system(text)
        self.signals.status_changed.emit(text)

    def _on_request_timeout(self):
        self._append_system("Gemini Web is taking too long. Cancelling the current task...")
        self.signals.status_changed.emit("Gemini Web is taking too long. Cancelling the current task...")
        self._cancel_task()

    def _set_status(self, text: str, color: str, bg: str):
        self.status_banner.setText(text)
        self.status_banner.setStyleSheet(
            f"background:{bg};color:{color};border-radius:6px;"
            f"font-weight:bold;padding:4px;font-size:10pt;")

    def _append_msg(self, sender: str, text: str, color: str):
        self._messages.append({
            "kind": "chat",
            "sender": sender,
            "text": text,
            "color": color,
        })
        self._render_chat()
        return len(self._messages) - 1

    def _append_system(self, text: str):
        self._messages.append({
            "kind": "system",
            "text": text,
        })
        self._render_chat()

    def _render_chat(self):
        parts = ['<div style="font-family:\'Segoe UI\'; font-size:11pt;">']
        for item in self._messages:
            if item["kind"] == "system":
                parts.append(
                    '<div style="margin:10px 0 16px 0; color:#8b949e; '
                    'font-style:italic; line-height:1.55;">'
                    f'{self._format_text(item["text"])}'
                    '</div>'
                )
                continue

            is_user = item["sender"] == "You"
            bubble_bg = "#13243a" if is_user else "#161b22"
            border = "#1f6feb" if is_user else "#2ea043"
            badge_bg = "#0f3d75" if is_user else "#0f5323"
            parts.append(
                '<div style="margin:0 0 16px 0;">'
                f'<div style="margin-bottom:6px; color:{item["color"]}; font-weight:700;">'
                f'{html.escape(item["sender"])}'
                '</div>'
                f'<div style="background:{bubble_bg}; border:1px solid {border}; '
                'border-radius:12px; padding:12px 14px; line-height:1.6;">'
                f'<div style="margin-bottom:8px; display:inline-block; padding:3px 8px; '
                f'background:{badge_bg}; color:#f0f6fc; border-radius:999px; '
                'font-size:9pt; font-weight:700;">'
                f'{html.escape(item["sender"])}'
                '</div>'
                f'{self._format_text(item["text"])}'
                '</div>'
                '</div>'
            )

        parts.append("</div>")
        self.chat_display.setHtml("".join(parts))
        scrollbar = self.chat_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _format_text(self, text: str) -> str:
        escaped = html.escape(text)
        escaped = escaped.replace("\n", "<br>")
        return f'<div style="white-space:pre-wrap;">{escaped}</div>'


