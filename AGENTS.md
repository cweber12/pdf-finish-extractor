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

## Documentation Rules

- Maintain an architecture document for the project.
- Update the architecture document whenever module boundaries, data flow, dependencies, or extraction strategy changes.
- Document any non-obvious extraction assumptions, such as coordinate pairing rules or OCR fallback behavior.

## Commit Message Rule

- Provide a commit message that explains the change, how it was implemented, and why it was needed.
- Do not use literal section labels like `what`, `how`, or `why`; write it as a clean conventional commit-style message.

## Handoff Checklist

Before handoff, summarize:

- Files changed.
- Tests added or updated.
- Checks run and results.
- Any known limitations or follow-up work.