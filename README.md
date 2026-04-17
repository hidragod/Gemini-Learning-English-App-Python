# Gemini AI + English Learning App

PySide6 desktop application tích hợp:
- 🤖 **Gemini AI Chat** với streaming response
- 📚 **English Learning** - học từ vựng, đọc, viết, ngữ pháp, nghe, nói với hỗ trợ AI
- 📖 **Vocabulary Bank** - lưu từ vựng từ bài học

## 🚀 Quick Start

```bash
# 1. Copy .env.example -> .env và điền API key
cp .env.example .env

# 2. Chạy ứng dụng
uv run main.py
```

## 📁 Project Structure

```
PythonProject/
├── main.py                    # Entry point
├── .env                       # API keys (tạo từ .env.example)
├── src/
│   ├── gemini/
│   │   └── gemini_web_client.py   # Gemini Web bridge / browser client
│   ├── ui/
│   │   ├── main_window.py     # MainWindow
│   │   ├── gemini_web_tab.py  # Gemini Web chat tab
│   │   └── splash_screen.py   # Splash screen
│   └── english_learning_app/
│       ├── modules/           # DB, AI bridge, TTS
│       └── ui/                # Dashboard, Vocabulary, Reading, Writing, Grammar...
└── vocabulary_bank.json       # Dữ liệu từ vựng (tự tạo khi dùng)
```

## 🔑 API Keys

- **Gemini**: https://aistudio.google.com/app/apikey
- Sau khi có key, mở app → File → Settings → nhập key

## 📦 Dependencies

- `pyside6` - UI framework
- `playwright` - browser automation cho Gemini Web
- `mcp` - Model Context Protocol
- `python-dotenv` - Environment variables
