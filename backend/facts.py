"""Shared fact policy.

Every generator (copy, video, site) must agree on the same confirmed facts.
A fact is confirmed only when it has a recorded source:

* venue   -> venue + venue_source
* code    -> code_url + code_url_confirmed == 1
* claims  -> extracted from the paper with a page and a quote, and meaningful
             (a bare storage size such as "384 MB" is not a result)
"""

from __future__ import annotations

import re
from typing import Any

VENUE_TOKEN = (
    r"(?:ICLR|NeurIPS|NIPS|ICML|ACL|EMNLP|NAACL|CVPR|ICCV|ECCV|AAAI|IJCAI|KDD|SIGIR|"
    r"TPAMI|TMLR|AISTATS|UAI|COLT|ICRA|IROS|MICCAI|WWW|CIKM|WSDM)"
)
SIZE_UNITS = re.compile(r"\b(?:TB|GB|MB|KB)\b", re.I)
RESULT_UNITS = re.compile(
    r"×|\d\s*x\b|\btimes\b|%|percent|percentage points?|\bpoints?\b|BLEU|perplexity|\bppl\b|"
    r"speedup|GPUs?|hours?|days?|tokens?",
    re.I,
)
COMPARATIVE = re.compile(
    r"reduc|improv|outperform|speedup|faster|fewer|higher|lower|than|compared|"
    r"vs\.?|while|without|instead|仅|相比|降低|提升",
    re.I,
)


def venue_confirmed(version: dict[str, Any]) -> bool:
    return bool((version.get("venue") or "").strip() and (version.get("venue_source") or "").strip())


def code_confirmed(version: dict[str, Any]) -> bool:
    if not (version.get("code_url") or "").strip():
        return False
    try:
        return int(version.get("code_url_confirmed") or 0) == 1
    except Exception:
        return False


def claim_is_meaningful(claim: dict[str, Any]) -> bool:
    value = (claim.get("value") or "").strip()
    quote = claim.get("source_quote") or ""
    if not value:
        return False
    if SIZE_UNITS.search(value) and not RESULT_UNITS.search(value):
        # "1.2 TB -> 350 GB" is a result; a lone "384 MB" is a model size.
        return bool(COMPARATIVE.search(quote))
    return bool(RESULT_UNITS.search(value))


def meaningful_claims(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [c for c in claims if claim_is_meaningful(c)]


def venue_label(version: dict[str, Any], lang: str = "en") -> str:
    if venue_confirmed(version):
        return str(version["venue"]).strip()
    return "venue not confirmed" if lang == "en" else "发表信息未确认"


def _strip_code_links(text: str) -> str:
    text = re.sub(r"(?im)^\s*(?:code|代码)\s*[:：].*$", "", text)
    text = re.sub(r"(?i)\s*(?:the\s+)?code\s+(?:is\s+|will\s+be\s+)?(?:available|released|public)?\s*(?:at|on)?\s*https?://\S+", "", text)
    text = re.sub(r"(?i)\s*代码(?:链接)?\s*[:：]?\s*https?://\S+", "", text)
    text = re.sub(r"https?://github\.com/\S+", "", text)
    # Remove labels left behind by URL removal ("Code:", "代码：").
    text = re.sub(r"(?i)\b(code|代码)(?:\s*链接)?\s*[:：]\s*(?=[.。;；,，\s]|$)", "", text)
    text = re.sub(r"(?i)\s*\bcode\s+(?:is\s+)?(?:available|released)\s+(?:at|on)\b\s*(?=[.。]|$)", "", text)
    return text


def scrub_unverified(text: str, version: dict[str, Any]) -> str:
    """Remove unconfirmed venue/code mentions from generated prose.

    The model is instructed not to invent facts, but a deterministic scrub keeps
    the promise even when the model ignores the prompt.
    """
    if not text:
        return text
    if not venue_confirmed(version):
        patterns = [
            rf"(?i)\s*(?:published|presented|accepted)\s+(?:at|to|in)\s+(?:the\s+)?{VENUE_TOKEN}\s*(?:20\d{{2}})?",
            rf"(?i)\s*(?:at|from|in)\s+(?:the\s+)?{VENUE_TOKEN}\s*(?:20\d{{2}})?",
            rf"(?i)\s*[·|]\s*{VENUE_TOKEN}\s*(?:20\d{{2}})?",
            rf"(?i)\s*(?:发表于|发表在|被)\s*{VENUE_TOKEN}?\s*(?:20\d{{2}})?\s*(?:会议|期刊)?",
            r"(?i)\s*published\s+at\s+preprint",
            r"(?i)\s*presented\s+at\s+preprint",
        ]
        for pattern in patterns:
            text = re.sub(pattern, "", text)
    if not code_confirmed(version):
        text = _strip_code_links(text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\s+([.,;:!?])", r"\1", text)
    text = re.sub(r"\.\s*\.(?!\.)", ".", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"(?m)^[ \t]+$", "", text)
    text = re.sub(r"(?m)^[.,;:!?]\s*$", "", text)
    return text.strip()


def fact_snapshot(version: dict[str, Any]) -> dict[str, Any]:
    """The single confirmed-fact view shared by copy, video and site."""
    return {
        "title": version.get("title") or "",
        "authors": version.get("authors") or [],
        "venue": str(version.get("venue") or "").strip() if venue_confirmed(version) else "",
        "venue_confirmed": venue_confirmed(version),
        "venue_source": str(version.get("venue_source") or "").strip(),
        "code_url": str(version.get("code_url") or "").strip() if code_confirmed(version) else "",
        "code_confirmed": code_confirmed(version),
        "paper_url": version.get("paper_url") or "",
        "doi": version.get("doi") or "",
        "year": version.get("year") or "",
        "abstract": version.get("abstract") or "",
    }
