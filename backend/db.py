from __future__ import annotations

import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from typing import Any, Iterable

from .config import DB_PATH, DEFAULT_SETTINGS, ensure_dirs

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS paper_versions (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    pdf_path TEXT NOT NULL,
    source_hash TEXT NOT NULL,
    status TEXT NOT NULL,
    title TEXT DEFAULT '',
    authors_json TEXT DEFAULT '[]',
    abstract TEXT DEFAULT '',
    venue TEXT DEFAULT '',
    venue_source TEXT DEFAULT '',
    year TEXT DEFAULT '',
    doi TEXT DEFAULT '',
    arxiv_id TEXT DEFAULT '',
    code_url TEXT DEFAULT '',
    project_url TEXT DEFAULT '',
    paper_url TEXT DEFAULT '',
    raw_text TEXT DEFAULT '',
    figures_json TEXT DEFAULT '[]',
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS claims (
    id TEXT PRIMARY KEY,
    version_id TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    unit TEXT DEFAULT '',
    source_page INTEGER DEFAULT 0,
    source_quote TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'candidate',
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS artifacts (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    locale TEXT DEFAULT '',
    platform TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'absent',
    content TEXT DEFAULT '',
    content_hash TEXT DEFAULT '',
    issues_json TEXT DEFAULT '[]',
    updated_at REAL NOT NULL,
    UNIQUE(project_id, kind, locale, platform)
);
CREATE TABLE IF NOT EXISTS artifact_versions (
    id TEXT PRIMARY KEY,
    artifact_id TEXT NOT NULL,
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    source_version_id TEXT DEFAULT '',
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    progress REAL DEFAULT 0,
    message TEXT DEFAULT '',
    result_json TEXT DEFAULT '{}',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS publications (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    target TEXT NOT NULL,
    remote_id TEXT DEFAULT '',
    remote_url TEXT DEFAULT '',
    state TEXT NOT NULL DEFAULT 'planned',
    content_hash TEXT DEFAULT '',
    last_verified_at REAL,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    locator TEXT NOT NULL,
    interval_min INTEGER NOT NULL DEFAULT 30,
    enabled INTEGER NOT NULL DEFAULT 1,
    last_checked_at REAL,
    last_hash TEXT DEFAULT '',
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    type TEXT NOT NULL,
    payload_json TEXT DEFAULT '{}',
    created_at REAL NOT NULL
);
"""


def now() -> float:
    return time.time()


def new_id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:12]}"


def connect() -> sqlite3.Connection:
    ensure_dirs()
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def db():
    conn = connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def init_db() -> None:
    ensure_dirs()
    with db() as conn:
        conn.executescript(SCHEMA)
        _ensure_column(conn, "paper_versions", "metadata_source", "metadata_source TEXT DEFAULT ''")
        _ensure_column(conn, "paper_versions", "code_url_source", "code_url_source TEXT DEFAULT ''")
        _ensure_column(conn, "paper_versions", "code_url_confirmed", "code_url_confirmed INTEGER DEFAULT 0")
        _ensure_column(conn, "artifacts", "source_version_id", "source_version_id TEXT DEFAULT ''")
        _ensure_column(conn, "jobs", "version_id", "version_id TEXT DEFAULT ''")
        for key, value in DEFAULT_SETTINGS.items():
            conn.execute("INSERT OR IGNORE INTO settings(key, value) VALUES(?, ?)", (key, value))


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row else None


def json_load(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


def get_setting(key: str, default: str = "") -> str:
    with db() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    with db() as conn:
        conn.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )


def all_settings() -> dict[str, str]:
    with db() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
    return {r["key"]: r["value"] for r in rows}


def create_project(name: str) -> dict[str, Any]:
    pid = new_id("p_")
    ts = now()
    with db() as conn:
        conn.execute(
            "INSERT INTO projects(id, name, created_at, updated_at) VALUES(?,?,?,?)",
            (pid, name, ts, ts),
        )
    return get_project(pid)  # type: ignore[return-value]


def touch_project(project_id: str) -> None:
    with db() as conn:
        conn.execute("UPDATE projects SET updated_at=? WHERE id=?", (now(), project_id))


def get_project(project_id: str) -> dict[str, Any] | None:
    with db() as conn:
        project = row_to_dict(conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone())
        if not project:
            return None
        version = row_to_dict(
            conn.execute(
                "SELECT * FROM paper_versions WHERE project_id=? ORDER BY created_at DESC LIMIT 1",
                (project_id,),
            ).fetchone()
        )
        if version:
            version["authors"] = json_load(version.pop("authors_json"), [])
            version["figures"] = json_load(version.pop("figures_json"), [])
        project["version"] = version
        project["artifacts"] = list_artifacts(project_id)
    return project


def list_projects() -> list[dict[str, Any]]:
    with db() as conn:
        rows = conn.execute("SELECT * FROM projects ORDER BY updated_at DESC").fetchall()
    result = []
    for row in rows:
        item = dict(row)
        version = None
        with db() as conn:
            v = conn.execute(
                "SELECT title, venue, status, authors_json FROM paper_versions WHERE project_id=? ORDER BY created_at DESC LIMIT 1",
                (row["id"],),
            ).fetchone()
            if v:
                version = dict(v)
                version["authors"] = json_load(version.pop("authors_json"), [])
        item["version"] = version
        result.append(item)
    return result


def create_version(project_id: str, filename: str, pdf_path: str, source_hash: str) -> str:
    vid = new_id("v_")
    with db() as conn:
        conn.execute(
            "INSERT INTO paper_versions(id, project_id, filename, pdf_path, source_hash, status, created_at) "
            "VALUES(?,?,?,?,?,?,?)",
            (vid, project_id, filename, pdf_path, source_hash, "imported", now()),
        )
    return vid


def update_version(version_id: str, **fields: Any) -> None:
    if not fields:
        return
    allowed = {
        "status", "title", "authors_json", "abstract", "venue", "venue_source",
        "year", "doi", "arxiv_id", "code_url", "code_url_source", "code_url_confirmed",
        "metadata_source", "project_url", "paper_url", "raw_text", "figures_json",
    }
    keys = [k for k in fields if k in allowed]
    if not keys:
        return
    sets = ", ".join(f"{k}=?" for k in keys)
    with db() as conn:
        conn.execute(f"UPDATE paper_versions SET {sets} WHERE id=?", [fields[k] for k in keys] + [version_id])


def get_version(version_id: str) -> dict[str, Any] | None:
    with db() as conn:
        row = row_to_dict(conn.execute("SELECT * FROM paper_versions WHERE id=?", (version_id,)).fetchone())
    if row:
        row["authors"] = json_load(row.pop("authors_json"), [])
        row["figures"] = json_load(row.pop("figures_json"), [])
    return row


def current_version(project_id: str) -> dict[str, Any] | None:
    with db() as conn:
        row = row_to_dict(
            conn.execute(
                "SELECT * FROM paper_versions WHERE project_id=? ORDER BY created_at DESC LIMIT 1",
                (project_id,),
            ).fetchone()
        )
    if row:
        row["authors"] = json_load(row.pop("authors_json"), [])
        row["figures"] = json_load(row.pop("figures_json"), [])
    return row


def add_claim(version_id: str, key: str, value: str, unit: str, page: int, quote: str, status: str = "candidate") -> str:
    cid = new_id("c_")
    with db() as conn:
        conn.execute(
            "INSERT INTO claims(id, version_id, key, value, unit, source_page, source_quote, status, created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (cid, version_id, key, value, unit, page, quote, status, now()),
        )
    return cid


def set_claim_status(claim_id: str, status: str) -> None:
    with db() as conn:
        conn.execute("UPDATE claims SET status=? WHERE id=?", (status, claim_id))


def list_claims(version_id: str) -> list[dict[str, Any]]:
    with db() as conn:
        rows = conn.execute("SELECT * FROM claims WHERE version_id=? ORDER BY created_at", (version_id,)).fetchall()
    return [dict(r) for r in rows]


def upsert_artifact(project_id: str, kind: str, locale: str = "", platform: str = "") -> dict[str, Any]:
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM artifacts WHERE project_id=? AND kind=? AND locale=? AND platform=?",
            (project_id, kind, locale, platform),
        ).fetchone()
        if not row:
            aid = new_id("a_")
            conn.execute(
                "INSERT INTO artifacts(id, project_id, kind, locale, platform, status, updated_at) "
                "VALUES(?,?,?,?,?,?,?)",
                (aid, project_id, kind, locale, platform, "absent", now()),
            )
            row = conn.execute("SELECT * FROM artifacts WHERE id=?", (aid,)).fetchone()
    return dict(row)


def update_artifact(artifact_id: str, **fields: Any) -> None:
    allowed = {"status", "content", "content_hash", "issues_json", "source_version_id"}
    keys = [k for k in fields if k in allowed]
    if not keys:
        return
    sets = ", ".join(f"{k}=?" for k in keys)
    with db() as conn:
        conn.execute(
            f"UPDATE artifacts SET {sets}, updated_at=? WHERE id=?",
            [fields[k] for k in keys] + [now(), artifact_id],
        )


def get_artifact(project_id: str, kind: str, locale: str = "", platform: str = "") -> dict[str, Any] | None:
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM artifacts WHERE project_id=? AND kind=? AND locale=? AND platform=?",
            (project_id, kind, locale, platform),
        ).fetchone()
    return dict(row) if row else None


def list_artifacts(project_id: str) -> list[dict[str, Any]]:
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM artifacts WHERE project_id=? ORDER BY kind, locale, platform", (project_id,)
        ).fetchall()
    out = []
    for row in rows:
        item = dict(row)
        item["issues"] = json_load(item.pop("issues_json"), [])
        out.append(item)
    return out


def add_artifact_version(artifact_id: str, content: str, content_hash: str, source_version_id: str) -> str:
    vid = new_id("av_")
    with db() as conn:
        conn.execute(
            "INSERT INTO artifact_versions(id, artifact_id, content, content_hash, source_version_id, created_at) "
            "VALUES(?,?,?,?,?,?)",
            (vid, artifact_id, content, content_hash, source_version_id, now()),
        )
    return vid


def has_manual_edit(artifact_id: str) -> bool:
    with db() as conn:
        row = conn.execute(
            "SELECT 1 FROM artifact_versions WHERE artifact_id=? AND source_version_id='' LIMIT 1",
            (artifact_id,),
        ).fetchone()
    return bool(row)


def latest_artifact_version(artifact_id: str, source_only: bool = False) -> dict[str, Any] | None:
    query = "SELECT * FROM artifact_versions WHERE artifact_id=?"
    params: list[Any] = [artifact_id]
    if source_only:
        query += " AND source_version_id!=''"
    query += " ORDER BY created_at DESC LIMIT 1"
    with db() as conn:
        row = conn.execute(query, params).fetchone()
    return dict(row) if row else None


def create_job(project_id: str, kind: str, version_id: str = "") -> str:
    jid = new_id("j_")
    ts = now()
    with db() as conn:
        conn.execute(
            "INSERT INTO jobs(id, project_id, kind, status, progress, message, version_id, created_at, updated_at) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (jid, project_id, kind, "queued", 0, "", version_id, ts, ts),
        )
    return jid


def update_job(job_id: str, **fields: Any) -> None:
    allowed = {"status", "progress", "message", "result_json"}
    keys = [k for k in fields if k in allowed]
    if not keys:
        return
    sets = ", ".join(f"{k}=?" for k in keys)
    with db() as conn:
        conn.execute(f"UPDATE jobs SET {sets}, updated_at=? WHERE id=?", [fields[k] for k in keys] + [now(), job_id])


def get_job(job_id: str) -> dict[str, Any] | None:
    with db() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if row:
        item = dict(row)
        item["result"] = json_load(item.pop("result_json"), {})
        return item
    return None


def list_jobs(project_id: str, limit: int = 20) -> list[dict[str, Any]]:
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM jobs WHERE project_id=? ORDER BY created_at DESC LIMIT ?", (project_id, limit)
        ).fetchall()
    out = []
    for row in rows:
        item = dict(row)
        item["result"] = json_load(item.pop("result_json"), {})
        out.append(item)
    return out


def add_event(project_id: str, event_type: str, payload: dict[str, Any] | None = None) -> None:
    with db() as conn:
        conn.execute(
            "INSERT INTO events(id, project_id, type, payload_json, created_at) VALUES(?,?,?,?,?)",
            (new_id("e_"), project_id, event_type, json.dumps(payload or {}, ensure_ascii=False), now()),
        )


def list_events(project_id: str, limit: int = 50) -> list[dict[str, Any]]:
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM events WHERE project_id=? ORDER BY created_at DESC LIMIT ?", (project_id, limit)
        ).fetchall()
    out = []
    for row in rows:
        item = dict(row)
        item["payload"] = json_load(item.pop("payload_json"), {})
        out.append(item)
    return out


def add_source(project_id: str, kind: str, locator: str, interval_min: int = 30) -> str:
    sid = new_id("s_")
    with db() as conn:
        conn.execute(
            "INSERT INTO sources(id, project_id, kind, locator, interval_min, enabled, created_at) "
            "VALUES(?,?,?,?,?,?,?)",
            (sid, project_id, kind, locator, interval_min, 1, now()),
        )
    return sid


def list_sources(project_id: str) -> list[dict[str, Any]]:
    with db() as conn:
        rows = conn.execute("SELECT * FROM sources WHERE project_id=? ORDER BY created_at", (project_id,)).fetchall()
    return [dict(r) for r in rows]


def due_sources() -> list[dict[str, Any]]:
    ts = now()
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM sources WHERE enabled=1 AND (last_checked_at IS NULL OR last_checked_at + interval_min*60 <= ?)",
            (ts,),
        ).fetchall()
    return [dict(r) for r in rows]


def update_source(source_id: str, **fields: Any) -> None:
    allowed = {"last_checked_at", "last_hash", "enabled", "interval_min"}
    keys = [k for k in fields if k in allowed]
    if not keys:
        return
    sets = ", ".join(f"{k}=?" for k in keys)
    with db() as conn:
        conn.execute(f"UPDATE sources SET {sets} WHERE id=?", [fields[k] for k in keys] + [source_id])


def upsert_publication(project_id: str, target: str, **fields: Any) -> dict[str, Any]:
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM publications WHERE project_id=? AND target=?", (project_id, target)
        ).fetchone()
        if not row:
            pid = new_id("pub_")
            conn.execute(
                "INSERT INTO publications(id, project_id, target, created_at) VALUES(?,?,?,?)",
                (pid, project_id, target, now()),
            )
            row = conn.execute("SELECT * FROM publications WHERE id=?", (pid,)).fetchone()
        if fields:
            allowed = {"remote_id", "remote_url", "state", "content_hash", "last_verified_at"}
            keys = [k for k in fields if k in allowed]
            if keys:
                sets = ", ".join(f"{k}=?" for k in keys)
                conn.execute(
                    f"UPDATE publications SET {sets} WHERE id=?",
                    [fields[k] for k in keys] + [row["id"]],
                )
                row = conn.execute("SELECT * FROM publications WHERE id=?", (row["id"],)).fetchone()
    return dict(row)


def list_publications(project_id: str) -> list[dict[str, Any]]:
    with db() as conn:
        rows = conn.execute("SELECT * FROM publications WHERE project_id=?", (project_id,)).fetchall()
    return [dict(r) for r in rows]
