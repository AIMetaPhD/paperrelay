from __future__ import annotations

import hashlib
import json
import re
from typing import Any

import requests

from .db import all_settings
from .facts import (
    code_confirmed,
    meaningful_claims,
    scrub_unverified,
    venue_confirmed,
    venue_label,
)
from .metadata import _venue_acronym

SYSTEM = (
    "You are a careful, independent research communications editor. Use only the supplied facts. "
    "Never invent numbers, authors, affiliations, venues, DOIs, links, awards, or citations. "
    "Keep conditions and limitations. If a fact is missing, omit it. "
    "Never write as the authors: do not use 'we', 'our', or '我们提出'. "
    "Do not call a checkpoint size a parameter count. "
    "Do not claim lower or faster inference latency unless the facts explicitly say lower; when the paper says "
    "'no additional inference latency', write exactly that. Avoid hype words such as revolutionize or groundbreaking. "
    "If the venue is marked UNCONFIRMED, never name a conference, journal, or year. "
    "If the code URL is marked UNCONFIRMED, never include a code link. "
    "Return the requested copy only."
)


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def facts_block(version: dict[str, Any], claims: list[dict[str, Any]]) -> str:
    authors = ", ".join(version.get("authors") or []) or "unknown"
    if venue_confirmed(version):
        venue_line = f"Venue: {version.get('venue')} (source: {version.get('venue_source')})"
    elif (version.get("venue") or "").strip():
        venue_line = (
            "Venue: UNCONFIRMED. A user-entered value exists but has no recorded source. "
            "Do not name any conference, journal, or year for the venue."
        )
    else:
        venue_line = (
            "Venue: UNCONFIRMED. Do not name any conference, journal, or year for the venue. "
            "Say the venue is not confirmed if a venue is needed."
        )
    if code_confirmed(version):
        code_line = f"Code URL: {version.get('code_url')} (confirmed by the user)"
    elif (version.get("code_url") or "").strip():
        code_line = (
            "Code URL: UNCONFIRMED. The link was auto-extracted from the PDF and not verified; "
            "do not include any code link."
        )
    else:
        code_line = "Code URL: none. Do not include any code link."
    lines = [
        f"Title: {version.get('title', '')}",
        f"Authors: {authors}",
        venue_line,
        f"Year: {version.get('year') or 'unknown'}",
        f"Paper URL: {version.get('paper_url') or 'unknown'}",
        code_line,
        "Abstract:",
        (version.get("abstract") or "")[:1800],
        "Claims extracted from the PDF (page + quote). 'candidate' means auto-extracted and not independently verified:",
    ]
    for claim in meaningful_claims(claims)[:12]:
        status = "verified" if claim.get("status") == "verified" else "candidate"
        lines.append(f"- [{status}] {claim['value']} | page {claim['source_page']} | {claim['source_quote'][:220]}")
    if not meaningful_claims(claims):
        lines.append("- none extracted; do not state any numeric result")
    return "\n".join(lines)


def _chat_completions(base_url: str, api_key: str, model: str, messages: list[dict[str, str]], timeout: int) -> str:
    response = requests.post(
        base_url.rstrip("/") + "/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": model, "messages": messages, "temperature": 0.4, "max_tokens": 1800},
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    return (data.get("choices") or [{}])[0].get("message", {}).get("content", "") or ""


def _chat_responses(base_url: str, api_key: str, model: str, messages: list[dict[str, str]], timeout: int) -> str:
    system = "\n".join(m["content"] for m in messages if m.get("role") == "system")
    user = "\n\n".join(m["content"] for m in messages if m.get("role") != "system")
    payload: dict[str, Any] = {"model": model, "input": user}
    if system:
        payload["instructions"] = system
    response = requests.post(
        base_url.rstrip("/") + "/responses",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    if data.get("error"):
        raise RuntimeError(str(data["error"])[:300])
    texts: list[str] = []
    for item in data.get("output") or []:
        if item.get("type") != "message":
            continue
        for part in item.get("content") or []:
            if part.get("type") in ("output_text", "text") and part.get("text"):
                texts.append(part["text"])
    if not texts and data.get("output_text"):
        texts.append(data["output_text"])
    return "\n".join(texts).strip()


def _chat(base_url: str, api_key: str, model: str, messages: list[dict[str, str]],
          timeout: int = 180, wire: str = "chat") -> str:
    if wire == "responses":
        return _chat_responses(base_url, api_key, model, messages, timeout)
    return _chat_completions(base_url, api_key, model, messages, timeout)


def check_model(settings: dict[str, str] | None = None) -> dict[str, Any]:
    settings = settings or all_settings()
    base = settings.get("llm_base_url", "")
    key = settings.get("llm_api_key", "")
    model = settings.get("llm_model", "")
    wire = settings.get("llm_wire_api", "chat") or "chat"
    if not base or not model:
        return {"ok": False, "error": "Base URL and model are required."}
    models: list[str] = []
    try:
        response = requests.get(base.rstrip("/") + "/models", headers={"Authorization": f"Bearer {key}"}, timeout=10)
        if response.status_code == 200:
            models = [m.get("id") for m in (response.json().get("data") or [])]
    except Exception:
        pass
    try:
        text = _chat(base, key, model, [{"role": "user", "content": "Reply with exactly: OK"}], timeout=60, wire=wire)
        return {"ok": True, "reply": text.strip()[:80], "models": models[:20], "wire": wire}
    except Exception as exc:
        first_error = str(exc)[:300]
    other = "responses" if wire == "chat" else "chat"
    try:
        text = _chat(base, key, model, [{"role": "user", "content": "Reply with exactly: OK"}], timeout=60, wire=other)
        return {
            "ok": True,
            "reply": text.strip()[:80],
            "models": models[:20],
            "wire": other,
            "hint": f"The gateway rejected '{wire}' but works with '{other}'. Save the protocol setting as {other}.",
        }
    except Exception as exc:
        return {"ok": False, "error": first_error, "wire": wire,
                "hint": f"Tried {wire} and {other}. Check that the gateway is running and the model id exists."}


def _template(version: dict[str, Any], claims: list[dict[str, Any]]) -> dict[str, str]:
    title = version.get("title") or "Untitled paper"
    authors = ", ".join(version.get("authors") or []) or "the authors"
    venue = venue_label(version, "en")
    link = version.get("paper_url") or version.get("doi") or ""
    code = version.get("code_url") if code_confirmed(version) else ""
    key_claims = [c["value"] for c in meaningful_claims(claims)[:3]]
    claim_line = "; ".join(key_claims) if key_claims else "a new method and analysis"
    venue_seg_en = f" · {venue}" if venue_confirmed(version) else ""
    venue_seg_zh = f" · {venue}" if venue_confirmed(version) else " · 发表信息未确认"
    x_en = (
        f"New paper: {title}\n\n"
        f"{authors}{venue_seg_en}\n\n"
        f"Reported results: {claim_line}.\n\n"
        f"Paper: {link}" + (f"\nCode: {code}" if code else "")
        + "\n\n#MachineLearning #Research"
    )
    x_zh = (
        f"新论文：{title}\n\n"
        f"{authors}{venue_seg_zh}\n\n"
        f"论文报告的结果：{claim_line}。\n\n"
        f"论文：{link}" + (f"\n代码：{code}" if code else "")
        + "\n\n#机器学习 #论文分享"
    )
    if venue_confirmed(version):
        intro_en = f"{authors} have released a new paper at {venue}."
    else:
        intro_en = f"{authors} have released a new paper. The publication venue is not confirmed."
    linkedin = (
        f"{title}\n\n"
        f"{intro_en} "
        f"The work reports {claim_line}. "
        f"Read the paper: {link}" + (f"\nCode: {code}" if code else "") + "\n"
    )
    venue_zh = venue if venue_confirmed(version) else "发表信息未确认"
    wechat = (
        f"## {title}\n\n"
        f"作者：{authors}\n\n"
        f"发表：{venue_zh}\n\n"
        f"论文报告的结果包括：{claim_line}。\n\n"
        f"论文链接：{link}\n" + (f"代码链接：{code}\n" if code else "")
        + "\n（文案由 PaperRelay 基于论文事实生成，发布前请核对。）"
    )
    xhs = (
        f"📄 新论文分享｜{title}\n\n"
        f"👥 {authors}\n"
        f"🏷️ {venue_zh}\n\n"
        f"✨ 论文报告的结果：{claim_line}\n\n"
        f"🔗 论文：{link}\n" + (f"💻 代码：{code}\n" if code else "")
        + "\n#科研 #论文 #机器学习"
    )
    return {"x_en": x_en, "x_zh": x_zh, "linkedin_en": linkedin, "wechat_zh": wechat, "xhs_zh": xhs}


def _parse_json(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except Exception:
        match = re.search(r"\{.*\}", text, re.S)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                return None
    return None


NUMBER_RE = re.compile(r"\d[\d,]*(?:\.\d+)?\s*(?:×|x|times|%|percent|TB|GB|MB|KB|B)?")


def _unknown_numbers(text: str, allowed: str) -> list[str]:
    allowed_numbers = {n.replace(",", "") for n in re.findall(r"\d[\d,]*(?:\.\d+)?", allowed)}
    unknown = []
    for match in NUMBER_RE.finditer(text):
        token = match.group(0).strip()
        base = re.match(r"\d[\d,]*(?:\.\d+)?", token)
        if not base:
            continue
        number = base.group(0).replace(",", "")
        if len(number) <= 2:
            continue
        if number.startswith("20") and len(number) == 4:
            continue
        if number in allowed_numbers or number.replace(".", "") in {n.replace(".", "") for n in allowed_numbers}:
            continue
        unknown.append(token)
    return sorted(set(unknown))


def fact_check(text: str, version: dict[str, Any], claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    allowed = facts_block(version, claims)
    issues: list[dict[str, Any]] = []
    unknown = _unknown_numbers(text, allowed)
    for token in unknown:
        issues.append({"type": "unknown_number", "value": token, "severity": "error",
                       "message": f"Number not found in verified facts: {token}"})
    venue = (version.get("venue") or "").strip()
    confirmed = venue_confirmed(version)
    negation = re.compile(r"未确认|未核实|尚未确认|unconfirmed|not confirmed|not verified|unknown venue", re.I)

    def _negated(match: re.Match) -> bool:
        window = text[max(0, match.start() - 12): match.end() + 12]
        return bool(negation.search(window))

    for match in re.finditer(r"\b(ICLR|NeurIPS|NIPS|ICML|ACL|EMNLP|NAACL|CVPR|ICCV|AAAI)\s*(20\d{2})?\b", text):
        if _negated(match):
            continue
        found = match.group(0).strip()
        if not confirmed:
            issues.append({"type": "venue_unverified", "value": found, "severity": "error",
                           "message": f"Copy states venue '{found}' but the venue is not confirmed (no recorded source)."})
        else:
            acronym = _venue_acronym(venue).lower().strip()
            found_lower = found.lower().strip()
            venue_lower = venue.lower().strip()
            mention_matches = (
                found_lower in venue_lower
                or venue_lower in found_lower
                or (acronym and (found_lower.startswith(acronym) or acronym in found_lower))
            )
            if not mention_matches:
                issues.append({"type": "venue_mismatch", "value": found, "severity": "error",
                               "message": f"Venue mention '{found}' does not match verified venue '{venue}'."})
    if not confirmed:
        venue_patterns = [
            r"(?:发表于|发表在|发表|presented|published|accepted)\s*(?:at|in|于)?\s*(?:the\s+)?[A-Za-z0-9]*(?:\s*20\d{2})?\s*(?:会议|conference|journal|期刊|workshop)",
            r"(?:在|于)\s*(?:the\s+)?(?:ICLR|NeurIPS|NIPS|ICML|ACL|EMNLP|NAACL|CVPR|ICCV|AAAI)",
            r"(?:ICLR|NeurIPS|NIPS|ICML|ACL|EMNLP|NAACL|CVPR|ICCV|AAAI)[A-Za-z0-9]*(?:\s*20\d{2})?\s*(?:会议|conference)",
            r"(?:会议|conference|journal)\s*(?:上|中|里)?\s*(?:发表|发布|presented)",
        ]
        for pattern in venue_patterns:
            match = re.search(pattern, text)
            if match and not _negated(match):
                issues.append({"type": "venue_unverified", "value": match.group(0)[:40], "severity": "error",
                               "message": "Copy names a venue while the venue is unconfirmed; record a source or remove it."})
                break
    if not confirmed and re.search(r"\bpreprint\b", text, re.I):
        issues.append({"type": "venue_unverified", "value": "preprint", "severity": "warning",
                       "message": "Venue is unconfirmed; copy uses the placeholder 'preprint'."})
    if venue and not (version.get("venue_source") or "").strip():
        issues.append({"type": "venue_source_missing", "severity": "warning",
                       "message": "A venue is entered but has no recorded source; it stays unconfirmed until a source is added."})
    if (version.get("code_url") or "").strip() and not code_confirmed(version):
        for url in re.findall(r"https?://github\.com/[A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-]+", text):
            issues.append({"type": "code_url_unverified", "value": url, "severity": "error",
                           "message": f"Copy includes code link {url} that was auto-extracted and not confirmed."})
            break
    for match in re.finditer(r"(?:[^.]{0,40}\b(?:MB|GB|TB)\b[^.]{0,40}\bparameters?\b|[^.]{0,40}\bparameters?\b[^.]{0,40}\b(?:MB|GB|TB)\b)", text, re.I):
        context = match.group(0).lower()
        if "checkpoint" not in context and "model size" not in context:
            issues.append({"type": "unit_confusion", "severity": "error",
                           "message": f"Storage size is being described as parameters: {match.group(0)[:140]}"})
            break
    if re.search(r"\b(?:we|our)\b[^.]{0,24}\b(?:propose|present|introduce|develop|method|package|model|work|provide|release)\b|我们(?:提出|开发|构建|做了|的方法|提供|发布|开源|实现)|我们的", text, re.I):
        issues.append({"type": "author_voice", "severity": "error",
                       "message": "Copy speaks as the authors; rewrite as an independent communicator."})
    if re.search(r"(?:lower|reduced|less|faster)\s+(?:inference\s+)?latency|降低[^。]{0,12}推理延迟|更低的推理延迟", text, re.I):
        issues.append({"type": "latency_claim", "severity": "error",
                       "message": "Paper says 'no additional inference latency'; do not claim lower latency."})
    if re.search(r"revolutioni[sz]e|groundbreaking|彻底|颠覆|史无前例", text, re.I):
        issues.append({"type": "hype", "severity": "warning",
                       "message": "Hype wording found; consider a more measured claim."})
    return issues


PLATFORM_SPECS = [
    ("x_en", "English X/Twitter thread. 3-5 posts separated by blank lines; each post under 280 characters; first post must stand alone; plain text, no markdown links formatting."),
    ("x_zh", "中文 X/Twitter 短帖，280 字以内，简洁有力，不要照搬摘要。"),
    ("linkedin_en", "English LinkedIn post, 120-200 words, professional but not hype; explain problem, method, evidence, and link."),
    ("wechat_zh", "中文微信公众号介绍稿，300-500 字，有自然段落和小标题；面向中文研究者，保留条件与局限。"),
    ("xhs_zh", "中文小红书分享稿，200-300 字，带 emoji 和 3-5 个 hashtag；语气真实，不要夸大。"),
]


def _normalize_voice(text: str) -> str:
    text = re.sub(r"\bour\b", "the", text, flags=re.I)
    text = re.sub(r"\bwe\b", "the authors", text, flags=re.I)
    text = text.replace("我们提供", "研究团队提供").replace("我们提出", "研究团队提出")
    text = text.replace("我们的", "研究团队的")
    text = re.sub(r"(^|[.!?]\s+|^#+\s*)the authors\b",
                  lambda m: m.group(1) + "The authors", text)
    return text


def _finish(text: str, version: dict[str, Any], platform_key: str) -> str:
    """Deterministic post-processing shared by every platform."""
    text = _normalize_voice(text)
    text = scrub_unverified(text, version)
    links: list[str] = []
    paper_url = version.get("paper_url") or ""
    code_url = version.get("code_url") or ""
    if paper_url and paper_url not in text:
        links.append(paper_url)
    if code_url and code_confirmed(version) and code_url not in text:
        links.append(code_url)
    if links:
        label = "链接：" if platform_key.endswith("_zh") else "Links: "
        text = text.rstrip() + "\n\n" + label + " · ".join(links)
    return text


def generate_copy(version: dict[str, Any], claims: list[dict[str, Any]], settings: dict[str, str] | None = None) -> dict[str, Any]:
    settings = settings or all_settings()
    base = settings.get("llm_base_url", "")
    key = settings.get("llm_api_key", "")
    model = settings.get("llm_model", "")
    wire = settings.get("llm_wire_api", "chat") or "chat"
    facts = facts_block(version, claims)
    fallback = _template(version, claims)
    content: dict[str, str] = {}
    issues: list[dict[str, Any]] = []
    used_llm = False
    llm_failed = False
    for platform_key, instruction in PLATFORM_SPECS:
        text = ""
        platform_issues: list[dict[str, Any]] = []
        try:
            prompt = (
                f"Write one piece of promotional copy for the paper below.\n"
                f"Platform requirement: {instruction}\n"
                f"Use only the facts below. Do not invent numbers, authors, venues, or links. "
                f"If the venue is UNCONFIRMED, never name a conference or journal. "
                f"If the code URL is UNCONFIRMED, never include a code link. "
                f"Keep conditions and limitations. Return the copy text only, no JSON, no preamble.\n\n{facts}"
            )
            raw = _chat(base, key, model,
                        [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
                        wire=wire)
            text = raw.strip()
            if text.startswith("```"):
                text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
                text = re.sub(r"\s*```$", "", text).strip()
            if len(text) < 40:
                raise ValueError("Model returned too little text.")
            used_llm = True
        except Exception as exc:
            text = fallback[platform_key]
            llm_failed = True
            platform_issues.append({"type": "llm_unavailable", "severity": "warning",
                                    "message": f"{platform_key}: LLM failed; deterministic template used. {str(exc)[:180]}"})
        text = _finish(text, version, platform_key)
        content[platform_key] = text
        platform_issues.extend(fact_check(text, version, claims))
        if platform_key == "x_en":
            for post in [p for p in text.split("\n\n") if p.strip()]:
                if len(post) > 280:
                    platform_issues.append({"type": "platform_length", "severity": "warning",
                                            "message": f"X post is {len(post)} characters; target is <=280."})
        if len(text.strip()) < 40:
            platform_issues.append({"type": "too_short", "severity": "error",
                                    "message": f"{platform_key} is shorter than 40 characters."})
        for issue in platform_issues:
            issue["platform"] = platform_key
        issues.extend(platform_issues)
    unique = []
    seen = set()
    for issue in issues:
        marker = (issue.get("type"), issue.get("value"), issue.get("message"))
        if marker not in seen:
            seen.add(marker)
            unique.append(issue)
    return {
        "content": content,
        "issues": unique,
        "used_llm": used_llm,
        "llm_failed": llm_failed,
        "wire": wire,
        "facts": facts,
        "content_hash": content_hash(json.dumps(content, sort_keys=True, ensure_ascii=False)),
    }
