# Enforcement Gaps

> Status: **Complete** — Phases 1–5 implemented and verified 2026-09-08 on the
> `profiling` branch.
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
- Tests are outside the pyright gate. A strict `pyright tests` run surfaces
  exactly **2 real type errors** today; 108 of the ~149 test files carry
  file-level `# pyright:` suppressions, so the pass is partial — but it still
  catches any rule not suppressed.

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
| G5 | Tests are outside the pyright gate; a strict run over `tests/` surfaces 2 real type errors (`test_reset_contamination_ratchet_helpers.py:159,162`); 108 test files carry blanket suppressions | Low | Typing |

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

### Part C — Gate hardening (#15, #27)

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

#### Phase 5 — Type-check the test suite (G5)

Bring `tests/` into the pyright gate. It is cheap insurance: the existing
file-level suppressions bound the noise, but anything not suppressed (e.g. the
two `reportArgumentType` errors) is caught on every run, and new test files
without suppressions get full strict.

- Fix the 2 errors in
  `tests/analyzers/state_integrity/test_reset_contamination_ratchet_helpers.py:159,162`
  by relocating the inline `# pyright: ignore[reportArgumentType]` from the
  closing-paren line (160/163) onto the argument line — matching the file's
  existing inline-ignore style (lines 143, 153–155, 172).
- Add `tests` to `pyproject.toml` `[tool.pyright] include`. Side effect: the
  editor-LSP "could not be resolved" cross-test imports in `tests/helpers/`
  disappear because the whole tree becomes one project.
- Extend the gate command to `python -m pyright src/sattlint tests` in
  `ci.yml` and `docs/maintainers/quality-gates.md` (full-local + CI); extend
  the pre-commit pyright hook the same way.
- Frame honestly: this is "pyright over tests with the existing per-file
  suppressions", **not** "tests are strict-clean". Keep core-beliefs #27 as a
  `src`-scoped claim; do not overclaim in docs (#11).

Acceptance: `pyright src/sattlint tests` is 0/0/0; CI, full-local, and
pre-commit run it; no doc claims tests are strictly clean.

## Dependency order

Phase 1 first (restore green). Phases 2 and 3 are sequential (2 lands the guard
+ doc reconciliation; 3 verifies the whole section). Phase 4 and Phase 5 are
independent and can land at any time.

Suggested sequence: **1 → 2 → 3 → 4 → 5**.

## Definition of Done

- Full-local gate green on the working tree (Phase 1).
- Casefold-only normalization for SattLine identifiers, enforced by
  `tests/test_casefolding_guard.py`.
- `core-beliefs.md` Enforcement Mechanisms section points only at real,
  findable artifacts; the file-size line no longer reads as an enforced guard.
- CI enforces an aggregate coverage floor that only ratchets up; deferred
  architecture Phase 23 is marked superseded.
- Pyright runs over `src` and `tests` with 0/0/0 (existing per-file
  suppressions retained; docs do not overclaim strict-clean tests).
- Gates: `pyright src/sattlint tests` 0 errors, `ruff check .` clean,
  `ruff format --check .` clean, full pytest green after every phase.

## Implementation principles

- One phase at a time; keep the repository green between phases.
- Enforcement by test, not grep (repo pattern: `test_dependency_guard.py`).
- No behavior change outside the casefold normalization.
- Update docs in the same commit as the code that invalidates them (#11).
- Coverage floor only ratchets up; never lower it.

## Completed execution notes

**Phase 1 — done.** `ruff format` drift on `alarm_integrity.py` and
`spec_compliance.py` was formatted; the three `scripts/*` import-sort errors
(`I001`) were fixed with `ruff check --fix`. `ruff check .` and
`ruff format --check .` are green.

**Phase 2 — done.** Identifier `.lower()` normalization was migrated to casefold:
- `resolution/context_builder.py` env keys, `resolution/scope.py` lookups.
- `analyzers/variables/__init__.py` index keys (`any_var_index`, `typedef_index`,
  `root_env`), `_variables_access.py`, `_variables_effect_flow.py`,
  `_variables_execution.py` (env/param-index keys), `_variables_submodules.py`,
  `_variables_picture_display_support.py`.
- `variable_usage_reporting.py` (index + field-path normalization),
  `analyzers/modules.py`, `same_cycle.py`, `_modules_fingerprints.py`,
  `sattline_builtins/__init__.py`, `shared/_validators.py`, `project/loader.py`.
- New `tests/test_casefolding_guard.py` AST guard flags any reintroduced
  `.lower()` on identifier-carrying attribute receivers or unknown bare names,
  with a documented allowlist for the remaining non-identifier `.lower()` uses
  (file suffixes, mode/config strings, CLI prompts).
- `core-beliefs.md` enforcement line now points at the guard.
- Test drift updated in `test_execution_and_issue_collection.py`
  (`used_params_by_typedef` key is now consistently casefolded).

**Phase 3 — done.** `core-beliefs.md` Enforcement Mechanisms reconciled: the
casefold line points at `tests/test_casefolding_guard.py`; the file-size line
no longer reads as an enforced cap (reviewed, no mechanical cap); the shared
utility-reuse line is reworded honestly (no duplication detector exists —
caught in review).

**Phase 4 — done.** `ci.yml` pytest now runs with `--cov-fail-under=80`
(current aggregate 83.07%, 3-point margin). `architecture-upgrade-plan.md`
Phase 23 is marked **superseded by enforcement-gaps Phase 4** with the ratchet
policy noted. `quality-gates.md` documents the floor.

**Phase 5 — done.** `tests/` added to `[tool.pyright] include`; the two
`reportArgumentType` errors in
`test_reset_contamination_ratchet_helpers.py` were fixed by moving the inline
`# pyright: ignore` onto the argument line; five `reportUnusedFunction`
false positives on decorator-registered test functions in
`test_analyzer_architecture.py` were silenced via the file's existing
per-file suppression header. `ci.yml`, `pre-commit-config.yaml`, and
`quality-gates.md` now run `pyright src/sattlint tests`.

**Final gate (2026-09-08):** `pyright src/sattlint tests` 0/0/0, `ruff check .`
clean, `ruff format --check .` clean (443 files), `pytest -q --tb=short
--cov=sattlint --cov-fail-under=80` → **1359 passed** at 83.07% coverage.
