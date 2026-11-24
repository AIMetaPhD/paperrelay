from __future__ import annotations

import asyncio
import base64
import html
import json
import os
import re
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any

import edge_tts
from PIL import Image, ImageDraw, ImageFont

from .config import find_ffmpeg, find_ffprobe
from .facts import code_confirmed, meaningful_claims, venue_confirmed

W, H = 1920, 1080
SUB_Y = 946
LIGATURES = {"ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl", "ﬅ": "ft", "ﬆ": "st"}


def norm(text: str) -> str:
    for source, target in LIGATURES.items():
        text = text.replace(source, target)
    text = re.sub(r"\bour\b", "the", text, flags=re.I)
    text = re.sub(r"\bwe\b", "the authors", text, flags=re.I)
    return text


def _clip(text: str, limit: int) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(" ,.;:，。；")
    return cut + "…"


def _zh_sentences(text: str, limit: int = 4) -> list[str]:
    text = norm(text or "")
    parts = re.split(r"(?<=[。！？；])", re.sub(r"\s+", " ", text).strip())
    out = [p.strip() for p in parts if 8 <= len(p.strip()) <= 320]
    return out or ([text.strip()] if text.strip() else [])[:limit]


def _sentences(text: str, limit: int = 4, lang: str = "en") -> list[str]:
    if lang == "zh":
        return _zh_sentences(text, limit)[:limit]
    text = norm(text or "")
    parts = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text).strip())
    out = [p.strip() for p in parts if 20 <= len(p.strip()) <= 320]
    return out[:limit]


def _scene_plan_zh(version: dict[str, Any], claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    title = version.get("title") or "研究论文"
    author_list = [a for a in (version.get("authors") or []) if a]
    authors = "、".join(author_list) or "作者信息待确认"
    authors_short = (author_list[0] + " 等") if len(author_list) > 3 else authors
    venue_ok = venue_confirmed(version)
    venue = (version.get("venue") or "").strip() if venue_ok else ""
    paper_url = version.get("paper_url") or ""
    code_url = (version.get("code_url") or "") if code_confirmed(version) else ""
    claims = meaningful_claims(claims)
    claim_values = "；".join(c["value"] for c in claims[:3]) or "论文未抽取到可核对的数值结果"
    figures = version.get("figures") or []

    opening = f"本视频介绍论文《{title}》，作者为{authors_short}。"
    opening += f"论文发表于{venue}。" if venue_ok else "论文的发表信息尚未确认。"
    return [
        {
            "kicker": "研究问题",
            "title": title,
            "venue": venue,
            "bullets": [authors_short] + ([venue] if venue_ok else []) + ["论文摘要介绍研究问题与方法，具体表述请参见原文。"],
            "narration": opening + "下面概述论文的研究问题与主要结果。",
            "figure": "",
        },
        {
            "kicker": "方法概述",
            "title": "论文研究什么",
            "bullets": ["研究问题与方法以论文原文为准。", "本视频不替作者补充未公开的信息。"],
            "narration": "论文摘要介绍了研究问题与方法。为避免改写原文事实，具体方法请以论文原文为准。",
            "figure": figures[0]["path"] if figures else "",
        },
        {
            "kicker": "关键结果",
            "title": "论文报告的结果",
            "bullets": [f"{c['value']}（第 {c['source_page']} 页）" for c in claims[:3]] or ["论文未抽取到可核对的数值结果。"],
            "narration": f"论文报告的关键结果包括：{claim_values}。这些数值来自论文原文抽取，引用前请核对上下文。",
            "figure": figures[1]["path"] if len(figures) > 1 else (figures[0]["path"] if figures else ""),
        },
        {
            "kicker": "条件与限制",
            "title": "结果依赖的条件",
            "bullets": ["结果依赖论文的实验设置。", "引用时请保留原文的条件与限制。"],
            "narration": "这些结果依赖论文设定的实验条件与限制。引用或传播时，请保留原文的上下文。",
            "figure": figures[2]["path"] if len(figures) > 2 else "",
        },
        {
            "kicker": "阅读原文",
            "title": "论文与代码",
            "bullets": [paper_url or "论文链接见论文记录"] + ([code_url] if code_url else []),
            "narration": (f"论文链接：{paper_url}。" if paper_url else "")
            + (f"代码链接：{code_url}。" if code_url else "")
            + "感谢观看。",
            "figure": "",
        },
    ]


def scene_plan(version: dict[str, Any], claims: list[dict[str, Any]], lang: str = "en") -> list[dict[str, Any]]:
    if lang == "zh":
        return _scene_plan_zh(version, claims)
    title = norm(version.get("title") or "Research paper")
    author_list = [norm(a) for a in (version.get("authors") or []) if a]
    authors = ", ".join(author_list) or "The authors"
    authors_short = (author_list[0] + " et al.") if len(author_list) > 3 else (authors or "The authors")
    venue_ok = venue_confirmed(version)
    venue = norm(version.get("venue") or "") if venue_ok else ""
    abstract = version.get("abstract") or ""
    sentences = _sentences(abstract, 6)
    figures = version.get("figures") or []
    paper_url = version.get("paper_url") or ""
    code_url = (version.get("code_url") or "") if code_confirmed(version) else ""
    claims = meaningful_claims(claims)
    claim_a = claims[0] if claims else None
    claim_b = claims[1] if len(claims) > 1 else None

    def claim_text(claim: dict[str, Any] | None) -> str:
        if not claim:
            return "The paper presents a new method and analysis."
        return f"Key result: {norm(claim['value'])}"

    opening = f"This is {title}, by {authors_short}."
    if venue_ok:
        opening += f" Published at {venue}."
    scenes = [
        {
            "kicker": "THE PROBLEM",
            "title": title,
            "venue": venue,
            "bullets": [f"{authors_short}"] + ([f"{venue}"] if venue_ok else []) +
                       [(_clip(sentences[0], 120) if sentences else "An important open problem.")],
            "narration": (
                opening + " "
                + (sentences[0] if sentences else "The paper studies an important open problem.")
            ),
            "figure": "",
        },
        {
            "kicker": "THE METHOD",
            "title": "What the paper does",
            "bullets": [s[:110] for s in sentences[1:3]] or ["A new method for the problem."],
            "narration": " ".join(sentences[1:3]) or "The paper introduces a new method and explains how it works.",
            "figure": figures[0]["path"] if figures else "",
        },
        {
            "kicker": "KEY RESULT",
            "title": claim_text(claim_a),
            "bullets": [_clip(norm(claim_a["source_quote"]), 180)] if claim_a else ["See the paper for the reported results."],
            "narration": (
                f"The headline result is {norm(claim_a['value'])}. "
                + norm(claim_a["source_quote"])
            ) if claim_a else "The paper reports its main results in the evaluation section.",
            "figure": figures[1]["path"] if len(figures) > 1 else (figures[0]["path"] if figures else ""),
        },
        {
            "kicker": "CONDITIONS",
            "title": "What the result depends on",
            "bullets": [
                (norm(claim_b["source_quote"])[:180] if claim_b else "The reported result depends on the paper's experimental setting."),
                "Keep the paper's conditions and limitations.",
            ],
            "narration": (
                f"The result comes with conditions. {norm(claim_b['source_quote'])}" if claim_b
                else "The reported result depends on the paper's experimental setting and should be read with its stated conditions."
            ),
            "figure": figures[2]["path"] if len(figures) > 2 else "",
        },
        {
            "kicker": "READ THE PAPER",
            "title": "Paper and code",
            "bullets": [paper_url or "Paper link in the paper record", code_url or "Code link when available"],
            "narration": (
                f"You can read the paper at {paper_url}. " if paper_url else ""
            ) + (f"The code is available at {code_url}." if code_url else "") + " Thanks for watching.",
            "figure": "",
        },
    ]
    return scenes


def _slide_html(scene: dict[str, Any], index: int, total: int) -> str:
    kicker = html.escape(scene["kicker"])
    title = html.escape(scene["title"])
    bullets = "".join(f"<li>{html.escape(str(b))}</li>" for b in scene["bullets"] if b)
    figure_html = ""
    if scene.get("figure"):
        try:
            data = base64.b64encode(Path(scene["figure"]).read_bytes()).decode("ascii")
            figure_html = f'<div class="figure"><img src="data:image/png;base64,{data}" alt=""></div>'
        except Exception:
            figure_html = ""
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    html,body{{width:{W}px;height:{H}px;overflow:hidden;background:#0c141b;color:#f4efe6;
      font-family:'Segoe UI','Microsoft YaHei',sans-serif}}
    .stage{{width:{W}px;height:{H}px;padding:96px 110px;display:flex;flex-direction:column;
      background:radial-gradient(1200px 700px at 80% 0%, #193242 0%, #0c141b 60%)}}
    .top{{display:flex;justify-content:space-between;align-items:center;color:#e0a458;
      font-size:24px;letter-spacing:.22em;text-transform:uppercase}}
    .index{{color:#7f93a3;letter-spacing:.1em}}
    h1{{font-family:Georgia,'Times New Roman',serif;font-size:{76 if len(title) < 60 else 60}px;
      line-height:1.08;margin-top:54px;max-width:1500px}}
    .body{{display:flex;gap:56px;flex:1;align-items:center;margin-top:40px}}
    ul{{list-style:none;display:flex;flex-direction:column;gap:26px;max-width:820px}}
    li{{font-size:34px;line-height:1.35;color:#d9e2e8;padding-left:34px;position:relative}}
    li:before{{content:'';position:absolute;left:0;top:14px;width:14px;height:14px;
      background:#e0a458;border-radius:2px}}
    .figure{{flex:1;display:flex;align-items:center;justify-content:center}}
    .figure img{{max-width:760px;max-height:560px;object-fit:contain;background:#fff;
      padding:18px;border-radius:6px;box-shadow:0 24px 60px rgba(0,0,0,.35)}}
    </style></head><body><div class="stage">
      <div class="top"><span>{kicker}</span><span class="index">{index:02d} / {total:02d}</span></div>
      <h1>{title}</h1>
      <div class="body"><ul>{bullets}</ul>{figure_html}</div>
    </div></body></html>"""


def render_slides(scenes: list[dict[str, Any]], outdir: Path, progress=None) -> list[Path]:
    from playwright.sync_api import sync_playwright

    outdir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, timeout=60000)
        page = browser.new_page(viewport={"width": W, "height": H})
        for idx, scene in enumerate(scenes, start=1):
            page.set_content(_slide_html(scene, idx, len(scenes)), wait_until="load")
            page.wait_for_timeout(200)
            path = outdir / f"slide_{idx:02d}.png"
            page.screenshot(path=str(path), clip={"x": 0, "y": 0, "width": W, "height": H}, timeout=60000)
            paths.append(path)
            if progress:
                progress(0.08 + 0.2 * idx / len(scenes), f"Rendered slide {idx}/{len(scenes)}")
        browser.close()
    return paths


async def _tts(text: str, voice: str, path: Path) -> None:
    communicate = edge_tts.Communicate(text, voice, rate="+4%")
    await communicate.save(str(path))


def synthesize(scenes: list[dict[str, Any]], voice: str, outdir: Path) -> list[Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for idx, scene in enumerate(scenes, start=1):
        path = outdir / f"voice_{idx:02d}.mp3"
        asyncio.run(_tts(scene["narration"], voice, path))
        paths.append(path)
    return paths


def ffprobe_duration(path: Path) -> float:
    cmd = [find_ffprobe(), "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)]
    data = json.loads(subprocess.check_output(cmd, text=True, encoding="utf-8"))
    return float(data["format"]["duration"])


def probe_video(path: Path) -> dict[str, Any]:
    """Read the final MP4, not the planned scene durations."""
    cmd = [find_ffprobe(), "-v", "error", "-show_entries",
           "format=duration,size:stream=index,codec_type,codec_name,width,height,r_frame_rate",
           "-of", "json", str(path)]
    data = json.loads(subprocess.check_output(cmd, text=True, encoding="utf-8"))
    streams = data.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), {})
    audio = next((s for s in streams if s.get("codec_type") == "audio"), {})
    return {
        "duration": float((data.get("format") or {}).get("duration") or 0),
        "size": int((data.get("format") or {}).get("size") or 0),
        "width": int(video.get("width") or 0),
        "height": int(video.get("height") or 0),
        "vcodec": video.get("codec_name") or "",
        "acodec": audio.get("codec_name") or "",
        "has_audio": bool(audio),
    }


def _require_tool(path: str, name: str, hint: str) -> None:
    if not path:
        raise RuntimeError(f"{name} not found. {hint}")
    if os.path.sep in path or (len(path) > 1 and path[1] == ":"):
        if not Path(path).exists():
            raise RuntimeError(f"{name} not found at {path}. {hint}")
    elif shutil.which(path) is None:
        raise RuntimeError(f"{name} not found on PATH. {hint}")


def _subtitle_images(text: str, outdir: Path, scene_index: int, duration: float,
                     lang: str = "en") -> list[tuple[Path, float, float]]:
    outdir.mkdir(parents=True, exist_ok=True)
    sentences = _sentences(text, 8, lang=lang) or [text]
    total_chars = sum(len(s) for s in sentences) or 1
    try:
        font = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 34)
    except Exception:
        font = ImageFont.load_default()
    items: list[tuple[Path, float, float]] = []
    cursor = 0.0
    for idx, sentence in enumerate(sentences):
        share = duration * (len(sentence) / total_chars)
        start = cursor
        end = min(duration, cursor + share)
        cursor = end
        image = Image.new("RGBA", (W, 108), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, W, 108), fill=(8, 14, 20, 168))
        # Wrap by words for English and by characters for Chinese/CJK.
        words = sentence.split()
        lines, current = [], ""
        if len(words) <= 1:
            for char in sentence:
                trial = current + char
                if draw.textlength(trial, font=font) > W - 160 and current:
                    lines.append(current)
                    current = char
                else:
                    current = trial
            if current:
                lines.append(current)
        else:
            for word in words:
                trial = (current + " " + word).strip()
                if draw.textlength(trial, font=font) > W - 160 and current:
                    lines.append(current)
                    current = word
                else:
                    current = trial
            if current:
                lines.append(current)
        lines = lines[:2]
        y = 10 if len(lines) == 1 else 2
        for line in lines:
            width = draw.textlength(line, font=font)
            draw.text(((W - width) / 2, y), line, font=font, fill=(255, 255, 255, 255),
                      stroke_width=2, stroke_fill=(0, 0, 0, 220))
            y += 50
        path = outdir / f"sub_{scene_index:02d}_{idx:02d}.png"
        image.save(path)
        items.append((path, start, max(start + 0.6, end)))
    return items


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "ffmpeg failed")[-1800:])


def _scene_clip(slide: Path, audio: Path, subs: list[tuple[Path, float, float]], duration: float,
                out: Path, ffmpeg: str, zoom_in: bool) -> None:
    cmd = [ffmpeg, "-y", "-loop", "1", "-framerate", "30", "-t", f"{duration:.3f}", "-i", str(slide),
           "-i", str(audio)]
    for path, _, _ in subs:
        cmd += ["-i", str(path)]
    zoom = "min(zoom+0.00035,1.07)" if zoom_in else "if(eq(on,0),1.07,max(zoom-0.00035,1.0))"
    filters = [
        f"[0:v]scale={W}:{H},zoompan=z='{zoom}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps=30,"
        f"fade=t=in:st=0:d=0.35,fade=t=out:st={max(0, duration-0.35):.3f}:d=0.35[bg]"
    ]
    last = "bg"
    for idx, (_, start, end) in enumerate(subs):
        label = f"v{idx + 1}"
        filters.append(f"[{last}][{idx + 2}:v]overlay=0:{SUB_Y}:enable='between(t,{start:.3f},{end:.3f})'[{label}]")
        last = label
    filters.append(f"[{last}]format=yuv420p[v]")
    cmd += ["-filter_complex", ";".join(filters), "-map", "[v]", "-map", "1:a",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "192k",
            "-t", f"{duration:.3f}", "-movflags", "+faststart", str(out)]
    _run(cmd)


def _write_srt(scenes: list[dict[str, Any]], durations: list[float], out: Path,
               lang: str = "en") -> None:
    lines: list[str] = []
    cursor = 0.0
    counter = 1
    for scene, duration in zip(scenes, durations):
        sentences = _sentences(scene["narration"], 8, lang=lang) or [scene["narration"]]
        total = sum(len(s) for s in sentences) or 1
        local = 0.0
        for sentence in sentences:
            share = duration * len(sentence) / total
            start, end = cursor + local, cursor + local + share
            local += share
            def ts(seconds: float) -> str:
                ms = int(round(seconds * 1000))
                h, ms = divmod(ms, 3600000)
                m, ms = divmod(ms, 60000)
                s, ms = divmod(ms, 1000)
                return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
            lines += [str(counter), f"{ts(start)} --> {ts(end)}", sentence, ""]
            counter += 1
        cursor += duration
    out.write_text("\n".join(lines), encoding="utf-8")


def voice_for(settings: dict[str, str], lang: str) -> str:
    if lang == "zh":
        return settings.get("voice_zh") or "zh-CN-XiaoxiaoNeural"
    return settings.get("voice_en") or "en-US-AriaNeural"


def generate_video(version: dict[str, Any], claims: list[dict[str, Any]], settings: dict[str, str],
                   outdir: Path, progress=None) -> dict[str, Any]:
    ffmpeg = find_ffmpeg()
    ffprobe = find_ffprobe()
    _require_tool(ffmpeg, "ffmpeg", "Install FFmpeg and add it to PATH, or set FFMPEG_BIN.")
    _require_tool(ffprobe, "ffprobe", "Install FFmpeg (includes ffprobe) and add it to PATH, or set FFPROBE_BIN.")
    lang = "zh" if settings.get("video_language", "en") == "zh" else "en"
    voice = voice_for(settings, lang)
    scenes = scene_plan(version, claims, lang=lang)
    work = outdir / "video_work"
    work.mkdir(parents=True, exist_ok=True)
    build = work / f"build_{uuid.uuid4().hex[:8]}"
    build.mkdir(parents=True, exist_ok=True)
    if progress:
        progress(0.08, "Rendering slides")
    try:
        slides = render_slides(scenes, build / "slides", progress)
    except Exception as exc:
        raise RuntimeError(
            "Slide rendering failed. Playwright Chromium must be installed: "
            "`python -m playwright install chromium`. " + str(exc)[:300]
        )
    if progress:
        progress(0.3, "Synthesizing narration")
    try:
        voices = synthesize(scenes, voice, build / "voice")
    except Exception as exc:
        raise RuntimeError("Narration synthesis failed (Edge TTS needs network). " + str(exc)[:300])
    durations = [ffprobe_duration(p) for p in voices]
    total = sum(durations)
    if total < 60:
        durations = [d + max(2.0, (60 - total) / len(durations)) for d in durations]
        total = sum(durations)
    clips: list[Path] = []
    if progress:
        progress(0.45, "Composing scenes")
    for idx, (scene, slide, audio, duration) in enumerate(zip(scenes, slides, voices, durations), start=1):
        subs = _subtitle_images(scene["narration"], build / "subs", idx, duration, lang=lang)
        clip = build / f"clip_{idx:02d}.mp4"
        _scene_clip(slide, audio, subs, duration, clip, ffmpeg, zoom_in=(idx % 2 == 1))
        clips.append(clip)
        if progress:
            progress(0.45 + 0.35 * idx / len(scenes), f"Composed scene {idx}/{len(scenes)}")
    list_file = build / "concat.txt"
    list_file.write_text("\n".join(f"file '{c.resolve().as_posix()}'" for c in clips), encoding="utf-8")
    assembled = build / "assembled.mp4"
    _run([ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy",
          "-movflags", "+faststart", str(assembled)])
    probed = probe_video(assembled)
    final = assembled
    speed_factor = 1.0
    if probed["duration"] > 120:
        # Keep the published video inside the 60-120s promise without cutting narration.
        speed_factor = probed["duration"] / 115.0
        tempo = min(2.0, speed_factor)
        fast = build / "video_fast.mp4"
        if progress:
            progress(0.86, f"Speeding up {probed['duration']:.0f}s video by {speed_factor:.2f}x")
        _run([ffmpeg, "-y", "-i", str(assembled), "-filter_complex",
              f"[0:v]setpts=PTS/{speed_factor:.6f}[v];[0:a]atempo={tempo:.6f}[a]",
              "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
              "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(fast)])
        final = fast
        probed = probe_video(final)
        durations = [d / speed_factor for d in durations]
    srt_path = build / "video.srt"
    _write_srt(scenes, durations, srt_path, lang=lang)
    vtt_path = build / "video.vtt"
    srt_text = srt_path.read_text(encoding="utf-8")
    vtt_text = "WEBVTT\n\n" + re.sub(r"(\d{2}:\d{2}:\d{2}),(\d{3})", r"\1.\2", srt_text)
    vtt_path.write_text(vtt_text, encoding="utf-8")
    # Publish only after a complete, probed MP4 exists; the old files stay until now.
    video_path = outdir / "video.mp4"
    os.replace(final, video_path)
    os.replace(srt_path, outdir / "video.srt")
    os.replace(vtt_path, outdir / "video.vtt")
    return {
        "video": str(video_path),
        "srt": str(outdir / "video.srt"),
        "vtt": str(outdir / "video.vtt"),
        "duration": probed["duration"],
        "probe": probed,
        "speed_factor": speed_factor,
        "scenes": scenes,
        "voice": voice,
    }
