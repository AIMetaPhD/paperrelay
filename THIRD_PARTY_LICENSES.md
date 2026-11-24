# Third-party licenses and compliance isolation

PaperRelay's own source is MIT (`LICENSE`). The following dependencies keep
their own licenses; the MIT license does not relicense them.

| Component | Tested version | License | How it is used |
|---|---|---|---|
| FastAPI / Uvicorn | 0.164.0 | MIT | local HTTP API |
| PyMuPDF (`pymupdf`) | 2.1 | **AGPL-3.0 or Artifex commercial** | PDF text/figure extraction (default) |
| pypdf | 6.x | BSD-3-Clause | optional text/link-only PDF extraction plugin |
| Pillow | 13.0.0 | HPND / MIT-CMU | subtitle images |
| edge-tts | 7.3.1 | **LGPL-3.0** | optional narration synthesis |
| Playwright | 1.65.2 | Apache-2.0 | slide screenshots (Chromium installed separately) |
| FFmpeg / FFprobe | system build | LGPL/GPL depending on build | video composition |
| Semantic Scholar / arXiv / OpenAlex APIs | n/a | public API terms | metadata cross-check |

## Isolation strategy

PaperRelay is distributed as a local application, not as a hosted service or a
single-file binary.

1. **PyMuPDF** is an ordinary, unmodified Python dependency installed by the
   user from `requirements.txt`. A redistributed binary that embeds it must
   comply with AGPL-3.0 (publish the corresponding source under AGPL terms) or
   hold an Artifex commercial license. For a closed-source distribution,
   replace it with `pypdf` (BSD-3) or `pdfplumber` (MIT) and re-validate
   extraction quality.
2. **edge-tts** is an optional, separately installed LGPL-3.0 dependency. It is
   not statically linked. Distributors must keep it replaceable and ship its
   license and source pointer.
3. **Playwright/Chromium** is installed by the user with
   `python -m playwright install chromium`; the browser is not bundled in this
   repository.
4. **FFmpeg** is a system tool located at runtime; it is not bundled here.
5. API calls go to public metadata services and the user's configured LLM
   endpoint. No credentials are committed.

## Release note

The repository's MIT license covers PaperRelay's own code only. Before
publishing a packaged installer or a hosted service, review the AGPL and
LGPL obligations above with the distributor's legal owner.

See `THIRD_PARTY.md` for design references and the rationale for not copying
research-demo code.
