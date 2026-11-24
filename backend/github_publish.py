from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Any

import requests


def _run(args: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
    proc = subprocess.run(args, cwd=str(cwd) if cwd else None, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def github_status() -> dict[str, Any]:
    code, out, err = _run(["gh", "api", "user", "--jq", ".login"])
    if code != 0:
        return {"ok": False, "error": (err or out or "gh is not authenticated")[:300]}
    return {"ok": True, "account": out.strip()}


def _pages_state(repo: str) -> dict[str, Any]:
    code, out, err = _run(["gh", "api", f"repos/{repo}/pages", "--jq", "{status:.status,url:.html_url}"])
    if code != 0:
        return {}
    import json
    try:
        return json.loads(out)
    except Exception:
        return {}


def _latest_build(repo: str) -> dict[str, Any]:
    code, out, err = _run(["gh", "api", f"repos/{repo}/pages/builds/latest", "--jq", "{status:.status,error:.error.message}"])
    if code != 0:
        return {}
    import json
    try:
        return json.loads(out)
    except Exception:
        return {}


def _enable_pages(repo: str) -> tuple[bool, str]:
    code, out, err = _run(["gh", "api", "-X", "POST", f"repos/{repo}/pages",
                           "-f", "source[branch]=main", "-f", "source[path]=/"])
    if code == 0:
        return True, ""
    # Pages may already exist; update the source instead.
    code2, out2, err2 = _run(["gh", "api", "-X", "PUT", f"repos/{repo}/pages",
                              "-f", "source[branch]=main", "-f", "source[path]=/"])
    if code2 == 0:
        return True, ""
    return False, (err2 or out2 or err or out)[:400]


def _verify_live(url: str, title: str, attempts: int = 24, delay: float = 5.0) -> dict[str, Any]:
    """Return live=True only after the URL actually serves the generated page."""
    last = ""
    for _ in range(attempts):
        try:
            response = requests.get(url, timeout=15, headers={"User-Agent": "PaperRelay/0.1"})
            last = f"HTTP {response.status_code}"
            if response.status_code == 200:
                body = response.text
                if (title and title[:40].lower() in body.lower()) or "PaperRelay" in body:
                    return {"live": True, "http_status": 200}
                last = "HTTP 200 but page content does not match the generated site"
        except Exception as exc:
            last = str(exc)[:200]
        time.sleep(delay)
    return {"live": False, "error": last or "no response"}


def publish_site(site_dir: Path, repo: str, approve: bool = False, title: str = "") -> dict[str, Any]:
    if not approve:
        return {
            "ok": False,
            "blocked": True,
            "error": "Publishing requires explicit human approval. Re-run with approve=true after reviewing the site.",
        }
    if not repo or "/" not in repo:
        return {"ok": False, "error": "Repository must be owner/name."}
    status = github_status()
    if not status.get("ok"):
        return {"ok": False, "blocked": True, "error": status.get("error", "GitHub is not authenticated.")}

    code, out, err = _run(["gh", "repo", "view", repo, "--json", "name,visibility"])
    if code != 0:
        return {
            "ok": False,
            "error": (
                f"Repository {repo} is not accessible. PaperRelay never creates public repositories automatically; "
                "create the repository yourself and grant this account access. "
                + (err or out)[:400]
            ),
        }

    if not (site_dir / ".git").exists():
        for args in (["git", "init"], ["git", "checkout", "-b", "main"]):
            code, out, err = _run(args, cwd=site_dir)
            if code != 0:
                return {"ok": False, "error": (err or out)[:500]}
    _run(["git", "add", "-A"], cwd=site_dir)
    _run(["git", "commit", "-m", "Publish paper project page"], cwd=site_dir)
    _run(["git", "remote", "remove", "origin"], cwd=site_dir)
    code, out, err = _run(["git", "remote", "add", "origin", f"https://github.com/{repo}.git"], cwd=site_dir)
    if code != 0:
        return {"ok": False, "error": (err or out)[:500]}
    code, out, err = _run(["git", "push", "-u", "origin", "main"], cwd=site_dir)
    if code != 0:
        return {"ok": False, "error": (err or out)[:500]}

    enabled, enable_error = _enable_pages(repo)
    if not enabled:
        return {"ok": False, "pushed": True, "error": f"Pushed, but GitHub Pages could not be enabled: {enable_error}"}

    owner, name = repo.split("/", 1)
    url = f"https://{owner}.github.io/{name}/"
    verification = _verify_live(url, title)
    if verification.get("live"):
        return {"ok": True, "repo": repo, "url": url, "verified": True,
                "message": "GitHub Pages build is live and serves the generated page."}
    return {
        "ok": True,
        "repo": repo,
        "url": url,
        "verified": False,
        "live": False,
        "message": (
            "Pushed and Pages was enabled, but the public URL did not serve the generated page "
            f"within the verification window ({verification.get('error', 'unknown error')}). "
            "It is recorded as pending verification, not as live."
        ),
    }
