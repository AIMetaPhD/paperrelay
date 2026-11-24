from __future__ import annotations

import os
import sys
import webbrowser
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

if __name__ == "__main__":
    port = int(os.environ.get("PAPERRELAY_PORT", "8787"))
    if os.environ.get("PAPERRELAY_OPEN_BROWSER", "1") == "1":
        try:
            webbrowser.open(f"http://127.0.0.1:{port}/")
        except Exception:
            pass
    uvicorn.run("backend.main:app", host="127.0.0.1", port=port, log_level="info")
