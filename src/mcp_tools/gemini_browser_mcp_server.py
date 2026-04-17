"""
MCP Server cho Gemini Web Browser
Expose Gemini web chat qua MCP protocol
Tools: open_gemini, chat_gemini, new_conversation, screenshot
"""
import asyncio
import json
import logging
from typing import Any
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

from src.gemini.gemini_web_client import GeminiWebClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Server("gemini-browser")
_client: GeminiWebClient = None


async def get_client(headless: bool = False) -> GeminiWebClient:
    global _client
    if _client is None or not await _client.is_alive():
        _client = GeminiWebClient(headless=headless)
        await _client.start()
    return _client


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="open_gemini",
            description="Mở Gemini.google.com trong Chrome. Nếu chưa đăng nhập, browser sẽ hiện để user login.",
            inputSchema={
                "type": "object",
                "properties": {
                    "headless": {"type": "boolean", "description": "Ẩn browser (False = hiện browser)", "default": False},
                    "wait_for_login": {"type": "boolean", "description": "Chờ user đăng nhập", "default": True}
                }
            }
        ),
        types.Tool(
            name="chat_gemini",
            description="Gửi tin nhắn tới Gemini trên web và nhận phản hồi.",
            inputSchema={
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Tin nhắn gửi cho Gemini"},
                    "timeout_seconds": {"type": "integer", "description": "Thời gian chờ phản hồi (giây)", "default": 60}
                },
                "required": ["message"]
            }
        ),
        types.Tool(
            name="new_conversation",
            description="Bắt đầu cuộc hội thoại mới với Gemini.",
            inputSchema={"type": "object", "properties": {}}
        ),
        types.Tool(
            name="take_screenshot",
            description="Chụp màn hình trạng thái hiện tại của Gemini.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Đường dẫn lưu ảnh", "default": "gemini_screenshot.png"}
                }
            }
        ),
        types.Tool(
            name="close_browser",
            description="Đóng browser Gemini.",
            inputSchema={"type": "object", "properties": {}}
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    global _client
    try:
        if name == "open_gemini":
            headless = arguments.get("headless", False)
            wait_login = arguments.get("wait_for_login", True)

            _client = GeminiWebClient(headless=headless)
            await _client.start()
            logged_in = await _client.navigate_to_gemini()

            if not logged_in and wait_login:
                logged_in = await _client.wait_for_login(timeout_seconds=120)

            status = "✅ Đã đăng nhập và sẵn sàng chat!" if logged_in else "⚠️ Chưa đăng nhập. Hãy login trong browser."
            return [types.TextContent(type="text", text=json.dumps({"success": logged_in, "status": status}))]

        elif name == "chat_gemini":
            if not _client or not await _client.is_alive():
                return [types.TextContent(type="text", text=json.dumps({
                    "success": False, "error": "Browser chưa mở. Gọi open_gemini trước!"
                }))]

            message = arguments["message"]
            timeout = arguments.get("timeout_seconds", 60) * 1000
            response = await _client.chat(message)
            return [types.TextContent(type="text", text=json.dumps({
                "success": True,
                "message": message,
                "response": response
            }, ensure_ascii=False))]

        elif name == "new_conversation":
            if not _client:
                return [types.TextContent(type="text", text='{"success": false, "error": "Browser chưa mở"}')]
            await _client.new_conversation()
            return [types.TextContent(type="text", text='{"success": true, "status": "New conversation started"}')]

        elif name == "take_screenshot":
            if not _client:
                return [types.TextContent(type="text", text='{"success": false, "error": "Browser chưa mở"}')]
            path = arguments.get("path", "gemini_screenshot.png")
            saved = await _client.take_screenshot(path)
            return [types.TextContent(type="text", text=json.dumps({"success": True, "path": saved}))]

        elif name == "close_browser":
            if _client:
                await _client.stop()
                _client = None
            return [types.TextContent(type="text", text='{"success": true, "status": "Browser closed"}')]

        else:
            return [types.TextContent(type="text", text=f'{{"error": "Unknown tool: {name}"}}'  )]

    except Exception as e:
        logger.exception(f"Tool error: {name}")
        return [types.TextContent(type="text", text=json.dumps({"success": False, "error": str(e)}))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
