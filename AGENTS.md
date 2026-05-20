# AGENTS.md

Guidelines for coding agents working on this Python PDF extraction project.

## Scope

This project extracts images, text, and image/text pairs from PDFs. Keep the implementation small, readable, and easy to maintain.

## Development Rules

- Add or update tests for every new feature, bug fix, or parsing behavior.
- Keep linting and formatting configured and passing before handoff.
- Run the available checks before finishing, such as tests, linting, formatting, and type checks if configured.
- Keep the architecture organized. Avoid flat folder structures, oversized files, duplicated logic, and unrelated code in the same module.
- Break large files into focused modules when responsibilities become unclear.
- Keep PDF parsing logic separate from export logic, CLI logic, image processing, and tests.
- Use clear names for files, functions, and extracted data models.
- Handle malformed PDFs, missing text, missing images, duplicate IDs, and unmatched image/text pairs gracefully.
- Prefer deterministic extraction based on coordinates and layout rules over fragile assumptions about PDF text order.
- Add small sample fixtures when testing PDF behavior. Do not commit large PDFs unless necessary.

### Asynchronous extraction

Extraction runs on a `QThread` worker (`_ExtractionWorker`) to keep the UI responsive. The worker emits progress/finished/failed signals. Test workers with `monkeypatch` to mock signal emits, or use a minimal test PDF if testing the full extraction pipeline. Do not block the main thread during PDF rendering or large batch operations.

### Two-step material upload

Upload workflow via Cloudflare Worker API:
1. **GET /api/v1/projects/{projectId}/materials** to search for material by composite ID, reuse UUID if found
2. **POST /api/v1/images** with entity_type=material and entity_id={materialUUID}

Store no R2/boto3 credentials locally. Use Firebase token refresh if token expires. Test with mock HTTP responses via `requests_mock` or a test fixture server.

## Documentation Rules

- Maintain an architecture document for the project.
- Update the architecture document whenever module boundaries, data flow, dependencies, or extraction strategy changes.
- Document any non-obvious extraction assumptions, such as coordinate pairing rules or OCR fallback behavior.

## Commit Message Rule

Use this exact structure — no deviations:

```
type(scope): short summary of what changed

- bullet describing one thing that was done
- bullet describing another thing that was done
- (add as many bullets as needed — one fact per bullet)

One or two sentences explaining why the change was needed or what problem it solves.
```

Rules:
- First line: `type(scope): what` — lowercase, no period, under 72 characters.
- Valid types: `feat`, `fix`, `refactor`, `test`, `chore`, `docs`.
- Blank line between summary, bullets, and closing sentences — always.
- Bullets describe *what was done*, not how or why (that goes in the closing sentences).
- Closing paragraph is 1–2 sentences max. No labels (`Why:`, `Reason:`, etc.).
- No quotation marks anywhere in the message.
- Do not wrap the message in a code block when presenting it to the user.

## Handoff Checklist

Before handoff, summarize:

- Files changed.
- Tests added or updated.
- Checks run and results.
- Any known limitations or follow-up work.