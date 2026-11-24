from __future__ import annotations

import os
import shutil
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("PAPERRELAY_DATA", APP_ROOT / "data"))
PROJECTS_DIR = DATA_DIR / "projects"
EXPORTS_DIR = DATA_DIR / "exports"
DB_PATH = DATA_DIR / "paperrelay.sqlite3"

HOST = "127.0.0.1"
PORT = int(os.environ.get("PAPERRELAY_PORT", "8787"))

DEFAULT_SETTINGS = {
    "llm_base_url": os.environ.get("PAPERRELAY_LLM_BASE", "http://127.0.0.1:11434/v1"),
    "llm_model": os.environ.get("PAPERRELAY_LLM_MODEL", "qwen2.5:7b-instruct"),
    "llm_api_key": os.environ.get("PAPERRELAY_LLM_KEY", "local"),
    # "chat" = /chat/completions (Ollama, OpenAI, vLLM); "responses" = /responses
    # (Magpie gateway and other Responses-API-only gateways).
    "llm_wire_api": os.environ.get("PAPERRELAY_LLM_WIRE", "chat"),
    "voice_en": "en-US-AriaNeural",
    "voice_zh": "zh-CN-XiaoxiaoNeural",
    "video_language": "en",
    "github_repo": "",
    "maintenance_enabled": "0",
    "maintenance_interval_min": "30",
    # On a detected source change, pre-generate update candidates (marked for review).
    "maintenance_auto_update": "1",
}

ALLOWED_PDF_SUFFIXES = {".pdf"}


def ensure_dirs() -> None:
    for path in (DATA_DIR, PROJECTS_DIR, EXPORTS_DIR):
        path.mkdir(parents=True, exist_ok=True)


def find_ffmpeg() -> str:
    candidates = [
        os.environ.get("FFMPEG_BIN", ""),
        shutil.which("ffmpeg") or "",
        r"F:\Applications\Anaconda\envs\g0tools\Library\bin\ffmpeg.exe",
        r"C:\ffmpeg\bin\ffmpeg.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return "ffmpeg"


def find_chrome() -> str:
    candidates = [
        os.environ.get("CHROME_BIN", ""),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return ""


def find_ffprobe() -> str:
    candidates = [
        os.environ.get("FFPROBE_BIN", ""),
        shutil.which("ffprobe") or "",
        r"F:\Applications\Anaconda\envs\g0tools\Library\bin\ffprobe.exe",
        r"C:\ffmpeg\bin\ffprobe.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return "ffprobe"
