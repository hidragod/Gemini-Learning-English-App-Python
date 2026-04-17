"""Text-to-Speech module using gTTS with Windows fallback."""
import os
import subprocess
import tempfile
from pathlib import Path
from gtts import gTTS


def text_to_speech(text: str, lang: str = "en", slow: bool = False) -> str:
    """Convert text to speech, return temp file path"""
    tts = gTTS(text=text, lang=lang, slow=slow)
    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp.close()
    tts.save(tmp.name)
    return tmp.name


def _powershell_speak(text: str):
    """Fallback speech using Windows SAPI."""
    if os.name != "nt":
        return
    escaped = text.replace('"', '""')
    script = (
        "Add-Type -AssemblyName System.Speech;"
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
        f"$s.Speak(\"{escaped}\");"
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def play_audio(file_path: str, fallback_text: str = ""):
    """Play audio file using pygame"""
    try:
        import pygame

        pygame.mixer.init()
        pygame.mixer.music.load(file_path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)
    except Exception as e:
        print(f"Audio error: {e}")
        if fallback_text:
            _powershell_speak(fallback_text)


def speak_word(word: str, slow: bool = False):
    """Speak a single word"""
    path = None
    try:
        path = text_to_speech(word, slow=slow)
        play_audio(path, fallback_text=word)
    except Exception:
        _powershell_speak(word)
    finally:
        if path and os.path.exists(path):
            try:
                os.unlink(path)
            except Exception:
                pass


def speak_sentence(sentence: str, slow: bool = False):
    """Speak a sentence"""
    path = None
    try:
        path = text_to_speech(sentence, slow=slow)
        play_audio(path, fallback_text=sentence)
    except Exception:
        _powershell_speak(sentence)
    finally:
        if path and os.path.exists(path):
            try:
                os.unlink(path)
            except Exception:
                pass


def save_audio(text: str, output_path: str, slow: bool = False):
    """Save audio to specific path"""
    tts = gTTS(text=text, lang="en", slow=slow)
    tts.save(output_path)
    return output_path
