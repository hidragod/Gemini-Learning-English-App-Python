"""
Test MCP Client - chạy để kiểm tra kết nối MCP Server + tools
Run: uv run test_mcp_client.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


async def main():
    from src.mcp_tools.mcp_client import ScraplingMCPClient

    print("🔌 Connecting to Scrapling MCP Server...")

    async with ScraplingMCPClient() as client:
        # List tools
        tools = await client.list_tools()
        print(f"\n✅ Connected! Available tools ({len(tools)}):")
        for t in tools:
            print(f"  • {t['name']}: {t['description'][:60]}")

        # Test fetch
        print("\n🌐 Testing fetch_webpage...")
        result = await client.fetch_webpage("https://httpbin.org/get")
        if result.get("success"):
            print(f"  ✅ Status: {result.get('status')}")
            print(f"  Text preview: {result.get('text', '')[:100]}")
        else:
            print(f"  ❌ Error: {result.get('error')}")

        # Test extract_links
        print("\n🔗 Testing extract_links on example.com...")
        links = await client.extract_links("https://example.com")
        print(f"  Found {len(links)} links: {links[:3]}")

        print("\n✅ All tests passed!")


if __name__ == "__main__":
    asyncio.run(main())
