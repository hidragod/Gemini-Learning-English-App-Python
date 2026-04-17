"""
MCP Server cho Scrapling Browser - lazy import
"""
import asyncio
import json
import logging
from typing import Any
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Server("scrapling-browser")


def get_crawler():
    from src.crawler.crawler import WebCrawler
    return WebCrawler()


def get_browser_crawler():
    from src.crawler.crawler import BrowserCrawler
    return BrowserCrawler()


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(name="fetch_webpage",
            description="Fetch nội dung trang web (HTML + text).",
            inputSchema={"type":"object","properties":{"url":{"type":"string"},"stealth":{"type":"boolean","default":False}},"required":["url"]}),
        types.Tool(name="fetch_with_browser",
            description="Fetch trang có JavaScript dùng Playwright.",
            inputSchema={"type":"object","properties":{"url":{"type":"string"},"headless":{"type":"boolean","default":True}},"required":["url"]}),
        types.Tool(name="extract_text",
            description="Trích xuất toàn bộ text từ trang web.",
            inputSchema={"type":"object","properties":{"url":{"type":"string"}},"required":["url"]}),
        types.Tool(name="extract_links",
            description="Lấy tất cả links từ trang web.",
            inputSchema={"type":"object","properties":{"url":{"type":"string"},"filter_domain":{"type":"string"}},"required":["url"]}),
        types.Tool(name="css_selector_query",
            description="Tìm elements bằng CSS selector.",
            inputSchema={"type":"object","properties":{"url":{"type":"string"},"selector":{"type":"string"}},"required":["url","selector"]}),
        types.Tool(name="extract_tables",
            description="Trích xuất bảng dữ liệu từ trang web.",
            inputSchema={"type":"object","properties":{"url":{"type":"string"}},"required":["url"]}),
        types.Tool(name="search_english_content",
            description="Crawl trang web và trích xuất nội dung tiếng Anh.",
            inputSchema={"type":"object","properties":{"url":{"type":"string"},"content_type":{"type":"string","enum":["article","vocabulary","grammar","story"]}},"required":["url"]}),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    try:
        crawler = get_crawler()

        if name == "fetch_webpage":
            stealth = arguments.get("stealth", False)
            result = crawler.fetch_stealth(arguments["url"]) if stealth else crawler.fetch(arguments["url"])
            return [types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

        elif name == "fetch_with_browser":
            result = get_browser_crawler().fetch_with_js(arguments["url"], arguments.get("headless", True))
            return [types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

        elif name == "extract_text":
            result = crawler.fetch(arguments["url"])
            return [types.TextContent(type="text", text=result.get("text","") if result["success"] else result.get("error",""))]

        elif name == "extract_links":
            result = crawler.fetch(arguments["url"])
            if not result["success"]:
                return [types.TextContent(type="text", text=f"Error: {result['error']}")]
            links = result.get("links", [])
            if fd := arguments.get("filter_domain"):
                links = [l for l in links if fd in l]
            return [types.TextContent(type="text", text=json.dumps(links, ensure_ascii=False, indent=2))]

        elif name == "css_selector_query":
            result = crawler.fetch(arguments["url"])
            if not result["success"]:
                return [types.TextContent(type="text", text=f"Error: {result['error']}")]
            elements = crawler.search_elements(result["html"], arguments["selector"])
            return [types.TextContent(type="text", text=json.dumps(elements, ensure_ascii=False, indent=2))]

        elif name == "extract_tables":
            tables = crawler.extract_tables(arguments["url"])
            return [types.TextContent(type="text", text=json.dumps(tables, ensure_ascii=False, indent=2))]

        elif name == "search_english_content":
            result = crawler.fetch(arguments["url"])
            if not result["success"]:
                return [types.TextContent(type="text", text=f"Error: {result['error']}")]
            text = result.get("text", "")
            output = {"url": arguments["url"], "title": result.get("title",""),
                      "content_type": arguments.get("content_type","article"),
                      "text": text[:5000], "word_count": len(text.split())}
            return [types.TextContent(type="text", text=json.dumps(output, ensure_ascii=False, indent=2))]

        else:
            return [types.TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as e:
        logger.exception(f"Tool error: {name}")
        return [types.TextContent(type="text", text=f"Error: {str(e)}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
