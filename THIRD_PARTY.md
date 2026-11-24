# Third-party dependencies and references

PaperRelay's own code is MIT. This file records the third-party software and
design references used while building it, and what a redistributed build must
review.

Verified against the installed packages on 2026-11-20 (`importlib.metadata`).

## Runtime dependencies

| Component | Installed | License | Use |
|---|---|---|---|
| FastAPI / Uvicorn | 0.164.0 | MIT | local HTTP API |
| PyMuPDF | 2.1 | **AGPL-3.0 or Artifex commercial** | PDF text/figure extraction |
| Pillow | 13.0.0 | HPND (MIT-CMU) | subtitle images |
| edge-tts | 7.3.1 | **LGPL-3.0** | narration synthesis (optional) |
| Playwright | 1.65.2 | Apache-2.0 | slide screenshots |
| FFmpeg | system | LGPL/GPL depending on build | video composition |
| Semantic Scholar API | n/a | public API terms | metadata cross-check |
| OpenReview API | n/a | public API terms | venue provenance |
| arXiv API | n/a | public API terms | metadata / source checks |

Two dependencies need action before any public redistribution:

### PyMuPDF (AGPL-3.0 / commercial)

PyMuPDF is dual licensed. If PaperRelay is distributed as a public binary or
service, AGPL-3.0 requires publishing the complete corresponding source of the
combined work under AGPL-compatible terms. Options, in order of effort:

1. **Keep it local-only.** Do not distribute builds; the AGPL obligations are
   triggered by distribution, not by private use. This is the current state:
   the repository is private and the app runs on the user's machine.
2. **Buy the Artifex commercial license** before shipping a closed product.
3. **Replace it.** `pypdf` (BSD-3) or `pdfplumber` (MIT, built on pdfminer.six)
   cover text and simple figure regions; they need re-validation of the
   extraction quality that PyMuPDF currently provides.

### edge-tts (LGPL-3.0)

LGPL-3.0 allows use in a larger work if the library stays replaceable and its
license and source are made available. Practical steps for a distribution:

- keep `edge-tts` as an unmodified, separately installed dependency;
- ship its license text and a pointer to its source;
- do not statically bundle it into a single-file executable without providing
  the relink mechanism.

The earlier handoff note said "GPL-3.0"; the installed package metadata says
**LGPL-3.0**, which is the value to use.

## Design references (not copied)

- Microsoft ResearchStudio / ResearchStudio-Reel (MIT): the pipeline idea of a
  shared paper-assets bundle feeding poster, blog and video. **Not reused
  directly** because it is a notebook-centric pipeline with no local state,
  no fact gate, and no persistence model; borrowing it would have meant
  re-architecting around its assumptions rather than reusing code. No source
  was copied.
- ai-nuts/pptx2video (MIT): reference for deck-to-video composition. It builds
  a Remotion project and needs a Node toolchain; PaperRelay already renders
  slides with Playwright and composes with FFmpeg, so there was no
  component small enough to reuse without adding a second runtime. No source
  copied.
- AutoPR / PromoAgent: evaluated during G0; their observed fact-hallucination
  failure modes informed the deterministic fact gate. No source copied.
- Paper2All: **not reused**; the inspected revision had no root LICENSE.

Reuse rule applied: reuse when a component can be dropped in without adding a
new runtime, a new build step, or an incompatible license. None of the three
candidates met that bar; their design lessons are recorded above.

## Sample paper

The local test samples (LoRA arXiv:2106.09685, Attention arXiv:1706.03762,
BERT arXiv:1810.04805) are used only for local evaluation. Public
redistribution of their PDFs or figures requires checking the arXiv
distribution terms.
