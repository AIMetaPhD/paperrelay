# Contributing

PaperRelay is a local-first research communication tool. Contributions are welcome
for parsing adapters, metadata sources, UI polish, and documentation.

## Development

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe test_verify.py
```

Keep changes small and testable. Do not add a new runtime just for a small UI feature.

## What to include in a PR

- A short description of the user-visible change.
- Reproduction steps or a test that fails before the change.
- For paper extraction changes, a sanitized sample and the expected page/quote evidence.
- No real credentials, private PDFs, or machine-specific absolute paths.

## Safety and facts

- Do not make the app claim a venue, author, code repository, or numeric result without a recorded source.
- Keep manual edits when regenerating; candidates must be reviewable before adoption.
- External publishing remains explicitly approved and verified; never bypass the approval gate.
