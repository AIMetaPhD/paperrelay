from __future__ import annotations

import html
import re
import shutil
from pathlib import Path
from typing import Any

from .facts import code_confirmed, meaningful_claims, venue_label


def _bibtex(version: dict[str, Any]) -> str:
    title = version.get("title") or "Untitled"
    authors = " and ".join(version.get("authors") or [])
    venue = (version.get("venue") or "").strip() if venue_label(version) != "venue not confirmed" else ""
    year = version.get("year") or ""
    venue_year = re.search(r"(20\d{2})", venue)
    if venue_year:
        year = venue_year.group(1)
    key = (authors.split(" and ")[0].split()[-1] if authors else "paper") + (year or "")
    entry = "misc" if not venue else "inproceedings"
    fields = [f"  title={{{title}}}"]
    if authors:
        fields.append(f"  author={{{authors}}}")
    if year:
        fields.append(f"  year={{{year}}}")
    if venue:
        fields.append(f"  booktitle={{{venue}}}")
    if version.get("doi"):
        fields.append(f"  doi={{{version['doi']}}}")
    if version.get("paper_url"):
        fields.append(f"  url={{{version['paper_url']}}}")
    return f"@{entry}{{{key},\n" + ",\n".join(fields) + "\n}"


def generate_site(version: dict[str, Any], claims: list[dict[str, Any]], artifacts: list[dict[str, Any]],
                  outdir: Path) -> Path:
    outdir.mkdir(parents=True, exist_ok=True)
    assets = outdir / "assets"
    assets.mkdir(exist_ok=True)
    (assets / "figures").mkdir(exist_ok=True)

    figure_paths = []
    for fig in version.get("figures") or []:
        src = Path(fig.get("path", ""))
        if src.exists():
            dst = assets / "figures" / src.name
            shutil.copy2(src, dst)
            figure_paths.append((f"assets/figures/{src.name}", fig.get("caption", "")))

    video = next((a for a in artifacts if a["kind"] == "video" and a["status"] in {"ready", "needs_review", "published"}), None)
    if video:
        for name in ("video.mp4", "video.srt", "video.vtt"):
            src = Path(video["content"]) / name
            if src.exists():
                shutil.copy2(src, assets / name)

    title = html.escape(version.get("title") or "Research paper")
    authors = html.escape(", ".join(version.get("authors") or []) or "Unknown authors")
    venue = html.escape(venue_label(version))
    abstract = html.escape(version.get("abstract") or "")
    paper_url = html.escape(version.get("paper_url") or "")
    code_url = html.escape(version.get("code_url") or "") if code_confirmed(version) else ""
    doi = html.escape(version.get("doi") or "")
    canonical = paper_url or "https://example.invalid/"
    bib = html.escape(_bibtex(version))

    claims_html = "".join(
        f"<li><strong>{html.escape(c['value'])}</strong><span>{html.escape(c['source_quote'][:220])}</span></li>"
        for c in meaningful_claims(claims)[:6]
    ) or "<li><strong>No numeric result extracted</strong><span>Read the paper for the reported results.</span></li>"
    figures_html = "".join(
        f'<figure><img src="{html.escape(src)}" alt=""><figcaption>{html.escape(cap)}</figcaption></figure>'
        for src, cap in figure_paths[:4]
    )
    video_html = ""
    if video and (assets / "video.mp4").exists():
        track = '<track kind="subtitles" srclang="en" src="assets/video.vtt" default>' if (assets / "video.vtt").exists() else ""
        video_html = (
            '<section class="video"><h2>Paper walkthrough</h2>'
            f'<video controls preload="metadata" src="assets/video.mp4">{track}</video>'
            '<p><a href="assets/video.mp4" download>Download MP4</a> · <a href="assets/video.srt" download>SRT</a></p></section>'
        )
    og_image = f"assets/figures/{figure_paths[0][0].split('/')[-1]}" if figure_paths else ""
    links = []
    if paper_url:
        links.append(f'<a class="btn" href="{paper_url}">Paper</a>')
    if code_url:
        links.append(f'<a class="btn ghost" href="{code_url}">Code</a>')
    if doi:
        links.append(f'<a class="btn ghost" href="https://doi.org/{doi}">DOI</a>')

    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{abstract[:180]}">
<link rel="canonical" href="{canonical}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{abstract[:180]}">
<meta property="og:type" content="article">
{f'<meta property="og:image" content="{html.escape(og_image)}">' if og_image else ''}
<meta name="twitter:card" content="summary_large_image">
<style>
:root{{--ink:#14202a;--muted:#5d6f7c;--paper:#f7f3ea;--card:#fffdf8;--accent:#b4552d;--line:#ddd3c4}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--paper);color:var(--ink);font-family:'Segoe UI',system-ui,sans-serif;line-height:1.65}}
.wrap{{max-width:1040px;margin:0 auto;padding:56px 24px 96px}}
header{{border-bottom:1px solid var(--line);padding-bottom:32px;margin-bottom:40px}}
.eyebrow{{letter-spacing:.22em;text-transform:uppercase;font-size:12px;color:var(--accent);font-weight:700}}
h1{{font-family:Georgia,'Times New Roman',serif;font-size:clamp(30px,5vw,52px);line-height:1.1;margin:14px 0 18px}}
h2{{font-family:Georgia,serif;font-size:28px;margin:44px 0 14px}}
.authors{{color:var(--muted);font-size:17px}}
.venue{{display:inline-block;margin-top:12px;padding:4px 12px;border:1px solid var(--line);border-radius:999px;font-size:13px}}
.links{{display:flex;gap:10px;flex-wrap:wrap;margin-top:24px}}
.btn{{display:inline-block;padding:10px 18px;border-radius:8px;background:var(--ink);color:#fff;text-decoration:none;font-weight:600}}
.btn.ghost{{background:transparent;color:var(--ink);border:1px solid var(--line)}}
section{{margin-top:36px}}
p{{max-width:72ch}}
ul.claims{{list-style:none;padding:0;display:grid;gap:14px}}
ul.claims li{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px 20px}}
ul.claims strong{{display:block;font-size:22px;color:var(--accent);font-family:Georgia,serif}}
ul.claims span{{display:block;color:var(--muted);font-size:14px;margin-top:6px}}
figure{{margin:28px 0;background:#fff;border:1px solid var(--line);border-radius:12px;padding:14px}}
figure img{{width:100%;height:auto;display:block}}
figcaption{{color:var(--muted);font-size:13px;margin-top:10px}}
video{{width:100%;border-radius:12px;background:#000}}
pre{{background:#14202a;color:#e9e2d6;padding:20px;border-radius:12px;overflow:auto;font-size:13px}}
footer{{margin-top:64px;color:var(--muted);font-size:13px;border-top:1px solid var(--line);padding-top:20px}}
@media(max-width:640px){{.wrap{{padding:32px 16px 64px}}}}
</style></head><body><div class="wrap">
<header><div class="eyebrow">Research paper</div><h1>{title}</h1>
<div class="authors">{authors}</div><div class="venue">{venue}</div>
<div class="links">{''.join(links)}</div></header>
<section><h2>Abstract</h2><p>{abstract}</p></section>
<section><h2>Key results</h2><ul class="claims">{claims_html}</ul></section>
{video_html}
<section><h2>Figures</h2>{figures_html}</section>
<section><h2>Cite</h2><pre>{bib}</pre></section>
<footer>Generated locally with PaperRelay. Facts are drawn from the paper and verified metadata; check the paper before citing.</footer>
</div></body></html>"""
    index = outdir / "index.html"
    index.write_text(page, encoding="utf-8")
    return index
