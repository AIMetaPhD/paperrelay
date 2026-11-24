"""Run the PaperRelay verification suite and print a reproducible summary.

Usage:
    .venv\\Scripts\\python.exe test_verify.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from backend import __version__  # noqa: E402


REQUIRED = ["run.py", "requirements.txt", "README.md", "LICENSE", "backend", "frontend"]


def main() -> int:
    print(f"PaperRelay version: {__version__}")
    missing = [name for name in REQUIRED if not (ROOT / name).exists()]
    if missing:
        print("MISSING_ROOT_ITEMS:", ", ".join(missing))
        return 1
    print("root structure: OK")
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_*.py", top_level_dir=str(ROOT))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(
        f"RESULT tests={result.testsRun} failures={len(result.failures)} "
        f"errors={len(result.errors)} skipped={len(result.skipped)}"
    )
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
