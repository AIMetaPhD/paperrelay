# PaperRelay v0.1.0

Local-first research paper communication workspace.

## What is included

- Upload a paper PDF and extract text, figures, links and candidate numeric claims with page/quote provenance.
- Generate English and Chinese promotional copy, a narrated MP4 with burned-in subtitles and SRT/VTT, and a responsive project page.
- Chinese narration is supported (`video_language=zh`, default `zh-CN-XiaoxiaoNeural`).
- Edit and save copy, compare regenerated candidates, adopt or keep manual edits.
- Detect source changes, mark affected artifacts stale and prepare update candidates.
- Publish only after explicit approval; the app never creates public repositories automatically and only marks Pages live after HTTP verification.

## Quick start

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe run.py
```

Open http://127.0.0.1:8787/ .

Requirements: Python 3.11+, FFmpeg/FFprobe, optional OpenAI-compatible LLM (Ollama or a Responses-API gateway such as Magpie).

## Verification

- `test_verify.py`: 17 tests, 0 failures, including abrupt-restart recovery and Chinese narration/subtitles.
- Final independent QA report: `FINAL_QA_ACCEPTANCE_REPORT.md`.
- D1–D10 are PASS.

## Known boundaries

- PyMuPDF is AGPL-3.0 or commercial; edge-tts is LGPL-3.0. See `THIRD_PARTY_LICENSES.md` before redistributing a packaged build.
- OpenReview is not queried automatically; venue provenance must be confirmed by the user.
- Video generation requires network access for Edge TTS.
- Real GitHub Pages publication still requires a human-approved target repository and remote verification.

## License

PaperRelay's own code is MIT. Third-party dependencies retain their licenses.
