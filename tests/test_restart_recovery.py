"""D9: start an isolated server, terminate it like a crash, restart, verify persistence."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

import fitz
import requests

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_health(base: str, seconds: float = 40) -> None:
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            if requests.get(f"{base}/api/health", timeout=1).status_code == 200:
                return
        except Exception:
            pass
        time.sleep(0.25)
    raise AssertionError("server did not become healthy")


def _wait_parse(base: str, project_id: str, seconds: float = 60) -> dict:
    deadline = time.time() + seconds
    while time.time() < deadline:
        item = requests.get(f"{base}/api/projects/{project_id}", timeout=5).json()
        jobs = item.get("jobs") or []
        if not any(j["status"] in ("queued", "running") for j in jobs) and item["version"]["status"] in ("parsed", "needs_input"):
            return item
        time.sleep(0.4)
    raise AssertionError("parse did not finish")


class RestartRecoveryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.data_dir = tempfile.TemporaryDirectory(prefix="paperrelay-restart-")
        self.port = _free_port()
        self.base = f"http://127.0.0.1:{self.port}"
        self.proc: subprocess.Popen | None = None

    def tearDown(self) -> None:
        self._stop()
        self.data_dir.cleanup()

    def _env(self) -> dict[str, str]:
        env = os.environ.copy()
        env["PAPERRELAY_DATA"] = self.data_dir.name
        env["PAPERRELAY_PORT"] = str(self.port)
        env["PAPERRELAY_OPEN_BROWSER"] = "0"
        return env

    def _start(self) -> None:
        self.proc = subprocess.Popen(
            [PYTHON, "run.py"],
            cwd=str(ROOT),
            env=self._env(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        _wait_health(self.base)

    def _stop(self) -> None:
        if not self.proc:
            return
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=10)
        self.proc = None

    def test_project_survives_abrupt_restart(self) -> None:
        pdf = Path(self.data_dir.name) / "restart.pdf"
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 100), "Restart Recovery Test Paper")
        page.insert_text((72, 130), "Abstract")
        page.insert_text((72, 150), "This paper verifies that project records survive a server restart.")
        page.insert_text((72, 170), "The method reduces latency by 3 times versus the baseline.")
        doc.save(str(pdf))
        doc.close()

        self._start()
        with pdf.open("rb") as handle:
            created = requests.post(
                f"{self.base}/api/projects",
                files={"file": ("restart.pdf", handle, "application/pdf")},
                timeout=30,
            ).json()
        pid = created["project"]["id"]
        _wait_parse(self.base, pid)

        requests.patch(
            f"{self.base}/api/projects/{pid}/metadata",
            json={"title": "Restart Recovery Test Paper", "venue": "", "venue_source": ""},
            timeout=10,
        ).raise_for_status()
        before = requests.get(f"{self.base}/api/projects/{pid}", timeout=10).json()
        self.assertEqual(before["version"]["title"], "Restart Recovery Test Paper")

        # Simulate an abrupt process exit, then start a new process on the same data dir.
        self._stop()
        self._start()
        after = requests.get(f"{self.base}/api/projects/{pid}", timeout=10).json()
        self.assertEqual(after["version"]["title"], "Restart Recovery Test Paper")
        self.assertEqual(after["version"]["source_hash"], before["version"]["source_hash"])
        self.assertEqual(after["version"]["status"], before["version"]["status"])
        self.assertEqual(after["project"]["id"] if "project" in after else after["id"], pid)


if __name__ == "__main__":
    unittest.main()
