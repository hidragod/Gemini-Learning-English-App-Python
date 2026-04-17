# Gemini AI + English Learning App

PySide6 desktop application tích hợp:
- 🤖 **Gemini AI Chat** với streaming response
- 📚 **English Learning** - học từ vựng, đọc, viết, ngữ pháp, nghe, nói với hỗ trợ AI
- 📖 **Vocabulary Bank** - lưu từ vựng từ bài học

## ✨ Features

- **Gemini Web Chat**: mở Gemini Web trong app, chat trực tiếp, tạo hội thoại mới, chụp screenshot và theo dõi trạng thái kết nối.
- **Learning Dashboard**: theo dõi streak, XP, words learned/reviewed, reading sessions và daily study plan.
- **Vocabulary Studio**:
  - Flashcards với phát âm TTS, AI word coach và metadata theo topic/level
  - General English Quiz tách riêng khỏi Study Quiz chuyên ngành
  - Study Quiz cho anatomy, physiology, microbiology, pathology và các study packs học thuật
  - Vocab Builder tạo bộ từ theo CEFR level, topic, batch size, preset học thuật và lưu trực tiếp vào thư viện từ vựng
- **Reading Practice**: tạo passage theo topic/level, dịch song song, kiểm tra bản dịch, click từ để giải nghĩa và lưu lịch sử đọc.
- **Writing Studio**: tạo writing plan, soạn draft, nhận feedback AI và lưu lịch sử bài viết.
- **Grammar Practice**: sinh câu hỏi từng bước, kiểm tra đáp án, lưu thư viện bài tập ngữ pháp.
- **Listening Practice**: nghe câu mẫu, nhập lại nội dung, so sánh sai khác, tải bộ câu từ JSON hoặc database library.
- **Speaking Lab**: tạo chủ đề nói theo level, phát audio shadowing, chat coaching với AI và xem lại lịch sử luyện nói.
- **Progress & DB Manager**: theo dõi tiến độ học và quản lý dữ liệu vocabulary/learning records trong app.

## 🚀 Quick Start

```bash
# 1. Chạy ứng dụng
uv run main.py
```

## 📁 Project Structure

```
PythonProject/
├── main.py                    # Entry point
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

## 📦 Dependencies

- `pyside6` - UI framework
- `playwright` - browser automation cho Gemini Web
- `python-dotenv` - Environment variables
