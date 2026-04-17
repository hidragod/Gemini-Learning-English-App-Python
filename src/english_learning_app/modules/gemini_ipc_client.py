"""
Gemini IPC Client — gọi từ English Learning App tới WebCrawlerGemini.
Blocking call qua socket localhost:47891.
"""
from __future__ import annotations
import socket
import json
import uuid
import time

PORT = 47891
TIMEOUT = 120  # giây


def ask(prompt: str, timeout: int = TIMEOUT) -> str:
    """
    Gửi prompt tới Gemini Web (qua IPC) và trả về response text.
    Ném RuntimeError nếu server chưa chạy hoặc có lỗi.
    """
    req_id = str(uuid.uuid4())[:8]
    payload = json.dumps({"id": req_id, "prompt": prompt}, ensure_ascii=False) + "\n"

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect(("127.0.0.1", PORT))
    except ConnectionRefusedError:
        raise RuntimeError(
            "Gemini Web chưa được mở.\n"
            "Vào WebCrawlerGemini → tab 'Gemini Web' → nhấn 'Open Browser' trước."
        )
    except OSError as e:
        raise RuntimeError(f"Không thể kết nối Gemini Web: {e}")

    try:
        sock.sendall(payload.encode("utf-8"))
        # Đọc response (newline-terminated)
        buf = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            buf += chunk
            if b"\n" in buf:
                break
        resp = json.loads(buf.decode("utf-8").strip())
        if "error" in resp:
            raise RuntimeError(resp["error"])
        return resp.get("text", "")
    finally:
        sock.close()


def is_available() -> bool:
    """Kiểm tra xem Gemini Web server có đang chạy không."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(("127.0.0.1", PORT))
        sock.close()
        return result == 0
    except Exception:
        return False
