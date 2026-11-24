from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from typing import Any

import requests

UA = {"User-Agent": "PaperRelay/0.1 (local research tool; contact: local user)"}
S2 = "https://api.semanticscholar.org/graph/v1/paper"
S2_FIELDS = "title,authors,abstract,venue,year,externalIds,publicationVenue"
OPENALEX = "https://api.openalex.org/works"


def _get(url: str, params: dict[str, Any] | None = None, timeout: int = 20) -> requests.Response | None:
    for attempt in range(3):
        try:
            response = requests.get(url, params=params, headers=UA, timeout=timeout)
            if response.status_code == 200:
                return response
            if response.status_code in (429, 503):
                time.sleep(2 + attempt * 3)
                continue
            return None
        except Exception:
            time.sleep(1 + attempt)
    return None


def _norm_title(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def _similar(a: str, b: str) -> bool:
    na, nb = _norm_title(a), _norm_title(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    ta, tb = set(na.split()), set(nb.split())
    return len(ta & tb) / max(1, len(ta | tb)) >= 0.72


def _arxiv_entry(arxiv_id: str) -> dict[str, Any]:
    if not arxiv_id:
        return {}
    response = _get("https://export.arxiv.org/api/query", {"id_list": arxiv_id, "max_results": 1})
    if not response:
        return {}
    try:
        root = ET.fromstring(response.text)
        ns = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
        entry = root.find("a:entry", ns)
        if entry is None:
            return {}
        authors = [
            (author.findtext("a:name", default="", namespaces=ns) or "").strip()
            for author in entry.findall("a:author", ns)
        ]
        return {
            "title": (entry.findtext("a:title", default="", namespaces=ns) or "").strip(),
            "authors": [a for a in authors if a],
            "abstract": (entry.findtext("a:summary", default="", namespaces=ns) or "").strip(),
            "comment": (entry.findtext("arxiv:comment", default="", namespaces=ns) or "").strip(),
            "journal_ref": (entry.findtext("arxiv:journal_ref", default="", namespaces=ns) or "").strip(),
            "published": (entry.findtext("a:published", default="", namespaces=ns) or "").strip(),
        }
    except Exception:
        return {}


def _s2_paper(arxiv_id: str, title: str) -> dict[str, Any]:
    if arxiv_id:
        response = _get(f"{S2}/arXiv:{arxiv_id}", {"fields": S2_FIELDS})
        if response:
            try:
                return response.json()
            except Exception:
                pass
    if title:
        response = _get(f"{S2}/search", {"query": title[:180], "limit": 3, "fields": S2_FIELDS})
        if response:
            try:
                for paper in response.json().get("data") or []:
                    if _similar(paper.get("title", ""), title):
                        return paper
            except Exception:
                pass
    return {}


def _openalex(title: str) -> dict[str, Any]:
    response = _get(OPENALEX, {"search": title[:180], "per_page": 3,
                               "select": "title,publication_year,primary_location,authorships,doi,ids"})
    if not response:
        return {}
    try:
        for work in response.json().get("results") or []:
            if not _similar(work.get("title", ""), title):
                continue
            authors = [
                (a.get("author") or {}).get("display_name", "")
                for a in (work.get("authorships") or [])
            ]
            ids = work.get("ids") or {}
            arxiv = ""
            for value in ids.values():
                match = re.search(r"arxiv\.org/abs/(\d{4}\.\d{4,5})", str(value))
                if match:
                    arxiv = match.group(1)
                    break
            return {
                "title": work.get("title", ""),
                "authors": [a for a in authors if a],
                "year": str(work.get("publication_year") or ""),
                "doi": (work.get("doi") or "").replace("https://doi.org/", ""),
                "arxiv_id": arxiv,
            }
    except Exception:
        pass
    return {}


VENUE_ACRONYMS = {
    "international conference on learning representations": "ICLR",
    "conference on neural information processing systems": "NeurIPS",
    "neural information processing systems": "NeurIPS",
    "international conference on machine learning": "ICML",
    "annual meeting of the association for computational linguistics": "ACL",
    "north american chapter of the association for computational linguistics": "NAACL",
    "conference on empirical methods in natural language processing": "EMNLP",
    "ieee/cvf conference on computer vision and pattern recognition": "CVPR",
    "aaai conference on artificial intelligence": "AAAI",
}


def _venue_acronym(venue: str) -> str:
    key = re.sub(r"\s+", " ", venue.strip().lower())
    if key in VENUE_ACRONYMS:
        return VENUE_ACRONYMS[key]
    for full, short in VENUE_ACRONYMS.items():
        if key.startswith(full):
            return short
    return venue.strip()


def _venue_from_comment(comment: str, journal: str) -> tuple[str, str]:
    text = f"{comment} {journal}".strip()
    if not text:
        return "", ""
    match = re.search(
        r"((?:ICLR|NeurIPS|NIPS|ICML|ACL|EMNLP|NAACL|CVPR|ICCV|AAAI|IJCAI|KDD|SIGIR|TPAMI|TMLR)\s*(?:20\d{2})?)",
        text,
        re.I,
    )
    if match:
        return match.group(1), "arXiv metadata (Comments/Journal ref)"
    return "", ""


def enrich_metadata(title: str, arxiv_id: str = "", doi: str = "") -> dict[str, Any]:
    arxiv = _arxiv_entry(arxiv_id)
    seed_title = arxiv.get("title") or title
    result: dict[str, Any] = {
        "title": seed_title,
        "authors": arxiv.get("authors") or [],
        "abstract": arxiv.get("abstract") or "",
        "venue": "",
        "venue_source": "",
        "year": (arxiv.get("published") or "")[:4],
        "doi": doi,
        "arxiv_id": arxiv_id,
        "paper_url": f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else "",
        "code_url": "",
        "source": "arXiv API" if arxiv else "",
    }

    paper = _s2_paper(arxiv_id, seed_title)
    if paper and _similar(paper.get("title", ""), seed_title or title):
        # arXiv is authoritative for title/authors/abstract when available;
        # Semantic Scholar is used mainly for venue.
        result["title"] = result["title"] or paper.get("title") or ""
        if not result["authors"]:
            result["authors"] = [a.get("name", "") for a in (paper.get("authors") or []) if a.get("name")]
        result["abstract"] = result["abstract"] or paper.get("abstract") or ""
        result["year"] = result["year"] or str(paper.get("year") or "")
        result["source"] = f"Semantic Scholar ({paper.get('paperId', '')})"
        external = paper.get("externalIds") or {}
        result["arxiv_id"] = result["arxiv_id"] or external.get("ArXiv", "")
        result["doi"] = result["doi"] or external.get("DOI", "")
        if result["arxiv_id"] and not result["paper_url"]:
            result["paper_url"] = f"https://arxiv.org/abs/{result['arxiv_id']}"
        venue = paper.get("venue") or (paper.get("publicationVenue") or {}).get("name") or ""
        if venue:
            result["venue"] = _venue_acronym(venue)
            result["venue_source"] = f"Semantic Scholar ({paper.get('paperId', '')})"

    if not result["authors"] or not result["abstract"]:
        oa = _openalex(seed_title or title)
        if oa:
            result["title"] = result["title"] or oa.get("title", "")
            result["authors"] = result["authors"] or oa.get("authors", [])
            result["year"] = result["year"] or oa.get("year", "")
            result["doi"] = result["doi"] or oa.get("doi", "")
            result["arxiv_id"] = result["arxiv_id"] or oa.get("arxiv_id", "")
            if result["arxiv_id"] and not result["paper_url"]:
                result["paper_url"] = f"https://arxiv.org/abs/{result['arxiv_id']}"
            result["source"] = result["source"] or "OpenAlex"

    if not result["venue"]:
        venue, source = _venue_from_comment(arxiv.get("comment", ""), arxiv.get("journal_ref", ""))
        if venue:
            result["venue"] = venue
            result["venue_source"] = source

    result["authors"] = [a for a in result["authors"] if a]
    return result


def openreview_id(value: str) -> str:
    value = (value or "").strip()
    match = re.search(r"[?&]id=([^&#]+)", value)
    if match:
        return match.group(1)
    return value if re.fullmatch(r"[A-Za-z0-9_-]{6,}", value) else ""


def _openreview_note(note_id: str) -> dict[str, Any]:
    if not note_id:
        return {}
    for base in ("https://api2.openreview.net", "https://api.openreview.net"):
        response = _get(f"{base}/notes", {"forum": note_id, "limit": 1})
        if not response:
            continue
        try:
            notes = response.json().get("notes") or []
            if not notes:
                continue
            content = notes[0].get("content") or {}

            def value(key: str) -> str:
                item = content.get(key)
                if isinstance(item, dict):
                    item = item.get("value")
                if isinstance(item, list):
                    return ", ".join(str(v) for v in item if v)
                return str(item or "")

            title = value("title")
            venue = value("venue") or value("venueid")
            authors = value("authors")
            if title or venue or authors:
                return {
                    "title": title,
                    "venue": venue,
                    "authors": [a.strip() for a in authors.split(",") if a.strip()],
                    "source": f"OpenReview ({note_id})",
                    "url": f"https://openreview.net/forum?id={note_id}",
                }
        except Exception:
            continue
    return {}


def resolve_external(arxiv_id: str = "", openreview_url: str = "") -> dict[str, Any]:
    """Return candidate metadata only; never write it into the paper record."""
    result: dict[str, Any] = {"candidates": {}, "sources": [], "warnings": []}
    arxiv_id = (arxiv_id or "").strip()
    if arxiv_id:
        arxiv = _arxiv_entry(arxiv_id)
        if arxiv:
            result["candidates"].update({
                "title": arxiv.get("title", ""),
                "authors": arxiv.get("authors", []),
                "abstract": arxiv.get("abstract", ""),
                "year": (arxiv.get("published") or "")[:4],
                "arxiv_id": arxiv_id,
                "paper_url": f"https://arxiv.org/abs/{arxiv_id}",
            })
            result["sources"].append("arXiv API")
        else:
            result["warnings"].append(f"arXiv {arxiv_id} did not return an entry.")
    note_id = openreview_id(openreview_url)
    if openreview_url:
        note = _openreview_note(note_id)
        if note:
            result["candidates"].update({
                "title": note["title"],
                "authors": note["authors"],
                "venue": note["venue"],
                "venue_source": note["url"],
                "paper_url": note["url"],
            })
            result["sources"].append(note["source"])
        else:
            result["warnings"].append("OpenReview note could not be resolved; enter the venue source manually.")
    result["note"] = "Candidates are not applied automatically. Review them and save the paper card to confirm."
    return result
