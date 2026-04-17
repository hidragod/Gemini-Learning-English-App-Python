"""
MCP Python Client
Gọi các tool của MCP Server từ Python code
"""
import asyncio
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class ScraplingMCPClient:
    """Client kết nối đến Scrapling MCP Server"""

    def __init__(self, server_script: Optional[str] = None):
        # Tìm script mcp_server.py
        if server_script:
            self.server_script = server_script
        else:
            base = Path(__file__).parent.parent
            self.server_script = str(base / "mcp_tools" / "mcp_server.py")

        self._session: Optional[ClientSession] = None
        self._context = None

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *args):
        await self.disconnect()

    async def connect(self):
        python_exe = sys.executable
        params = StdioServerParameters(
            command=python_exe,
            args=[self.server_script],
            env=None
        )
        self._context = stdio_client(params)
        read, write = await self._context.__aenter__()
        self._session = ClientSession(read, write)
        await self._session.__aenter__()
        await self._session.initialize()

    async def disconnect(self):
        if self._session:
            await self._session.__aexit__(None, None, None)
        if self._context:
            await self._context.__aexit__(None, None, None)

    async def list_tools(self) -> list[dict]:
        result = await self._session.list_tools()
        return [{"name": t.name, "description": t.description} for t in result.tools]

    async def call_tool(self, tool_name: str, arguments: dict) -> str:
        result = await self._session.call_tool(tool_name, arguments)
        return "\n".join(c.text for c in result.content if hasattr(c, "text"))

    # --- Convenience methods ---

    async def fetch_webpage(self, url: str, stealth: bool = False) -> dict:
        raw = await self.call_tool("fetch_webpage", {"url": url, "stealth": stealth})
        return json.loads(raw)

    async def fetch_with_browser(self, url: str, headless: bool = True) -> dict:
        raw = await self.call_tool("fetch_with_browser", {"url": url, "headless": headless})
        return json.loads(raw)

    async def extract_text(self, url: str) -> str:
        return await self.call_tool("extract_text", {"url": url})

    async def extract_links(self, url: str, filter_domain: str = "") -> list:
        args: dict[str, Any] = {"url": url}
        if filter_domain:
            args["filter_domain"] = filter_domain
        raw = await self.call_tool("extract_links", args)
        return json.loads(raw)

    async def css_query(self, url: str, selector: str) -> list:
        raw = await self.call_tool("css_selector_query", {"url": url, "selector": selector})
        return json.loads(raw)

    async def extract_tables(self, url: str) -> list:
        raw = await self.call_tool("extract_tables", {"url": url})
        return json.loads(raw)

    async def get_english_content(self, url: str, content_type: str = "article") -> dict:
        raw = await self.call_tool("search_english_content",
                                    {"url": url, "content_type": content_type})
        return json.loads(raw)


# ---------- Synchronous wrapper ----------

class SyncScraplingClient:
    """Wrapper đồng bộ, dễ dùng hơn trong PySide6 threads"""

    def __init__(self, server_script: Optional[str] = None):
        self._async_client = ScraplingMCPClient(server_script)
        self._loop = asyncio.new_event_loop()

    def _run(self, coro):
        return self._loop.run_until_complete(coro)

    def connect(self):
        self._run(self._async_client.connect())

    def disconnect(self):
        self._run(self._async_client.disconnect())
        self._loop.close()

    def list_tools(self): return self._run(self._async_client.list_tools())
    def fetch_webpage(self, url, stealth=False): return self._run(self._async_client.fetch_webpage(url, stealth))
    def extract_text(self, url): return self._run(self._async_client.extract_text(url))
    def extract_links(self, url, domain=""): return self._run(self._async_client.extract_links(url, domain))
    def css_query(self, url, sel): return self._run(self._async_client.css_query(url, sel))
    def extract_tables(self, url): return self._run(self._async_client.extract_tables(url))
    def get_english_content(self, url, ctype="article"): return self._run(self._async_client.get_english_content(url, ctype))
