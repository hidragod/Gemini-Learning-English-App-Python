"""
Manual Chrome debug script.

Run with:
    uv run python test_chrome.py
"""

import asyncio
import glob
import sys
import traceback
from pathlib import Path

sys.path.insert(0, ".")

from src.gemini.gemini_web_client import GeminiWebClient, find_chrome


def print_environment() -> None:
    print("=" * 60)
    print("CHROME TEST")
    print("=" * 60)

    chrome_exe = find_chrome()
    print(f"[1] Chrome exe: {chrome_exe}")

    project_root = Path(__file__).parent
    user_data_dir = project_root / "chrome_profile" / "GeminiSession"
    print(f"[2] User data dir: {user_data_dir}")
    print(f"[3] Dir exists: {user_data_dir.exists()}")

    locks = glob.glob(str(user_data_dir / "**" / "LOCK"), recursive=True)
    print(f"[4] LOCK files con: {len(locks)}")
    for lock_file in locks[:5]:
        print(f"    - {lock_file}")

    print()
    print("[5] Dang thu khoi dong Chrome...")


async def run_chrome_check() -> None:
    client = GeminiWebClient(headless=False)
    try:
        await client.start()
        print("[OK] Chrome da mo!")
        input("Nhan Enter de dong...")
        await client.stop()
    except Exception as exc:
        print(f"[LOI] {type(exc).__name__}: {exc}")
        print()
        print("--- TRACEBACK ---")
        traceback.print_exc()


def main() -> None:
    print_environment()
    asyncio.run(run_chrome_check())
    input("\nNhan Enter de thoat...")


if __name__ == "__main__":
    main()
