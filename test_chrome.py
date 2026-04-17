"""
Test script - chạy file này để xem lỗi Chrome chi tiết
Chạy bằng: uv run python test_chrome.py
"""
import asyncio
import sys
import traceback
sys.path.insert(0, '.')

from src.gemini.gemini_web_client import GeminiWebClient, find_chrome
from pathlib import Path

print("=" * 60)
print("CHROME TEST")
print("=" * 60)

chrome_exe = find_chrome()
print(f"[1] Chrome exe: {chrome_exe}")

project_root = Path(__file__).parent
user_data_dir = project_root / "chrome_profile" / "GeminiSession"
print(f"[2] User data dir: {user_data_dir}")
print(f"[3] Dir exists: {user_data_dir.exists()}")

# Kiểm tra LOCK files
import glob
locks = glob.glob(str(user_data_dir / "**" / "LOCK"), recursive=True)
print(f"[4] LOCK files còn: {len(locks)}")
for lf in locks[:5]:
    print(f"    - {lf}")

print()
print("[5] Đang thử khởi động Chrome...")

async def test():
    client = GeminiWebClient(headless=False)
    try:
        await client.start()
        print("[OK] Chrome đã mở!")
        input("Nhấn Enter để đóng...")
        await client.stop()
    except Exception as e:
        print(f"[LỖI] {type(e).__name__}: {e}")
        print()
        print("--- TRACEBACK ---")
        traceback.print_exc()

asyncio.run(test())
input("\nNhấn Enter để thoát...")
