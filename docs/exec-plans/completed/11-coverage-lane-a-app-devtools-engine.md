# Coverage Lane A: App, Devtools, Docgen, Engine

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

Drain the highest-yield non-LSP coverage debt first. This lane owns the app, devtools, docgen, CLI, config, and engine surfaces that already have stable owner suites and still account for a large share of the remaining uncovered lines.

## Progress

- [x] (2026-04-30) Create this lane plan and lock the scope to existing owner suites.
- [x] (2026-04-30) Drain `configgen.py` through `tests/test_docgen.py`.
- [x] (2026-04-30) Drain `repo_audit.py` and `doc_gardener.py` through `tests/test_repo_audit.py`.
- [x] (2026-04-30) Drain `app_analysis.py`, `app_graphics.py`, `config.py`, `app_docs.py`, `app_cli_commands.py`, and `cli/entry.py` through the app and CLI owner suites.
- [x] (2026-04-30) Drain `engine.py` through `tests/test_engine.py`.
- [x] (2026-04-30) Run the lane-close validation set and hand the lane back to the orchestrator.

## Context and Orientation

Primary owner suites for this lane:

- `tests/test_docgen.py` -> `src/sattlint/docgenerator/configgen.py`
- `tests/test_repo_audit.py` -> `src/sattlint/devtools/repo_audit.py`, `src/sattlint/devtools/doc_gardener.py`
- `tests/test_app.py`, `tests/test_app_analysis.py`, `tests/test_app_menus.py`, `tests/test_cli.py` -> `src/sattlint/app_analysis.py`, `src/sattlint/app_graphics.py`, `src/sattlint/config.py`, `src/sattlint/app_docs.py`, `src/sattlint/app_cli_commands.py`, `src/sattlint/cli/entry.py`
- `tests/test_engine.py` -> `src/sattlint/engine.py`

Current high-miss files in this lane included `app_analysis.py` (270), `repo_audit.py` (263), `configgen.py` (258), `app_graphics.py` (198), `doc_gardener.py` (190), and `engine.py` (186) when the lane started.

## Plan of Work

Slice 1: finish `configgen.py` because the owner suite is already warm and prior work proved the seam is cheap to extend.

Slice 2: finish `repo_audit.py` and `doc_gardener.py` with direct helper and orchestration tests before touching broader app flows.

Slice 3: finish app/CLI/config surfaces using direct seam calls and monkeypatched dependencies instead of interactive flows.

Slice 4: finish `engine.py` once the surrounding app paths stop hiding easy wins.

## Concrete Steps

Run commands from repository root.

Per-slice first validations:

    & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_docgen.py -x -q --tb=short
    & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_repo_audit.py -x -q --tb=short
    & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_app.py tests/test_app_analysis.py tests/test_app_menus.py tests/test_cli.py -x -q --tb=short
    & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_engine.py -x -q --tb=short

Lane-close validation:

    & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_docgen.py tests/test_repo_audit.py tests/test_app.py tests/test_app_analysis.py tests/test_app_menus.py tests/test_cli.py tests/test_engine.py -x -q --tb=short

Suggested claim bundles when splitting this lane further:

- `coverage-lane-a-docgen-2026-04-30`
- `coverage-lane-a-repo-audit-2026-04-30`
- `coverage-lane-a-app-cli-2026-04-30`
- `coverage-lane-a-engine-2026-04-30`

## Validation and Acceptance

This lane is complete when:

- all lane owner suites pass with `--no-cov`,
- the lane's source files are no longer dominant entries in the next shared miss list,
- no app or engine bug was masked by a test-only workaround.

## Idempotence and Recovery

Keep work inside owner suites already listed here. If one source file becomes awkward, move sideways only within the same owner suite before widening the claim set.

## Surprises & Discoveries

- Observation: `configgen.py` stayed one of the fastest remaining sources of coverage because workbook helpers could be exercised entirely in memory.
  Evidence: the owner-suite expansion closed parser, mapper, dependency, and workbook orchestration branches without DOCX or Excel integration runs.
- Observation: repo-audit helper tests must avoid platform-specific newline assumptions on this Windows workspace.
  Evidence: the portable fix was asserting `splitlines()` output rather than exact `\n` content.
- Observation: malformed `coverage.xml` is a raised parse error, not a normalized finding.
  Evidence: `_parse_coverage_findings()` calls `ElementTree.fromstring()` directly, so the correct owner-suite contract is `pytest.raises(ParseError)`.
- Observation: app, CLI, and engine residue stayed cheapest through direct seam tests.
  Evidence: helper-level tests for command routing, documentation scope state, datatype analysis error handling, code-mode normalization, graphics companion lookup, and syntax-result wrapping closed the slice without widening into interactive flows.

## Decision Log

- Decision: start this lane with docgen, then repo-audit, then app/CLI, then engine.
  Rationale: that order follows both miss count and seam cheapness.
  Date/Author: 2026-04-30 / Copilot (GPT-5.4)
- Decision: keep `engine.py` in this lane even though it can feel separate from app code.
  Rationale: the validation surface and user-facing behavior overlap with the same app flows and closeout checkpoint.
  Date/Author: 2026-04-30 / Copilot (GPT-5.4)
- Decision: close the engine slice with direct helper tests rather than broader loader rewrites.
  Rationale: the remaining misses were concentrated in deterministic helper seams with a cheap owner-suite falsifier.
  Date/Author: 2026-04-30 / Copilot (GPT-5.4)

## Outcomes & Retrospective

Lane A closed on 2026-04-30 through owner-suite expansion only; no production code changes were needed in the final engine slice.

Validated outcomes:

- `tests/test_docgen.py` -> `51 passed`
- `tests/test_repo_audit.py` -> `65 passed`
- `tests/test_app.py tests/test_app_analysis.py tests/test_app_menus.py tests/test_cli.py` -> `174 passed`
- `tests/test_engine.py` -> `23 passed`
- Lane-close owner set -> `313 passed`

The lane is now handed back to the orchestrator for the next shared coverage checkpoint.

## Artifacts and Notes

- Use the orchestrator plan for shared checkpoints and final acceptance.
- Record exact claim IDs in the shared `.git/sattlint-ai-coordination/current_work_lock.json` lock state before editing code.

## Interfaces and Dependencies

Preserve existing console UX and CLI routing invariants. When touching app menu or CLI surfaces, keep the nearest existing tests updated in the same slice.
