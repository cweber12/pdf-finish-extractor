## Problem Statement

As the maintainer shipping PDF Finish Extractor to production use, I need the architecture to be easier to reason about, test, and evolve without regressions. Core behavior works, but several high-coupling modules are still too dense (especially GridEditor, theme styling, and PDF viewer logic), making changes expensive and risky.

The current state creates friction in three places:
- Large orchestrator modules hide decision logic inside widget code, slowing down refactors and debugging.
- UI concerns and domain decisions are not consistently expressed as deep, testable modules.
- Build/test confidence depends too heavily on full UI integration paths instead of small, deterministic seam tests.

## Solution

Complete a final architecture deepening pass that keeps user-visible behavior unchanged while extracting remaining high-coupling logic into stable, pure decision modules and narrow adapters.

The pass will:
- Finish decomposing GridEditor by moving remaining orchestration-heavy decisions into dedicated seams.
- Decompose theme and PDF viewer responsibilities into clearer module boundaries.
- Preserve existing extraction semantics (Grid, Group, Field recipe, OmitRegion, sparse groups, segment behavior) while improving testability and maintenance speed.
- Expand targeted unit test coverage around newly extracted seams and maintain architecture documentation alignment.

## User Stories

1. As a maintainer, I want GridEditor behavior split into small decision modules, so that I can modify one interaction path without re-reading the entire editor.
2. As a maintainer, I want page navigation and omission behavior expressed as pure functions, so that I can verify edge cases without spinning up full Qt widgets.
3. As a maintainer, I want Grid lifecycle transforms to be explicit and reusable, so that profile load/save/clear behavior stays consistent.
4. As a maintainer, I want MainWindow preflight and status logic separated from event wiring, so that extraction flow changes are low-risk.
5. As a maintainer, I want profile persistence isolated behind a repository seam, so that storage behavior can evolve independently from UI behavior.
6. As a maintainer, I want theme concerns decomposed into token and style seams, so that visual updates do not require editing one giant stylesheet blob.
7. As a maintainer, I want PDFViewer rendering and viewport state responsibilities separated, so that zoom and pan changes do not accidentally break coordinate conversions.
8. As a maintainer, I want extraction progress and completion messaging rules to be testable, so that user feedback stays consistent across refactors.
9. As a maintainer, I want Grid normalization and serialization responsibilities to remain deterministic, so that Profiles stay portable and reliable.
10. As a maintainer, I want architecture docs to reflect current seams, so that future contributors can navigate the codebase quickly.
11. As a maintainer, I want every seam extraction to preserve behavior, so that users do not experience regressions while internal architecture improves.
12. As a maintainer, I want focused unit tests around decision modules, so that regressions are caught before full integration testing.
13. As a maintainer, I want QThread extraction lifecycle behavior to remain stable during refactors, so that the UI stays responsive under large PDFs.
14. As a maintainer, I want segment navigation logic to remain correct after modularization, so that per-page Grid edits still apply forward as designed.
15. As a maintainer, I want OmitRegion and omitted page behavior to remain unchanged, so that mixed-format catalogs still extract correctly.
16. As a maintainer, I want field recipe structural edits to preserve current guardrails, so that Groups are not silently misinterpreted.
17. As a maintainer, I want test modules to mirror architectural seams, so that test failures immediately point to the correct layer.
18. As a maintainer, I want narrow interfaces for orchestration modules, so that future feature work can compose existing seams rather than duplicating logic.
19. As a maintainer, I want dormant upload code to remain decoupled from active extraction paths, so that future reintegration is intentional and isolated.
20. As a maintainer, I want this pass to end with a clear “remaining hotspots” checklist, so that follow-on work can continue incrementally.

## Implementation Decisions

- Continue the deep-module strategy already started in this branch: keep orchestrators thin and move policy/decision code into focused helper modules.
- Preserve the existing dependency rule: UI orchestrates extraction/export/profiles/common, while pure decision modules remain UI-framework-light whenever possible.
- Treat GridEditor as the primary remaining hotspot and complete extraction of remaining behavior clusters in small slices, each with a discrete seam boundary.
- Complete the MainWindow decomposition by leaving it as an orchestration shell with minimal branching and no duplicated message-policy logic.
- Decompose theme architecture into stable style tokens, composition helpers, and asset/icon access seams, preserving ADR 0001 visual direction.
- Decompose PDFViewer architecture into rendering scheduling, viewport state, and coordinate conversion seams, preserving ADR 0002 re-render strategy and fidelity guarantees.
- Keep Profile as the source of truth for saved Grid state and ensure lifecycle transforms remain deterministic around lines, groups, omitted pages, and OmitRegions.
- Preserve existing extraction contracts (Field recipe ordering, sparse Group handling, segment-forward application semantics) as non-negotiable behavior invariants.
- Prefer additive seams over large rewrites: each slice should preserve user-visible behavior and ship independently.
- Require architecture documentation updates whenever a module boundary materially changes.

## Testing Decisions

- Good tests assert external behavior and decision outcomes, not widget internals or private implementation details.
- Each extracted seam should receive focused unit tests with deterministic inputs/outputs (state mapping, hint/message mapping, guard decisions, and boundary cases).
- Orchestrator modules should be covered indirectly via seam tests plus existing lifecycle tests rather than broad brittle UI end-to-end tests.
- Modules to test in this PRD scope:
  - GridEditor decision seams (including remaining lifecycle/page/interaction extractions)
  - MainWindow intent/feedback seams
  - Profile repository and profile lifecycle transforms
  - Future theme and PDFViewer seams once extracted
- Prior art to mirror:
  - Existing focused seam tests in the UI test suite (interaction, right-click, omit, modes, segments, extraction session)
  - Existing extraction/domain deterministic tests (planner, grid, field extractor, group projection)
- Keep optional dependency constraints explicit in tests (PyQt/PyMuPDF availability) while preserving coverage for pure modules in minimal environments.

## Out of Scope

- Any user-facing feature additions beyond architecture refactoring.
- Changes to extraction semantics, field recipe meaning, Group data model meaning, or Profile file format contracts.
- Re-enabling or redesigning dormant upload workflows.
- Large visual redesigns that conflict with accepted ADR 0001.
- Fundamental zoom strategy changes that conflict with accepted ADR 0002.
- Packaging/distribution pipeline changes unrelated to architecture seams.

## Further Notes

- This PRD captures an incremental deepening plan from a partially completed state where multiple seams are already merged (MainWindow intents/feedback/profile menu, profile repository, several GridEditor seams).
- Remaining work should continue as thin vertical slices, each ending with tests, architecture doc updates, and a standalone commit.
- Apply the `ready-for-agent` triage label at publication so AFK implementation agents can execute directly.
