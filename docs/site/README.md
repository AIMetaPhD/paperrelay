# Pages deployment slot

This directory is intentionally empty except for this note.

PaperRelay generates the deployable site locally under `data/projects/<id>/site/`.
To use the manual Pages workflow:

1. Copy a generated site directory to `docs/site/` (or pass another path when running the workflow).
2. Open **Actions → pages → Run workflow** and provide the directory.
3. The workflow requires the `github-pages` environment approval, then deploys through GitHub Pages.

The workflow is manual (`workflow_dispatch`) on purpose. PaperRelay never publishes
a project page without a human action and a verified target.
