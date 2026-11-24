# PaperRelay v0.1.1

Follow-up release focused on first-run reliability, metadata resolution, and
open-source maintenance.

## Added

- **Pre-flight self-check** in Settings: Python, FFmpeg/FFprobe, Playwright
  Chromium and Edge TTS network status.
- **Candidate metadata resolver** for arXiv IDs and OpenReview URLs. It returns
  title/authors/abstract plus any OpenReview decision, rating and BibTeX found
  in the note; candidates are filled into the paper card but never confirmed or
  saved automatically.
- **Markdown copy** per platform and **share long image** exported from the
  generated project page.
- **PDF engine plugin**: optional `pypdf` text/link extraction alongside the
  default PyMuPDF path. `pypdf` does not extract figures.
- **Model presets** for Ollama, Magpie, OpenAI-compatible, vLLM and DeepSeek.
- **CI**: `.github/workflows/ci.yml` runs the regression suite on push/PR.
- **Manual Pages workflow** (`.github/workflows/pages.yml`) with environment
  approval.
- Community templates: `CONTRIBUTING.md`, issue templates and PR template.

## Verification

`python test_verify.py` — 20 tests, 0 failures. The suite includes restart
recovery, Chinese narration/subtitles, publish gates, fact gates and the new
extension helpers.

## Boundaries

- OpenReview results remain candidates; the user confirms venue and source.
- `pypdf` mode has no figure extraction; use PyMuPDF when figures matter.
- GitHub Pages stays a manual, approved workflow.
- PyMuPDF AGPL/commercial and edge-tts LGPL-3.0 obligations remain as documented.
