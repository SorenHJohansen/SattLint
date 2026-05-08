# CLI Documentation Parity

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This plan closes the documentation gap for SattLint command entry points. When it is complete, contributor-facing docs will describe the real CLI scripts and primary subcommands consistently, and the tracker items A-003 and B-W11 can move from open to done.

## Progress

- [x] Audit command entry points and current documentation surfaces.
- [x] Document `sattlint`, `sattlint-repo-audit`, `sattlint-corpus-runner`, and `sattlint-lsp` in the canonical contributor docs.
- [x] Update the tracker and related references when parity is complete.

## Surprises & Discoveries

- Observation: CLI documentation debt appears in both Program A and Program B because it affects contributor onboarding and active work execution.
  Evidence: `docs/exec-plans/tech-debt-tracker.md` tracks the same gap as A-003 and B-W11.

## Decision Log

- Decision: Keep CLI docs parity as its own active plan instead of burying it inside the tracker.
  Rationale: The work spans multiple docs files and should have an executable plan with validation, not just a debt row.
  Date/Author: 2026-04-29 / Copilot (GPT-5.4)

- Decision: Move this plan from `active/` to `completed/` after all progress items and validations were done.
  Rationale: Finished plans should be archived as historical records and removed from the active queue to prevent stale routing.
  Date/Author: 2026-04-29 / Copilot (GPT-5.3-Codex)

## Outcomes & Retrospective

CLI docs parity is now closed for the tracked command-entry gap. The canonical command reference now lives in `docs/references/cli-commands.md`, `README.md` points readers to practical command usage, and tracker rows A-003 and B-W11 are marked done.

Validation note: the focused repo-audit command-gap slice passed (`2 passed`), and doc-gardener was rerun after fixing malformed source-ledger table formatting in `docs/exec-plans/tech-debt-tracker.md`.

## Context and Orientation

The likely files are `README.md`, `docs/context-loading-order.md`, `docs/design-docs/index.md`, command-specific docs under `docs/`, and any code-adjacent docs that mention the supported script entry points. Repo-audit already has command-gap logic, so the nearest tests are in `tests/test_repo_audit.py`.

## Plan of Work

Start by comparing documented commands against the installed console scripts and main subcommands. Update the smallest set of contributor-facing docs needed to make the documented entry points accurate and discoverable. After the docs are aligned, update A-003 and B-W11 in the tracker and keep the active plan as the execution record.

## Concrete Steps

Run from repository root:

    rg -n "sattlint|sattlint-repo-audit|sattlint-corpus-runner|sattlint-lsp" README.md docs src/sattlint tests/test_repo_audit.py
    python scripts/run_repo_python.py -m pytest --no-cov tests/test_repo_audit.py -x -q --tb=short -k "documented_command or command_gaps"
    python scripts/run_repo_python.py -m sattlint.devtools.doc_gardener

## Validation and Acceptance

Acceptance means the documented command set matches the installed command surfaces, the focused repo-audit tests pass, and doc-gardener reports no broken documentation structure after the updates.

## Idempotence and Recovery

This work is documentation-first. Re-run the same focused test slice after each doc pass. If a doc change broadens scope unexpectedly, cut it back to the smallest set of command-entry docs and rerun validation.

## Artifacts and Notes

Canonical docs touched:

- `docs/references/cli-commands.md`
- `README.md`
- `docs/exec-plans/tech-debt-tracker.md`
- `docs/exec-plans/completed/03-cli-doc-parity.md`

Command-gap findings cleared:

- `sattlint`
- `sattlint-repo-audit`
- `sattlint-corpus-runner`
- `sattlint-lsp`

## Interfaces and Dependencies

This plan depends on the installed console scripts declared in the repo remaining stable while the docs catch up.
