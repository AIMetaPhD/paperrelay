from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path
from typing import Any

import requests

from .db import add_event, db, due_sources, get_setting, update_artifact, update_source, now

_stop = threading.Event()
_regenerate_hook = None


def set_regenerate_hook(fn) -> None:
    """main.py registers the job dispatcher so a source change can pre-generate candidates."""
    global _regenerate_hook
    _regenerate_hook = fn


def _hash(text: str | bytes) -> str:
    data = text.encode("utf-8") if isinstance(text, str) else text
    return hashlib.sha256(data).hexdigest()


def _check_arxiv(locator: str) -> tuple[str, str]:
    response = requests.get(
        "http://export.arxiv.org/api/query",
        params={"id_list": locator, "max_results": 1},
        timeout=20,
        headers={"User-Agent": "PaperRelay/0.1"},
    )
    response.raise_for_status()
    return _hash(response.text), f"arXiv entry {locator}"


def _check_github(locator: str) -> tuple[str, str]:
    response = requests.get(
        f"https://api.github.com/repos/{locator}",
        timeout=20,
        headers={"User-Agent": "PaperRelay/0.1", "Accept": "application/vnd.github+json"},
    )
    response.raise_for_status()
    data = response.json()
    payload = json.dumps(
        {"pushed_at": data.get("pushed_at"), "updated_at": data.get("updated_at"), "description": data.get("description")},
        sort_keys=True,
    )
    return _hash(payload), f"GitHub repo {locator}"


def _check_local(path: str) -> tuple[str, str]:
    file = Path(path)
    if not file.exists():
        raise FileNotFoundError(path)
    return _hash(file.read_bytes()), f"Local file {file.name}"


def _check_url(url: str) -> tuple[str, str]:
    response = requests.get(url, timeout=20, headers={"User-Agent": "PaperRelay/0.1"})
    response.raise_for_status()
    return _hash(response.text), f"URL {url}"


def check_source(source: dict[str, Any]) -> dict[str, Any]:
    kind = source["kind"]
    locator = source["locator"]
    if kind == "arxiv":
        digest, summary = _check_arxiv(locator)
    elif kind == "github":
        digest, summary = _check_github(locator)
    elif kind == "local_file":
        digest, summary = _check_local(locator)
    elif kind == "url":
        digest, summary = _check_url(locator)
    else:
        raise ValueError(f"Unknown source kind: {kind}")
    previous = source.get("last_hash") or ""
    changed = bool(previous) and previous != digest
    update_source(source["id"], last_checked_at=now(), last_hash=digest)
    if changed:
        with db() as conn:
            rows = conn.execute(
                "SELECT id FROM artifacts WHERE project_id=? AND status IN ('ready','published','draft','needs_review')",
                (source["project_id"],),
            ).fetchall()
        for row in rows:
            update_artifact(row["id"], status="stale", issues_json=json.dumps(
                [{"type": "source_changed",
                  "message": f"{summary} changed. An update candidate is being prepared; your manual edit is kept until you approve the candidate."}],
                ensure_ascii=False,
            ))
        add_event(source["project_id"], "source_changed", {"source_id": source["id"], "summary": summary})
        if _regenerate_hook:
            try:
                _regenerate_hook(source["project_id"])
            except Exception as exc:
                add_event(source["project_id"], "auto_update_failed", {"error": str(exc)[:300]})
    return {"changed": changed, "summary": summary, "hash": digest, "previous": previous}


def check_project_sources(project_id: str) -> list[dict[str, Any]]:
    with db() as conn:
        rows = conn.execute("SELECT * FROM sources WHERE project_id=? AND enabled=1", (project_id,)).fetchall()
    results = []
    for row in rows:
        try:
            result = check_source(dict(row))
            result["source_id"] = row["id"]
            results.append(result)
        except Exception as exc:
            results.append({"source_id": row["id"], "error": str(exc)[:300]})
    return results


def _loop() -> None:
    while not _stop.is_set():
        try:
            # The toggle is read on every tick so disabling it takes effect immediately
            # and survives restarts through the settings table.
            if get_setting("maintenance_enabled", "0") == "1":
                for source in due_sources():
                    try:
                        check_source(source)
                    except Exception:
                        pass
        except Exception:
            pass
        _stop.wait(30)


def start_scheduler() -> None:
    thread = threading.Thread(target=_loop, name="paperrelay-maintenance", daemon=True)
    thread.start()


def stop_scheduler() -> None:
    _stop.set()
