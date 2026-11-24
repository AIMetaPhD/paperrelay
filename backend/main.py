from __future__ import annotations

import json
import os
import shutil
import traceback
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import db
from .config import APP_ROOT, DATA_DIR, EXPORTS_DIR, PROJECTS_DIR, ensure_dirs
from .extract import extract_pdf, sha256_file
from .facts import code_confirmed, venue_confirmed
from .generate import check_model, content_hash, fact_check, generate_copy
from .github_publish import github_status, publish_site
from .maintenance import check_project_sources, set_regenerate_hook, start_scheduler
from .metadata import enrich_metadata
from .site import generate_site
from .video import generate_video

FRONTEND = APP_ROOT / "frontend"
ensure_dirs()
db.init_db()
app = FastAPI(title="PaperRelay", version="0.1.0")
executor = ThreadPoolExecutor(max_workers=2)

app.mount("/static", StaticFiles(directory=str(FRONTEND)), name="static")
app.mount("/files", StaticFiles(directory=str(PROJECTS_DIR)), name="files")
app.mount("/exports", StaticFiles(directory=str(EXPORTS_DIR)), name="exports")


class Superseded(RuntimeError):
    """A newer paper version landed while this job was running."""


def _project_dir(project_id: str) -> Path:
    path = PROJECTS_DIR / project_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _current_version_id(project_id: str) -> str:
    version = db.current_version(project_id)
    return version["id"] if version else ""


def _assert_current(project_id: str, version_id: str) -> None:
    if version_id and _current_version_id(project_id) != version_id:
        raise Superseded("A newer paper version was uploaded while this job was running; the result was discarded.")


def _artifact(project_id: str, kind: str, locale: str = "", platform: str = "") -> dict[str, Any]:
    return db.upsert_artifact(project_id, kind, locale, platform)


def _set_artifact(project_id: str, kind: str, status: str, content: str = "",
                  issues: list[dict[str, Any]] | None = None, locale: str = "", platform: str = "",
                  source_version_id: str = "") -> dict[str, Any]:
    art = _artifact(project_id, kind, locale, platform)
    db.update_artifact(
        art["id"],
        status=status,
        content=content,
        content_hash=content_hash(content) if content else "",
        issues_json=json.dumps(issues or [], ensure_ascii=False),
        source_version_id=source_version_id,
    )
    return art


def _job_progress(job_id: str):
    def update(progress: float, message: str) -> None:
        db.update_job(job_id, progress=progress, message=message)
    return update


def _save_claims(version_id: str, claims: list[dict[str, Any]]) -> None:
    with db.db() as conn:
        conn.execute("DELETE FROM claims WHERE version_id=?", (version_id,))
    for claim in claims:
        db.add_claim(version_id, claim["key"], claim["value"], claim.get("unit", ""), claim.get("page", 0), claim.get("quote", ""))


def _run_parse(job_id: str, project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    version = db.get_version(payload.get("version_id", "")) if payload.get("version_id") else None
    version = version or db.current_version(project_id)
    if not version:
        raise RuntimeError("No paper version")
    project_dir = _project_dir(project_id)
    progress = _job_progress(job_id)
    progress(0.1, "Reading PDF")
    data = extract_pdf(Path(version["pdf_path"]), project_dir)
    progress(0.55, "Checking metadata")
    meta = enrich_metadata(data["title"], data["links"].get("arxiv_id", ""), data["links"].get("doi", ""))
    title = meta.get("title") or data["title"]
    authors = meta.get("authors") or data["authors"]
    abstract = meta.get("abstract") or data["abstract"]
    venue = meta.get("venue") or ""
    venue_source = meta.get("venue_source") or ""
    code_url = data["links"].get("code_url") or meta.get("code_url") or ""
    paper_url = meta.get("paper_url") or data["links"].get("paper_url") or ""
    status = "parsed" if data["text"].strip() else "needs_input"
    code_source = "PDF 正文自动抽取（未核实）" if code_url else ""
    db.update_version(
        version["id"],
        status=status,
        title=title,
        authors_json=json.dumps(authors, ensure_ascii=False),
        abstract=abstract,
        venue=venue,
        venue_source=venue_source,
        year=meta.get("year", ""),
        doi=meta.get("doi", ""),
        arxiv_id=meta.get("arxiv_id", ""),
        metadata_source=meta.get("source") or "PDF 原文抽取",
        code_url=code_url,
        code_url_source=code_source,
        code_url_confirmed=0,
        project_url=data["links"].get("project_url", ""),
        paper_url=paper_url,
        raw_text=data["text"],
        figures_json=json.dumps(data["figures"], ensure_ascii=False),
    )
    _save_claims(version["id"], data["claims"])
    progress(1.0, "Parsed")
    return {"version_id": version["id"], "pages": data["pages"], "claims": len(data["claims"]), "figures": len(data["figures"])}


def _run_copy(job_id: str, project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    version = db.current_version(project_id)
    if not version:
        raise RuntimeError("No paper version")
    claims = db.list_claims(version["id"])
    progress = _job_progress(job_id)
    progress(0.15, "Generating platform copy")
    result = generate_copy(version, claims)
    target = None
    if payload.get("artifact_id"):
        target = next((a for a in db.list_artifacts(project_id) if a["id"] == payload["artifact_id"]), None)
    keys = [target["platform"]] if target and target.get("platform") else ["x_en", "x_zh", "linkedin_en", "wechat_zh", "xhs_zh"]
    auto_update = bool(payload.get("auto_update"))
    saved = {}
    for idx, key in enumerate(keys, start=1):
        _assert_current(project_id, version["id"])
        text = result["content"].get(key, "")
        issues = [i for i in result["issues"] if i.get("platform") in (None, key)]
        locale = "zh" if key.endswith("_zh") else "en"
        existing = db.get_artifact(project_id, "copy", locale=locale, platform=key)
        has_manual = bool(existing and db.has_manual_edit(existing["id"]))
        keep_current = bool(existing and (existing.get("content") or "").strip() and (has_manual or auto_update))
        if keep_current:
            db.add_artifact_version(existing["id"], text, content_hash(text), version["id"])
            issues.append({
                "type": "manual_edit_kept" if has_manual else "auto_update_candidate",
                "severity": "warning",
                "message": (
                    "A regenerated candidate was stored, but your manual edit was kept. Open the candidate to compare and adopt it."
                    if has_manual else
                    "A source changed. An update candidate is ready; compare it with the current copy and adopt it if you agree."
                ),
            })
            db.update_artifact(existing["id"], status="needs_review",
                               issues_json=json.dumps(issues, ensure_ascii=False),
                               source_version_id=version["id"])
            saved[key] = existing["id"]
        else:
            needs_review = any(
                i.get("severity") == "error" or i.get("type") == "llm_unavailable" for i in issues
            )
            status = "needs_review" if needs_review else "ready"
            art = _set_artifact(project_id, "copy", status, text, issues, locale=locale, platform=key,
                                source_version_id=version["id"])
            db.add_artifact_version(art["id"], text, content_hash(text), version["id"])
            saved[key] = art["id"]
        progress(0.15 + 0.8 * idx / len(keys), f"Saved {key}")
    return {"artifacts": saved, "used_llm": result["used_llm"], "wire": result.get("wire"),
            "issues": len(result["issues"])}


def _run_video(job_id: str, project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    version = db.current_version(project_id)
    if not version:
        raise RuntimeError("No paper version")
    claims = db.list_claims(version["id"])
    outdir = _project_dir(project_id) / "video"
    progress = _job_progress(job_id)
    _set_artifact(project_id, "video", "generating", source_version_id=version["id"])
    try:
        result = generate_video(version, claims, db.all_settings(), outdir, progress)
    except Exception as exc:
        _set_artifact(project_id, "video", "failed", "", [{"type": "video_failed", "message": str(exc)[:500]}])
        raise
    _assert_current(project_id, version["id"])
    probe = result.get("probe") or {}
    duration = float(result.get("duration") or probe.get("duration") or 0)
    issues = []
    if duration < 60:
        issues.append({"type": "short_video", "severity": "error",
                       "message": f"Video is {duration:.0f}s; target is 60-120s."})
    elif duration > 120:
        issues.append({"type": "long_video", "severity": "warning",
                       "message": f"Video is {duration:.0f}s, over the 120s target."})
    if not probe:
        issues.append({"type": "video_unprobed", "severity": "error",
                       "message": "The final MP4 could not be probed with ffprobe."})
    else:
        if (probe.get("width"), probe.get("height")) != (1920, 1080):
            issues.append({"type": "video_resolution", "severity": "error",
                           "message": f"Video is {probe.get('width')}x{probe.get('height')}; expected 1920x1080."})
        if probe.get("vcodec") != "h264":
            issues.append({"type": "video_codec", "severity": "error",
                           "message": f"Video codec is {probe.get('vcodec')}; expected h264."})
        if not probe.get("has_audio") or probe.get("acodec") != "aac":
            issues.append({"type": "audio_codec", "severity": "error",
                           "message": f"Audio is {probe.get('acodec') or 'missing'}; expected AAC."})
    _set_artifact(project_id, "video", "needs_review" if issues else "ready", str(outdir), issues,
                  source_version_id=version["id"])
    # refresh the site so it can embed the video (skipped inside the bundle,
    # which builds the site after the video step itself)
    if not payload.get("skip_site_refresh"):
        try:
            _run_site_inner(project_id)
        except Exception:
            pass
    progress(1.0, "Video ready")
    return {"duration": duration, "probe": probe, "video": str(outdir / "video.mp4"),
            "srt": str(outdir / "video.srt")}


def _run_site_inner(project_id: str, auto_update: bool = False) -> dict[str, Any]:
    version = db.current_version(project_id)
    if not version:
        raise RuntimeError("No paper version")
    claims = db.list_claims(version["id"])
    artifacts = db.list_artifacts(project_id)
    project_dir = _project_dir(project_id)
    if auto_update:
        outdir = project_dir / "site_candidates" / db.new_id("")
        index = generate_site(version, claims, artifacts, outdir)
    else:
        outdir = project_dir / "site"
        staging = project_dir / f".site_build_{db.new_id('')}"
        index = generate_site(version, claims, artifacts, staging)
        outdir.mkdir(parents=True, exist_ok=True)
        # Replace the published page only after the new build completed.
        os.replace(staging / "index.html", outdir / "index.html")
        staged_assets = staging / "assets"
        if staged_assets.exists():
            final_assets = outdir / "assets"
            if final_assets.exists():
                shutil.rmtree(final_assets)
            os.replace(staged_assets, final_assets)
        shutil.rmtree(staging, ignore_errors=True)
        index = outdir / "index.html"
    _assert_current(project_id, version["id"])
    if auto_update:
        existing = db.get_artifact(project_id, "site")
        if existing and (existing.get("content") or "").strip():
            db.add_artifact_version(existing["id"], str(index), content_hash(str(index)), version["id"])
            db.update_artifact(existing["id"], status="needs_review", issues_json=json.dumps(
                [{"type": "auto_update_candidate", "severity": "warning",
                  "message": "A source changed. A candidate project page was generated; the current page is unchanged until you adopt it."}],
                ensure_ascii=False))
            return {"index": str(index), "candidate": True}
    _set_artifact(project_id, "site", "ready", str(index), source_version_id=version["id"])
    return {"index": str(index)}


def _run_site(job_id: str, project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    progress = _job_progress(job_id)
    progress(0.3, "Building project page")
    result = _run_site_inner(project_id, auto_update=bool(payload.get("auto_update")))
    progress(1.0, "Page ready")
    return result


def _run_bundle(job_id: str, project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """One coordinated run: copy, then video, then site from the same facts.

    The site is built last so it embeds the video that was just produced. If any
    step fails, the job fails and each artifact keeps its real status.
    """
    version_id = _current_version_id(project_id)
    progress = _job_progress(job_id)
    results: dict[str, Any] = {}
    steps = [("copy", _run_copy), ("video", _run_video), ("site", _run_site)]
    for index, (kind, runner) in enumerate(steps, start=1):
        _assert_current(project_id, version_id)
        progress((index - 1) / len(steps) + 0.02, f"Running {kind}")
        step_payload = dict(payload)
        step_payload["skip_site_refresh"] = True
        results[kind] = runner(job_id, project_id, step_payload)
    return results


def _dispatch(job_id: str, project_id: str, kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    if kind == "parse":
        return _run_parse(job_id, project_id, payload)
    if kind == "copy":
        return _run_copy(job_id, project_id, payload)
    if kind == "video":
        return _run_video(job_id, project_id, payload)
    if kind == "site":
        return _run_site(job_id, project_id, payload)
    if kind == "bundle":
        return _run_bundle(job_id, project_id, payload)
    raise RuntimeError(f"Unknown job kind: {kind}")


def _job_wrapper(job_id: str, project_id: str, kind: str, payload: dict[str, Any]) -> None:
    db.update_job(job_id, status="running", progress=0.01, message="Starting")
    try:
        result = _dispatch(job_id, project_id, kind, payload)
        db.update_job(job_id, status="succeeded", progress=1.0, message="Done",
                      result_json=json.dumps(result, ensure_ascii=False))
        db.add_event(project_id, f"{kind}_done", result)
    except Superseded as exc:
        db.update_job(job_id, status="superseded", message=str(exc)[:500],
                      result_json=json.dumps({"error": str(exc), "superseded": True}, ensure_ascii=False))
        db.add_event(project_id, f"{kind}_superseded", {"error": str(exc)[:300]})
    except Exception as exc:
        db.update_job(job_id, status="failed", message=str(exc)[:500],
                      result_json=json.dumps({"error": str(exc), "trace": traceback.format_exc()[-2000:]}, ensure_ascii=False))
        db.add_event(project_id, f"{kind}_failed", {"error": str(exc)[:300]})


def start_job(project_id: str, kind: str, payload: dict[str, Any] | None = None) -> str:
    payload = payload or {}
    version_id = payload.get("version_id") or _current_version_id(project_id)
    job_id = db.create_job(project_id, kind, version_id)
    executor.submit(_job_wrapper, job_id, project_id, kind, payload)
    return job_id


@app.get("/")
def index() -> FileResponse:
    return FileResponse(str(FRONTEND / "index.html"))


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"ok": True, "app": "PaperRelay", "version": "0.1.0"}


@app.post("/api/projects")
async def create_project(file: UploadFile = File(...)) -> dict[str, Any]:
    filename = Path(file.filename or "paper.pdf").name
    if Path(filename).suffix.lower() != ".pdf":
        raise HTTPException(400, "Only PDF files are supported.")
    project = db.create_project(Path(filename).stem)
    project_dir = _project_dir(project["id"])
    pdf_path = project_dir / "paper.pdf"
    with pdf_path.open("wb") as handle:
        shutil.copyfileobj(file.file, handle)
    source_hash = sha256_file(pdf_path)
    version_id = db.create_version(project["id"], filename, str(pdf_path), source_hash)
    job_id = start_job(project["id"], "parse", {"version_id": version_id})
    return {"project": db.get_project(project["id"]), "job_id": job_id}


@app.get("/api/projects")
def projects() -> list[dict[str, Any]]:
    return db.list_projects()


@app.get("/api/projects/{project_id}")
def project(project_id: str) -> dict[str, Any]:
    item = db.get_project(project_id)
    if not item:
        raise HTTPException(404, "Project not found")
    item["claims"] = db.list_claims(item["version"]["id"]) if item.get("version") else []
    item["jobs"] = db.list_jobs(project_id)
    item["sources"] = db.list_sources(project_id)
    item["publications"] = db.list_publications(project_id)
    item["events"] = db.list_events(project_id)
    return item


@app.post("/api/projects/{project_id}/versions")
async def upload_version(project_id: str, file: UploadFile = File(...)) -> dict[str, Any]:
    if not db.get_project(project_id):
        raise HTTPException(404, "Project not found")
    filename = Path(file.filename or "paper.pdf").name
    if Path(filename).suffix.lower() != ".pdf":
        raise HTTPException(400, "Only PDF files are supported.")
    project_dir = _project_dir(project_id)
    data = await file.read()
    digest = __import__("hashlib").sha256(data).hexdigest()[:12]
    pdf_path = project_dir / f"paper_{digest}.pdf"
    pdf_path.write_bytes(data)
    version_id = db.create_version(project_id, filename, str(pdf_path), sha256_file(pdf_path))
    for art in db.list_artifacts(project_id):
        if art["status"] not in ("absent", "failed"):
            db.update_artifact(art["id"], status="stale")
    job_id = start_job(project_id, "parse", {"version_id": version_id})
    db.add_event(project_id, "new_version", {"version_id": version_id, "filename": filename})
    return {"version_id": version_id, "job_id": job_id}


@app.patch("/api/projects/{project_id}/metadata")
def update_metadata(project_id: str, body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    version = db.current_version(project_id)
    if not version:
        raise HTTPException(404, "No paper version")
    fields: dict[str, Any] = {}
    for key in ("title", "abstract", "venue", "venue_source", "year", "doi", "arxiv_id",
                "code_url", "paper_url", "project_url"):
        if key in body:
            fields[key] = str(body[key])
    if "authors" in body:
        authors = body["authors"]
        if isinstance(authors, str):
            authors = [a.strip() for a in authors.split(",") if a.strip()]
        fields["authors_json"] = json.dumps(authors, ensure_ascii=False)
    if "code_url" in fields:
        new_code = fields["code_url"].strip()
        old_code = (version.get("code_url") or "").strip()
        if new_code != old_code:
            # An explicit user edit is the confirmation step.
            fields["code_url_confirmed"] = 1 if new_code else 0
            fields["code_url_source"] = "用户确认" if new_code else ""
        elif "code_url_confirmed" in body:
            fields["code_url_confirmed"] = 1 if body.get("code_url_confirmed") else 0
            if body.get("code_url_confirmed"):
                fields["code_url_source"] = "用户确认"
    if "venue" in fields and not fields.get("venue", "").strip():
        fields["venue_source"] = ""
    db.update_version(version["id"], **fields)
    fact_fields = {"title", "authors_json", "abstract", "venue", "venue_source", "year", "doi",
                   "arxiv_id", "code_url", "paper_url", "project_url"}
    if fact_fields & set(fields):
        for art in db.list_artifacts(project_id):
            if art["status"] in ("ready", "published", "needs_review", "draft"):
                db.update_artifact(
                    art["id"], status="stale",
                    issues_json=json.dumps(
                        [{"type": "metadata_changed", "severity": "warning",
                          "message": "Paper metadata changed; regenerate this artifact."}],
                        ensure_ascii=False,
                    ),
                )
    db.add_event(project_id, "metadata_edited", {"fields": list(fields)})
    return db.get_project(project_id) or {}


@app.post("/api/projects/{project_id}/reparse")
def reparse(project_id: str) -> dict[str, Any]:
    version = db.current_version(project_id)
    if not version:
        raise HTTPException(404, "No paper version")
    for art in db.list_artifacts(project_id):
        if art["status"] in ("ready", "published", "needs_review", "draft"):
            db.update_artifact(art["id"], status="stale", issues_json=json.dumps(
                [{"type": "metadata_changed", "severity": "warning",
                  "message": "The paper was re-parsed; regenerate this artifact from the refreshed facts."}],
                ensure_ascii=False))
    db.add_event(project_id, "reparsed", {"version_id": version["id"]})
    return {"job_id": start_job(project_id, "parse", {"version_id": version["id"]})}


@app.post("/api/projects/{project_id}/generate")
def generate_all(project_id: str) -> dict[str, Any]:
    if not db.get_project(project_id):
        raise HTTPException(404, "Project not found")
    version = db.current_version(project_id)
    if not version:
        raise HTTPException(400, "No paper version")
    if version["status"] != "parsed" or not (version.get("raw_text") or "").strip():
        raise HTTPException(
            400,
            f"The paper is '{version['status']}', not parsed. Wait for parsing to succeed (or fix the PDF) before generating.",
        )
    active = [j for j in db.list_jobs(project_id, 10) if j["status"] in ("queued", "running")]
    if active:
        raise HTTPException(409, "A generation job is already running for this project.")
    bundle_job = start_job(project_id, "bundle", {"version_id": version["id"]})
    return {"jobs": {"bundle": bundle_job}}


@app.post("/api/projects/{project_id}/artifacts/{artifact_id}/regenerate")
def regenerate(project_id: str, artifact_id: str) -> dict[str, Any]:
    art = next((a for a in db.list_artifacts(project_id) if a["id"] == artifact_id), None)
    if not art:
        raise HTTPException(404, "Artifact not found")
    kind = art["kind"]
    job_kind = {"copy": "copy", "video": "video", "site": "site"}.get(kind)
    if not job_kind:
        raise HTTPException(400, "This artifact cannot be regenerated.")
    active = [j for j in db.list_jobs(project_id, 10) if j["status"] in ("queued", "running")]
    if active:
        raise HTTPException(409, "A generation job is already running for this project.")
    db.update_artifact(artifact_id, status="generating")
    return {"job_id": start_job(project_id, job_kind, {"artifact_id": artifact_id})}


@app.patch("/api/projects/{project_id}/artifacts/{artifact_id}")
def save_artifact(project_id: str, artifact_id: str, body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    art = next((a for a in db.list_artifacts(project_id) if a["id"] == artifact_id), None)
    if not art:
        raise HTTPException(404, "Artifact not found")
    content = str(body.get("content", ""))
    version = db.current_version(project_id)
    issues = art.get("issues") or []
    if art["kind"] == "copy" and version:
        issues = fact_check(content, version, db.list_claims(version["id"]))
    db.update_artifact(artifact_id, content=content, content_hash=content_hash(content), status="draft",
                       issues_json=json.dumps(issues, ensure_ascii=False), source_version_id="")
    db.add_artifact_version(artifact_id, content, content_hash(content), "")
    db.add_event(project_id, "artifact_edited", {"artifact_id": artifact_id})
    return {"ok": True, "issues": issues}


@app.get("/api/projects/{project_id}/artifacts/{artifact_id}/versions")
def artifact_versions(project_id: str, artifact_id: str) -> list[dict[str, Any]]:
    with db.db() as conn:
        rows = conn.execute(
            "SELECT id, artifact_id, source_version_id, created_at, length(content) AS chars, content_hash "
            "FROM artifact_versions WHERE artifact_id=? ORDER BY created_at DESC LIMIT 20",
            (artifact_id,),
        ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/projects/{project_id}/artifacts/{artifact_id}/versions/{version_id}")
def artifact_version(project_id: str, artifact_id: str, version_id: str) -> dict[str, Any]:
    with db.db() as conn:
        row = conn.execute(
            "SELECT * FROM artifact_versions WHERE id=? AND artifact_id=?", (version_id, artifact_id)
        ).fetchone()
    if not row:
        raise HTTPException(404, "Version not found")
    return dict(row)


@app.post("/api/projects/{project_id}/artifacts/{artifact_id}/use-version")
def use_artifact_version(project_id: str, artifact_id: str, body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    version_id = str(body.get("version_id", ""))
    with db.db() as conn:
        row = conn.execute(
            "SELECT * FROM artifact_versions WHERE id=? AND artifact_id=?", (version_id, artifact_id)
        ).fetchone()
    if not row:
        raise HTTPException(404, "Version not found")
    db.update_artifact(artifact_id, content=row["content"], content_hash=row["content_hash"], status="draft",
                       source_version_id=row["source_version_id"] or "")
    db.add_event(project_id, "version_used", {"artifact_id": artifact_id, "version_id": version_id})
    return {"ok": True}


@app.get("/api/projects/{project_id}/artifacts/{artifact_id}/candidate")
def artifact_candidate(project_id: str, artifact_id: str) -> dict[str, Any]:
    art = next((a for a in db.list_artifacts(project_id) if a["id"] == artifact_id), None)
    if not art:
        raise HTTPException(404, "Artifact not found")
    candidate = db.latest_artifact_version(artifact_id, source_only=True)
    if not candidate or candidate["content_hash"] == art.get("content_hash"):
        return {"candidate": None}
    return {
        "candidate": {
            "id": candidate["id"],
            "content": candidate["content"],
            "content_hash": candidate["content_hash"],
            "source_version_id": candidate["source_version_id"],
            "created_at": candidate["created_at"],
        },
        "current": {"content": art.get("content") or "", "content_hash": art.get("content_hash") or ""},
    }


@app.post("/api/projects/{project_id}/artifacts/{artifact_id}/approve")
def approve_artifact(project_id: str, artifact_id: str) -> dict[str, Any]:
    """Server-side gate: stale, outdated or factually wrong artifacts cannot be approved."""
    art = next((a for a in db.list_artifacts(project_id) if a["id"] == artifact_id), None)
    if not art:
        raise HTTPException(404, "Artifact not found")
    version = db.current_version(project_id)
    if not version:
        raise HTTPException(400, "No paper version")
    if art["status"] == "stale":
        raise HTTPException(409, "This artifact is stale. Regenerate it before approving.")
    if art["status"] not in {"draft", "needs_review"}:
        raise HTTPException(400, f"Cannot approve from status {art['status']}")
    if art.get("source_version_id") and art["source_version_id"] != version["id"]:
        raise HTTPException(409, "This artifact was generated from an older paper version. Regenerate it first.")

    errors = [i for i in (art.get("issues") or []) if i.get("severity") == "error"]
    if art["kind"] == "copy":
        fresh = fact_check(art.get("content") or "", version, db.list_claims(version["id"]))
        errors += [i for i in fresh if i.get("severity") == "error"]
        merged = []
        seen = set()
        for issue in (art.get("issues") or []) + fresh:
            marker = (issue.get("type"), issue.get("value"), issue.get("message"))
            if marker not in seen:
                seen.add(marker)
                merged.append(issue)
        db.update_artifact(artifact_id, issues_json=json.dumps(merged, ensure_ascii=False))
    if art["kind"] == "site" and art.get("content") and not Path(art["content"]).exists():
        errors.append({"type": "site_missing", "severity": "error", "message": "The generated page file is missing."})
    if art["kind"] == "video" and art.get("content") and not (Path(art["content"]) / "video.mp4").exists():
        errors.append({"type": "video_missing", "severity": "error", "message": "The generated MP4 is missing."})
    if errors:
        messages = "; ".join(sorted({str(e.get("message") or e.get("type")) for e in errors}))[:900]
        raise HTTPException(400, f"Not approvable: {messages}")
    db.update_artifact(artifact_id, status="ready")
    db.add_event(project_id, "artifact_approved", {"artifact_id": artifact_id})
    return {"ok": True}


@app.get("/api/projects/{project_id}/jobs")
def jobs(project_id: str) -> list[dict[str, Any]]:
    return db.list_jobs(project_id)


@app.get("/api/jobs/{job_id}")
def job(job_id: str) -> dict[str, Any]:
    item = db.get_job(job_id)
    if not item:
        raise HTTPException(404, "Job not found")
    return item


@app.get("/api/settings")
def settings() -> dict[str, Any]:
    values = db.all_settings()
    key = values.get("llm_api_key", "")
    values["llm_api_key"] = ("•" * 8 + key[-4:]) if key else ""
    values["github"] = github_status()
    return values


@app.put("/api/settings")
def update_settings(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    allowed = {"llm_base_url", "llm_model", "llm_api_key", "llm_wire_api", "voice_en", "voice_zh",
               "video_language", "github_repo", "maintenance_enabled", "maintenance_interval_min"}
    for key, value in body.items():
        if key in allowed and not (key == "llm_api_key" and "•" in str(value)):
            db.set_setting(key, str(value))
    return settings()


@app.post("/api/settings/test")
def test_settings() -> dict[str, Any]:
    return check_model()


@app.post("/api/projects/{project_id}/claims/{claim_id}/verify")
def verify_claim(project_id: str, claim_id: str, body: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    version = db.current_version(project_id)
    if not version:
        raise HTTPException(404, "No paper version")
    claim = next((c for c in db.list_claims(version["id"]) if c["id"] == claim_id), None)
    if not claim:
        raise HTTPException(404, "Claim not found in the current paper version")
    verified = body.get("verified", True)
    if not isinstance(verified, bool):
        raise HTTPException(400, "verified must be a JSON boolean")
    db.set_claim_status(claim_id, "verified" if verified else "candidate")
    db.add_event(project_id, "claim_verified" if verified else "claim_unverified", {"claim_id": claim_id})
    return {"ok": True, "status": "verified" if verified else "candidate"}


@app.get("/api/projects/{project_id}/sources")
def sources(project_id: str) -> list[dict[str, Any]]:
    return db.list_sources(project_id)


@app.post("/api/projects/{project_id}/sources")
def add_source(project_id: str, body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    kind = str(body.get("kind", "")).strip()
    locator = str(body.get("locator", "")).strip()
    if kind not in {"arxiv", "github", "local_file", "url"} or not locator:
        raise HTTPException(400, "kind must be arxiv/github/local_file/url and locator is required.")
    raw_interval = body.get("interval_min")
    if raw_interval in (None, ""):
        raw_interval = db.get_setting("maintenance_interval_min", "30") or 30
    interval = max(1, int(raw_interval))
    sid = db.add_source(project_id, kind, locator, interval)
    return {"id": sid}


@app.post("/api/projects/{project_id}/sources/check")
def check_sources(project_id: str) -> dict[str, Any]:
    return {"results": check_project_sources(project_id)}


@app.post("/api/projects/{project_id}/publish/github")
def publish_github(project_id: str, body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    item = db.get_project(project_id)
    if not item:
        raise HTTPException(404, "Project not found")
    raw_approve = body.get("approve", False)
    if not isinstance(raw_approve, bool):
        raise HTTPException(400, "approve must be a JSON boolean (true/false), not a string.")
    approve = raw_approve
    repo_value = body.get("repo", "")
    if not isinstance(repo_value, str):
        raise HTTPException(400, "repo must be a string owner/name.")
    site = db.get_artifact(project_id, "site")
    if not site or not site.get("content"):
        raise HTTPException(400, "Generate the project page first.")
    if not approve:
        return publish_site(Path(site["content"]).parent, repo_value.strip(), False)

    version = db.current_version(project_id)
    if not version:
        raise HTTPException(400, "No paper version")
    if site["status"] not in {"ready", "published"}:
        raise HTTPException(409, f"The project page is '{site['status']}'. Approve it before publishing.")
    if site.get("source_version_id") and site["source_version_id"] != version["id"]:
        raise HTTPException(409, "The project page was generated from an older paper version. Regenerate it first.")
    site_errors = [i for i in (site.get("issues") or []) if i.get("severity") == "error"]
    copy_blockers = [
        a for a in db.list_artifacts(project_id)
        if a["kind"] == "copy" and a["status"] in {"ready", "published", "needs_review"}
        and any(i.get("severity") == "error" for i in (a.get("issues") or []))
    ]
    if site_errors or copy_blockers:
        detail = "; ".join(
            [str(i.get("message")) for i in site_errors][:3] +
            [f"{a['platform']}: fact issue" for a in copy_blockers][:5]
        )
        return {"ok": False, "blocked": True,
                "error": f"Publishing blocked by unresolved fact issues: {detail[:600]}"}

    result = publish_site(Path(site["content"]).parent, repo_value.strip(), True,
                          title=str(version.get("title") or ""))
    if result.get("ok"):
        state = "live" if result.get("verified") else "pending_verification"
        db.upsert_publication(project_id, "github_pages", remote_url=result.get("url", ""), state=state,
                              content_hash=site.get("content_hash", ""),
                              last_verified_at=db.now() if result.get("verified") else None)
        db.add_event(project_id, "published" if result.get("verified") else "publish_pending", result)
    return result


@app.get("/api/projects/{project_id}/export")
def export_project(project_id: str) -> FileResponse:
    item = db.get_project(project_id)
    if not item:
        raise HTTPException(404, "Project not found")
    project_dir = _project_dir(project_id)
    export_path = EXPORTS_DIR / f"{project_id}.zip"
    skip = {"video_work", "site_candidates", ".git"}
    labels = {"x_en": "X / Twitter (English)", "x_zh": "X / Twitter (中文)",
              "linkedin_en": "LinkedIn (English)", "wechat_zh": "微信公众号",
              "xhs_zh": "小红书"}
    copies = [a for a in db.list_artifacts(project_id) if a["kind"] == "copy" and (a.get("content") or "").strip()]
    copy_md = ["# Copy package", ""]
    for art in copies:
        copy_md += [f"## {labels.get(art.get('platform'), art.get('platform'))}", "", art["content"].strip(), ""]
    with zipfile.ZipFile(export_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in project_dir.rglob("*"):
            if path.is_file() and not any(part in skip for part in path.parts):
                archive.write(path, path.relative_to(project_dir))
        if len(copy_md) > 2:
            archive.writestr("copy.md", "\n".join(copy_md))
    return FileResponse(str(export_path), filename=f"{item['name']}-paperrelay.zip", media_type="application/zip")


def _auto_update_candidates(project_id: str) -> None:
    """Prepare update candidates after a source change, without touching manual edits."""
    if db.get_setting("maintenance_auto_update", "1") != "1":
        return
    if not db.get_project(project_id):
        return
    if any(j["status"] in ("queued", "running") for j in db.list_jobs(project_id, 5)):
        return
    version = db.current_version(project_id)
    start_job(project_id, "copy", {"auto_update": True, "version_id": version["id"] if version else ""})
    start_job(project_id, "site", {"auto_update": True, "version_id": version["id"] if version else ""})
    db.add_event(project_id, "auto_update_started", {"jobs": ["copy", "site"]})


@app.on_event("startup")
def startup() -> None:
    with db.db() as conn:
        conn.execute("UPDATE jobs SET status='failed', message='Interrupted by restart' WHERE status IN ('queued','running')")
        conn.execute("UPDATE artifacts SET status='failed' WHERE status='generating'")
        conn.execute("UPDATE claims SET status='candidate' WHERE status NOT IN ('candidate','verified')")
    set_regenerate_hook(_auto_update_candidates)
    start_scheduler()
