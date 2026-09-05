# Enforcement Gaps

> Status: Active
> Source: repository review performed 2026-09-05 on branch
> `refactor/remove-app-facade` — this plan covers the findings that **no other
> exec-plan tracks**.
> Related: `architecture-upgrade-plan.md` (Phase 23),
> `release-1.0-and-doc-alignment.md` (Parts C/D),
> `analyzer-execution-refactor.md` (R1–R4),
> `library-resolution-and-config-cleanup.md` (P1–P6),
> `tests-cleanup-and-hardening.md` (A–E).

## Goal

Close the gaps between what `docs/design-docs/core-beliefs.md` claims is
enforced and what is actually enforced, and fix the one live red gate on the
current working tree. File-size line caps are intentionally out of scope — no
cap, no line-count guard.

Verified ground truth at review time:

- Full suite: **1216 passed**; `ruff check .` clean; `pyright src/sattlint`
  0/0/0.
- **`ruff format --check .` fails** on `tests/app/test_analysis_run.py`
  (modified on this branch) — the full-local gate is currently red.
- Aggregate coverage: **83.01%** (target 100% per core-beliefs #15); no
  `fail_under` in `ci.yml` or `pyproject.toml`.
- Identifier comparison mixes `.lower()` (104 sites) and `.casefold()` (550)
  on SattLine identifiers; the claimed casefold lint rule does not exist.

## Scope — already covered elsewhere (NOT re-planned)

These are explicitly excluded because an existing plan owns them:

| Gap | Owner |
| --- | --- |
| Split `analyzers/string_inference.py` (1716) | architecture Phase 13; release Phase 19 |
| `app.py` shim + entry-point repoint | release Phase 18; library P6 |
| UI `# pyright:` suppressions | release Phase 16 |
| Command-seam overlap | release Phase 14 |
| `application/service.py` fate | release Phase 13 |
| Semantic-name overload | release Phase 15 |
| Fuzzers at package root | release Phase 17 |
| Reflection dispatch (`getattr`) | analyzer-execution R1 |
| Compatibility/facade removal | analyzer-execution R3 |
| Windows full suite | release Phase 21 |
| Scorecard badge | release Phase 22 |
| Action pins / branch drift | release Phase 20 |
| Release automation / gitignore / pycache | release Phase 23 |
| Orphaned branches | release Phase 24 |
| File-size caps / oversized-file decomposition | **Out of scope (decision)** |

## Findings (uncovered gaps)

| # | Finding | Severity | Area |
| --- | --- | --- | --- |
| G1 | `ruff format --check .` red on `tests/app/test_analysis_run.py`; release plan claims "format clean (428 files)" — drift after the review | Blocker | Working tree |
| G2 | core-beliefs #6 claims "Casefold enforcement → custom lint rule", but no such rule exists; identifier comparison mixes `.lower()` (104 sites) and `.casefold()` (550) | High | Enforcement |
| G3 | core-beliefs #15: no coverage threshold enforced; architecture Phase 23 deferred indefinitely | Medium | Coverage |
| G4 | `core-beliefs.md` Enforcement Mechanisms section (lines 35–39) lists mechanisms that do not exist — the beliefs doc itself is stale (#11) | Medium | Docs |

## Phases

### Part A — Working-tree hygiene

#### Phase 1 — Restore the full-local gate (G1)

Format the one drifted file and re-run the full-local gate.

- Run `python -m ruff format tests/app/test_analysis_run.py` (single file, no
  bulk edit), then `python -m ruff format --check .`.
- Confirm the release plan's claim ("format clean, 428 files") is true again.

Acceptance: `ruff check .`, `ruff format --check .`, `pyright src/sattlint`,
and `pytest -q --tb=short` are all green on the current branch.

### Part B — Claimed-but-missing enforcement (#0, #6)

> These close the gap between what core-beliefs assert and what is enforced.
> The repo's pattern is **enforcement by test, not grep** (see
> `tests/test_dependency_guard.py`), so the guard below is an AST pytest guard,
> not a new linter.

#### Phase 2 — Casefold consistency + guard (G2)

Migrate identifier normalization to `casefold` and make it enforced.

Scope is **SattLine identifiers only**: variable / module-type / datatype /
program names and the env/index keys built from them. The `.lower()` sites that
normalize file suffixes, CLI prompts, and mode/config strings are **not**
identifiers and stay as-is.

- Refactor the identifier `.lower()` sites to `utils/casefolding.py`
  (`casefold_key`) or `.casefold()`. Identified sites include
  `resolution/context_builder.py:257-364`, `resolution/scope.py:58,116`,
  `analyzers/variables/__init__.py:59-101`,
  `analyzers/variables/_variables_access.py:56-446`,
  `analyzers/variables/_variables_effect_flow.py:147-445`,
  `analyzers/variables/_variables_execution.py:662-836`,
  `analyzers/variables/_variables_submodules.py:107-464`,
  `analyzers/variables/_variables_picture_display_support.py:40-41`,
  `analyzers/variable_usage_reporting.py:92-343`, `analyzers/modules.py:125-133`,
  `analyzers/same_cycle.py:413`, `analyzers/_modules_fingerprints.py:87`,
  `analyzers/sattline_builtins/__init__.py:40,45`.
- Add `tests/test_casefolding_guard.py`: an AST guard (mirroring
  `test_dependency_guard.py`) that flags `.lower()` calls on identifier-carrying
  attribute receivers (`.name`, `.datatype_text`, `.moduletype_name`, builtin
  names) with a documented allowlist for the non-identifier `.lower()` uses.
- Update `docs/design-docs/core-beliefs.md:37` — "Casefold enforcement →
  custom lint rule" → "→ `tests/test_casefolding_guard.py`".

Acceptance: no `.lower()` remains on a SattLine identifier; the guard blocks
reintroduction; core-beliefs points at the real mechanism.

#### Phase 3 — Reconcile `core-beliefs.md` Enforcement Mechanisms (G4)

Verify every mechanism listed in `core-beliefs.md:33-39` exists and point each
at its real artifact.

- Architecture boundaries → `tests/test_dependency_guard.py` ✅ exists.
- Doc freshness → "reviewed during each exec-plan pass" ✅ honest.
- Casefold enforcement → now `tests/test_casefolding_guard.py` (Phase 2).
- Shared utility reuse → duplication detection: **verify** — if no mechanism
  exists, either add a lightweight guard or reword the claim.
- File size → reword the claim: no mechanical cap is intended (decision), so
  "File size → max lines per file" must not read as an enforced guard.

Acceptance: every line in the Enforcement Mechanisms section maps to a real,
findable artifact or is honestly reworded (including the file-size line).

### Part C — Coverage floor (#15)

#### Phase 4 — Enforce coverage non-regression (G3)

Reactivate the deferred architecture-upgrade Phase 23 with the light approach it
already suggests.

- Add an aggregate floor to CI: `--cov-fail-under=80` in `ci.yml` (current
  83.01%, leaving a 3-point margin). Scope `--cov=sattlint` as today.
- Optionally add a per-module floor for the vital core (`core/`, `project/`,
  `analyzers/`) at a later ratchet step.
- Record the supersession: mark architecture-upgrade Phase 23 as "superseded by
  `enforcement-gaps.md` Phase 4" and note the ratchet policy — raise the floor
  after each deliberate coverage push; never lower it.

Acceptance: CI fails if aggregate coverage drops below the floor; the floor only
ratchets up; the deferred Phase 23 status is updated.

## Dependency order

Phase 1 first (restore green). Phases 2 and 3 are sequential (2 lands the guard
+ doc reconciliation; 3 verifies the whole section). Phase 4 is independent and
can land at any time.

Suggested sequence: **1 → 2 → 3 → 4**.

## Definition of Done

- Full-local gate green on the working tree (Phase 1).
- Casefold-only normalization for SattLine identifiers, enforced by
  `tests/test_casefolding_guard.py`.
- `core-beliefs.md` Enforcement Mechanisms section points only at real,
  findable artifacts; the file-size line no longer reads as an enforced guard.
- CI enforces an aggregate coverage floor that only ratchets up; deferred
  architecture Phase 23 is marked superseded.
- Gates: `pyright src/sattlint` 0 errors, `ruff check .` clean,
  `ruff format --check .` clean, full pytest green after every phase.

## Implementation principles

- One phase at a time; keep the repository green between phases.
- Enforcement by test, not grep (repo pattern: `test_dependency_guard.py`).
- No behavior change outside the casefold normalization.
- Update docs in the same commit as the code that invalidates them (#11).
- Coverage floor only ratchets up; never lower it.
