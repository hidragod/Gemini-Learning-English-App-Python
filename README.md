# Web Crawler + Gemini AI + English Learning App

PySide6 desktop application tích hợp:
- 🔍 **Web Crawler** bằng Scrapling (simple, stealth, Playwright JS)
- 🤖 **Gemini AI Chat** với streaming response
- 📚 **English Learning** - crawl bài viết + phân tích bằng AI
- 🔌 **MCP Server** cho Scrapling (dùng với Claude Desktop)
- 📖 **Vocabulary Bank** - lưu từ vựng từ bài học

## 🚀 Quick Start

```bash
# 1. Copy .env.example -> .env và điền API key
cp .env.example .env

# 2. Chạy ứng dụng
uv run main.py

# 3. Hoặc chạy MCP server riêng
uv run run_mcp_server.py

# 4. Test MCP client
uv run test_mcp_client.py
```

## 📁 Project Structure

```
PythonProject/
├── main.py                    # Entry point
├── run_mcp_server.py          # Chạy MCP server (stdio)
├── test_mcp_client.py         # Test MCP client
├── .env                       # API keys (tạo từ .env.example)
├── src/
│   ├── crawler/
│   │   └── crawler.py         # WebCrawler, BrowserCrawler (Scrapling)
│   ├── gemini/
│   │   └── gemini_client.py   # GeminiClient (stream, analyze)
│   ├── mcp_tools/
│   │   ├── mcp_server.py      # MCP Server expose 7 crawler tools
│   │   └── mcp_client.py      # Python client gọi MCP tools
│   ├── ui/
│   │   ├── main_window.py     # MainWindow (3 tabs)
│   │   ├── crawler_tab.py     # Tab: Web Crawler UI
│   │   ├── gemini_tab.py      # Tab: Gemini Chat UI
│   │   ├── english_tab.py     # Tab: English Learning UI
│   │   └── settings_dialog.py # Dialog cài đặt API key
│   └── english_app/
│       └── integration.py     # VocabularyBank, EnglishAppIntegration
└── vocabulary_bank.json       # Dữ liệu từ vựng (tự tạo khi dùng)
```

## 🔌 MCP Server Tools

| Tool | Mô tả |
|------|-------|
| `fetch_webpage` | Fetch HTML + text trang tĩnh |
| `fetch_with_browser` | Fetch trang có JS (Playwright) |
| `extract_text` | Chỉ lấy text thuần |
| `extract_links` | Lấy tất cả links |
| `css_selector_query` | Query elements bằng CSS |
| `extract_tables` | Trích xuất bảng dữ liệu |
| `search_english_content` | Crawl bài học tiếng Anh |

## ⚙️ Tích hợp Claude Desktop

Thêm vào `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "scrapling": {
      "command": "uv",
      "args": ["run", "run_mcp_server.py"],
      "cwd": "C:/Users/hipy/Desktop/ProjectRoot/PythonProject"
    }
  }
}
```

## 🔑 API Keys

- **Gemini**: https://aistudio.google.com/app/apikey
- Sau khi có key, mở app → File → Settings → nhập key

## 📦 Dependencies

- `pyside6` - UI framework
- `scrapling` - Web crawler (stealth + Playwright)
- `google-generativeai` - Gemini AI
- `mcp` - Model Context Protocol
- `python-dotenv` - Environment variables
