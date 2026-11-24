"""Read-only environment self-check for the settings page and CI/troubleshooting."""

from __future__ import annotations

import importlib.util
import platform
import shutil
import socket
import sys
from pathlib import Path
from typing import Any

from .config import find_ffmpeg, find_ffprobe


def _tool(path: str, name: str, hint: str) -> dict[str, Any]:
    resolved = path if (Path(path).is_absolute() and Path(path).exists()) else (shutil.which(path) or "")
    if resolved:
        return {"key": name, "status": "ok", "detail": resolved, "hint": ""}
    return {"key": name, "status": "fail", "detail": path or "not found", "hint": hint}


def _playwright() -> dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            executable = Path(pw.chromium.executable_path)
        if executable.exists():
            return {"key": "chromium", "status": "ok", "detail": str(executable), "hint": ""}
        return {
            "key": "chromium",
            "status": "fail",
            "detail": f"Chromium executable missing: {executable}",
            "hint": "Run: python -m playwright install chromium",
        }
    except Exception as exc:
        return {
            "key": "chromium",
            "status": "fail",
            "detail": str(exc)[:180],
            "hint": "Run: python -m playwright install chromium",
        }


def _tts() -> dict[str, Any]:
    try:
        socket.create_connection(("speech.platform.bing.com", 443), timeout=4).close()
        return {
            "key": "edge_tts",
            "status": "warn",
            "detail": "TCP 443 reachable; synthesis can still return 503",
            "hint": "If video generation reports 503, retry later or choose another voice.",
        }
    except Exception as exc:
        return {
            "key": "edge_tts",
            "status": "fail",
            "detail": str(exc)[:180],
            "hint": "Edge TTS needs outbound network access to speech.platform.bing.com.",
        }


def run_checks() -> list[dict[str, Any]]:
    python_ok = sys.version_info >= (3, 11)
    checks: list[dict[str, Any]] = [
        {
            "key": "python",
            "status": "ok" if python_ok else "fail",
            "detail": f"{platform.python_version()} / {platform.system()}",
            "hint": "" if python_ok else "Install Python 3.11 or newer.",
        }
    ]
    checks.append(_tool(find_ffmpeg(), "ffmpeg", "Install FFmpeg and add it to PATH, or set FFMPEG_BIN."))
    checks.append(_tool(find_ffprobe(), "ffprobe", "Install FFmpeg (includes ffprobe), or set FFPROBE_BIN."))
    checks.append(_playwright())
    if importlib.util.find_spec("edge_tts") is None:
        checks.append({"key": "edge_tts", "status": "fail", "detail": "edge-tts not installed",
                       "hint": "pip install -r requirements.txt"})
    else:
        checks.append(_tts())
    return checks
