"""
Gemini IPC Server — lắng nghe kết nối từ English Learning App.
Chạy trong cùng process với GeminiWebClient.
Port: 47891 (localhost only)
Protocol: newline-delimited JSON
  Request:  {"id": "...", "prompt": "..."}
  Response: {"id": "...", "text": "..."} hoặc {"id": "...", "error": "..."}
"""
from __future__ import annotations
import asyncio
import json
import logging

logger = logging.getLogger(__name__)

PORT = 47891
_server: asyncio.Server | None = None
_client_ref = None   # GeminiWebClient instance


def set_gemini_client(client):
    global _client_ref
    _client_ref = client


def clear_gemini_client():
    global _client_ref
    _client_ref = None


async def _handle_connection(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    addr = writer.get_extra_info("peername")
    logger.debug(f"IPC: kết nối từ {addr}")
    try:
        while True:
            line = await reader.readline()
            if not line:
                break
            try:
                req = json.loads(line.decode("utf-8").strip())
                req_id = req.get("id", "0")
                prompt = req.get("prompt", "")

                if _client_ref is None:
                    resp = {"id": req_id, "error": "Gemini Web chưa sẵn sàng. Nhấn Open Browser trước."}
                else:
                    try:
                        full = ""
                        async for chunk in _client_ref.stream_response(prompt):
                            full += chunk
                        resp = {"id": req_id, "text": full}
                    except Exception as e:
                        resp = {"id": req_id, "error": str(e)}

                writer.write((json.dumps(resp, ensure_ascii=False) + "\n").encode("utf-8"))
                await writer.drain()

            except json.JSONDecodeError:
                pass
    except (asyncio.IncompleteReadError, ConnectionResetError):
        pass
    finally:
        writer.close()


async def start_server(loop: asyncio.AbstractEventLoop):
    global _server
    try:
        _server = await asyncio.start_server(_handle_connection, "127.0.0.1", PORT)
        logger.info(f"Gemini IPC server listening on 127.0.0.1:{PORT}")
    except OSError as e:
        logger.warning(f"IPC server không start được: {e}")


async def stop_server():
    global _server
    if _server:
        _server.close()
        await _server.wait_closed()
        _server = None
