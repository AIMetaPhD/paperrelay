from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF

from .facts import claim_is_meaningful

NOISE = re.compile(
    r"arxiv|preprint|under review|published as|copyright|proceedings|conference on|"
    r"doi:|https?://|all rights reserved|draft|version",
    re.I,
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _clean(text: str) -> str:
    for source, target in {"ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl", "ﬅ": "ft", "ﬆ": "st"}.items():
        text = text.replace(source, target)
    text = text.replace("­", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _title_from_page(page: fitz.Page) -> str:
    try:
        data = page.get_text("dict")
    except Exception:
        return ""
    rows: list[tuple[float, str]] = []
    for block in data.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            text = "".join(span.get("text", "") for span in spans).strip()
            size = max((float(span.get("size") or 0) for span in spans), default=0)
            if text and not NOISE.search(text) and len(text) >= 6:
                rows.append((size, text))
    if not rows:
        return ""
    max_size = max(size for size, _ in rows)
    lines = [text for size, text in rows if abs(size - max_size) < 0.35][:3]
    title = ""
    for line in lines:
        if not title:
            title = line
        elif title.endswith("-") and line[:1].isupper():
            title = title[:-1] + line
        else:
            title = title + " " + line
    return _clean(title)[:300]


def _authors_from_page(page: fitz.Page, title: str) -> list[str]:
    text = page.get_text("text")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return []
    start = 0
    for idx, line in enumerate(lines[:25]):
        if title and title.lower()[:30] in line.lower():
            start = idx + 1
            break
    candidates: list[str] = []
    for line in lines[start : start + 8]:
        if re.search(r"abstract|introduction|@|university|institute|department|microsoft|google", line, re.I):
            break
        if 2 <= len(line) <= 160:
            candidates.append(line)
    joined = " ".join(candidates)
    joined = re.sub(r"[\d\*†‡§¶]+", "", joined)
    parts = re.split(r",| and |;", joined)
    names = []
    for part in parts:
        part = part.strip(" .")
        if 2 <= len(part) <= 60 and re.search(r"[A-Za-z]", part):
            names.append(part)
    return names[:12]


def _abstract_from_text(text: str) -> str:
    match = re.search(
        r"(?is)\babstract\b\s*[—\-:]?\s*(.{200,2400}?)(?:\n\s*(?:1\s+)?introduction\b|\n\s*keywords?\b)",
        text,
    )
    if match:
        return _clean(match.group(1))
    idx = text.lower().find("abstract")
    if idx >= 0:
        return _clean(text[idx + 8 : idx + 1600])
    return _clean(text[:1200])


GENERIC_REPOS = {
    "tensorflow/tensor2tensor", "tensorflow/models", "pytorch/pytorch",
    "tensorflow/tensorflow", "huggingface/transformers", "google/jax",
    "openai/gpt-2", "openai/gpt-3", "microsoft/DeepSpeed",
    "tensorflow/t2t", "tensorflow/mesh", "google/flax",
}


def _code_url(text: str) -> str:
    """Pick the paper's own code repository, only with semantic evidence.

    A bare GitHub URL in a footnote is not the paper's code (BERT's
    tensor2tensor case). Require the URL to sit next to code-release or
    implementation wording; otherwise return "" and let the user confirm it.
    """
    raw = text[:20000]
    head = _clean(raw)
    candidates = [m.group(0).rstrip(".,;)") for m in re.finditer(
        r"https?://github\.com/[A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-]+", head)]
    if not candidates:
        return ""
    strong = re.compile(
        r"(?i)\b(code|implementation|source code|software|repository|codebase)\b[^.\n]{0,90}?"
        r"(?:is|are|will be|available|released|publicly|found|hosted)\s*(?:at|on)?\s*"
        r"(https?://github\.com/[A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-]+)")
    for match in strong.finditer(head):
        url = match.group(2)
        if url in candidates:
            owner_repo = url.split("github.com/")[-1].lower()
            if owner_repo not in GENERIC_REPOS:
                return url
    # "Our code: https://github.com/..." / "Implementation: <url>"
    labeled = re.compile(
        r"(?i)\b(code|implementation|codebase|source code)\b\s*[:：\-–]?\s*"
        r"(https?://github\.com/[A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-]+)")
    for match in labeled.finditer(head):
        url = match.group(2)
        owner_repo = url.split("github.com/")[-1].lower()
        if owner_repo not in GENERIC_REPOS:
            return url
    return ""


def _links_from_text(text: str) -> dict[str, str]:
    head = text[:4000]
    links = {"paper_url": "", "code_url": "", "project_url": "", "doi": "", "arxiv_id": ""}
    arxiv = re.search(r"arxiv\s*:\s*(\d{4}\.\d{4,5})", head, re.I)
    if not arxiv:
        arxiv = re.search(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})", head, re.I)
    if arxiv:
        links["arxiv_id"] = arxiv.group(1)
        links["paper_url"] = f"https://arxiv.org/abs/{arxiv.group(1)}"
    doi = re.search(r"\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+\b", head)
    if doi:
        links["doi"] = doi.group(0).rstrip(".,;)")
    code_url = _code_url(text)
    if code_url:
        links["code_url"] = code_url
    project = re.search(r"https?://[A-Za-z0-9_.\-]+\.(?:github\.io|ai|org|io)/[A-Za-z0-9_./\-]*", head)
    if project and project.group(0) != links["code_url"] and "arxiv.org" not in project.group(0):
        links["project_url"] = project.group(0).rstrip(".,;)")
    return links


CLAIM_PATTERN = re.compile(
    r"(?i)\d[\d,\.]*\s*(?:×|x|times|%|percent|percentage points?|points?|BLEU|TB|GB|MB|KB|hours?|days?|GPUs?|tokens?|perplexity|ppl)\b"
)


def _score_claim(sentence: str, matched: str) -> int:
    score = 0
    low = sentence.lower()
    if re.search(r"×|times|%|percent|BLEU|points?", matched, re.I):
        score += 6
    if re.search(r"\b(?:TB|GB|MB|KB)\b", matched, re.I):
        score += 4
    if re.search(r"reduce|improve|outperform|speedup|faster|fewer|higher|lower", low):
        score += 3
    if len(re.sub(r"\D", "", matched)) >= 3:
        score += 1
    if re.search(r"et al\.|arxiv|https?://|references", low):
        score -= 20
    if len(sentence) > 300:
        score -= 2
    return score


def _claims_from_pages(pages: list[str]) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    seen_keys: set[str] = set()
    for page_no, text in enumerate(pages[:12], start=1):
        for sentence in re.split(r"(?<=[.!?])\s+", text):
            sentence = _clean(sentence)
            if len(sentence) < 25:
                continue
            for match in CLAIM_PATTERN.finditer(sentence):
                value = _clean(match.group(0))
                if re.fullmatch(r"\d\s*[×x]", value):
                    continue
                if _score_claim(sentence, value) <= 0:
                    continue
                if not claim_is_meaningful({"value": value, "source_quote": sentence}):
                    # A bare storage size ("384 MB") is a model size, not a result.
                    continue
                key = re.sub(r"\s+", " ", value)[:60]
                unit_match = re.search(r"(×|x|times|%|percent|TB|GB|MB|KB)\b", value, re.I)
                unit = unit_match.group(1) if unit_match else ""
                dedup = (key.lower(), sentence[:80].lower())
                if dedup in seen or key.lower() in seen_keys:
                    continue
                seen.add(dedup)
                seen_keys.add(key.lower())
                claims.append(
                    {
                        "key": key,
                        "value": value,
                        "unit": unit,
                        "page": page_no,
                        "quote": sentence[:300],
                        "status": "supported",
                        "_score": _score_claim(sentence, value),
                    }
                )
    claims.sort(key=lambda c: (c["page"], -c["_score"]))
    for claim in claims:
        claim.pop("_score", None)
    return claims[:12]


def _non_white_ratio(pix: fitz.Pixmap) -> float:
    try:
        samples = pix.samples
        if not samples:
            return 0.0
        step = max(1, len(samples) // 4000)
        values = samples[::step]
        non_white = sum(1 for b in values if b < 245)
        return non_white / max(1, len(values))
    except Exception:
        return 1.0


def _union_rect(rects: list[fitz.Rect]) -> fitz.Rect | None:
    if not rects:
        return None
    rect = fitz.Rect(rects[0])
    for r in rects[1:]:
        rect |= r
    return rect


def _figure_rect(page: fitz.Page, caption: fitz.Rect, blocks: list[Any]) -> fitz.Rect | None:
    x0, x1 = caption.x0 - 20, caption.x1 + 20
    candidates: list[fitz.Rect] = []

    def intersects(rect: fitz.Rect) -> bool:
        return rect.x1 > x0 and rect.x0 < x1 and rect.y1 < caption.y0 - 4 and rect.y0 > caption.y0 - 430

    try:
        for drawing in page.get_drawings():
            rect = fitz.Rect(drawing.get("rect"))
            if intersects(rect) and rect.width > 30 and rect.height > 20:
                candidates.append(rect)
    except Exception:
        pass
    try:
        for info in page.get_image_info():
            rect = fitz.Rect(info.get("bbox"))
            if intersects(rect):
                candidates.append(rect)
    except Exception:
        pass

    union = _union_rect(candidates)
    if union and union.height > 60 and union.width > 90:
        return fitz.Rect(max(20, union.x0 - 6), max(20, union.y0 - 6),
                         min(page.rect.width - 20, union.x1 + 6), min(caption.y0 - 3, union.y1 + 6))

    previous_bottom = 40.0
    for other in blocks:
        if other[6] != 0:
            continue
        if not (other[2] > x0 and other[0] < x1):
            continue
        bottom = float(other[3])
        if bottom < caption.y0 - 5 and bottom > previous_bottom:
            previous_bottom = bottom
    top = max(36.0, previous_bottom + 4)
    if caption.y0 - top < 60:
        return None
    return fitz.Rect(max(30, x0), top, min(page.rect.width - 30, x1), caption.y0 - 4)


def _figures_from_pdf(doc: fitz.Document, outdir: Path) -> list[dict[str, Any]]:
    outdir.mkdir(parents=True, exist_ok=True)
    figures: list[dict[str, Any]] = []
    seen_pages: set[int] = set()
    for page_index in range(min(len(doc), 20)):
        page = doc[page_index]
        blocks = page.get_text("blocks")
        caption_blocks = [
            b for b in blocks
            if b[6] == 0 and re.match(r"^\s*(figure|fig\.)\s*\d+", str(b[4]).strip(), re.I)
        ]
        for cap_index, block in enumerate(caption_blocks):
            page_no = page_index + 1
            if page_no in seen_pages:
                continue
            caption_rect = fitz.Rect(block[:4])
            rect = _figure_rect(page, caption_rect, blocks)
            if rect is None:
                continue
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=rect, alpha=False)
            if _non_white_ratio(pix) < 0.012:
                continue
            filename = f"fig_p{page_no}_{cap_index + 1}.png"
            path = outdir / filename
            pix.save(str(path))
            caption = _clean(str(block[4]))
            figures.append(
                {
                    "file": filename,
                    "path": str(path),
                    "page": page_no,
                    "caption": caption[:240],
                    "width": pix.width,
                    "height": pix.height,
                }
            )
            seen_pages.add(page_no)
            break
        if len(figures) >= 4:
            break
    if not figures:
        page = doc[0]
        rect = fitz.Rect(36, 60, page.rect.width - 36, page.rect.height * 0.58)
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=rect, alpha=False)
        path = outdir / "fig_p1_page.png"
        pix.save(str(path))
        figures.append(
            {
                "file": path.name,
                "path": str(path),
                "page": 1,
                "caption": "First page (no figure caption detected)",
                "width": pix.width,
                "height": pix.height,
            }
        )
    return figures


def extract_pdf(pdf_path: Path, project_dir: Path) -> dict[str, Any]:
    doc = fitz.open(str(pdf_path))
    pages = [_clean(page.get_text("text")) for page in doc]
    full_text = "\n\n".join(pages)
    meta = doc.metadata or {}
    title = _clean(meta.get("title") or "") or _title_from_page(doc[0])
    authors = _authors_from_page(doc[0], title)
    abstract = _abstract_from_text(full_text)
    links = _links_from_text(full_text)
    figures = _figures_from_pdf(doc, project_dir / "figures")
    claims = _claims_from_pages(pages)
    page_count = len(doc)
    doc.close()
    return {
        "title": title[:300],
        "authors": authors,
        "abstract": abstract,
        "text": full_text,
        "pages": page_count,
        "figures": figures,
        "claims": claims,
        "links": links,
    }
