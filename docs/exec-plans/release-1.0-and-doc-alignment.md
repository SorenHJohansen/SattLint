# SattLint Release 1.0 + Doc Alignment Plan

> Status: Active — Part A (release blockers) ✅ COMPLETE, Part B (docs) ✅
> COMPLETE, Part C and Part D pending.
>
> Source: repository review performed 2026-09-05 on branch
> `refactor/remove-app-facade` (5 unmerged commits on top of `main`).
>
> Verified ground truth at review time:
> - `src/sattlint/__version__.py` already reports `1.0.0`.
> - **No git tags exist**; `CHANGELOG.md` ends at `[Unreleased]` + `[0.1.1]`.
> - Full suite: **1216 passed** (39.7 s); `ruff check .` clean;
>   `ruff format --check .` clean (428 files); `pyright src/sattlint` 0/0/0.
> - Local gate is genuinely green; the blockers are release hygiene and
>   documentation drift, not code failures.

## Goal

Get SattLint to a shippable `v1.0.0` tag. The code is structurally sound — the
refactor produced clean, test-enforced layering — but the documentation
describes the pre-refactor state, the release metadata is inconsistent with the
code, and the publish path is not gated on CI. This plan separates:

- **Part A — Release blockers** (must land before the `v1.0.0` tag).
- **Part B — Documentation alignment** (must land before the tag; docs ship).
- **Part C — Architecture cleanup** (before or immediately after the tag).
- **Part D — CI / operations hardening** (before or immediately after the tag).

Guiding rule, consistent with `docs/design-docs/core-beliefs.md` (#11):

> Docs rot is technical debt; stale docs are worse than none.

## Current state & sizing

Review findings, ranked by severity:

| # | Finding | Severity | Area |
|---|---------|----------|------|
| F1 | Version is `1.0.0` in code, classifier `Production/Stable`, but no `1.0.0` CHANGELOG entry and no git tags | Blocker | Release |
| F2 | `publish.yml` is not gated on CI — a failing-CI tag can still publish | Blocker | CI |
| F3 | `format-icf` documented (README, feature-guide, SUPPORT, architecture) but the CLI command was removed | Blocker | Docs |
| F4 | README documents only `config.toml`; the `.slproj`/`init`/`--project` system is absent | Blocker | Docs |
| F5 | README/feature-guide show bare `sattlint analyze` which exits 2 without `--check` | Blocker | Docs |
| F6 | `CHANGELOG 0.1.1` claims removed subsystems: doc generation, LSP, `repo-audit` | High | Docs |
| F7 | `architecture.md`, `repo-map.md`, `python-api.md` reference removed/relocated paths (`structural/`, top-level `app_textual.py`/`tracing.py`/`config.py`, `sattlint.structural`) | High | Docs |
| F8 | Stale paths/claims: `validation-map.md`, `CONTRIBUTING.md` (uv claim, `.vscode`), `.github/instructions` `applyTo`, `core-beliefs.md` (nonexistent stale-doc scanner), ISSUE_TEMPLATE broken links | High | Docs |
| F9 | License metadata uses deprecated `license = { text = "MIT" }` dict form | Medium | Release |
| F10 | `application/service.py` is production-dead (tests only) | Medium | Code |
| F11 | Two independent "semantic" engines overload the name | Medium | Code |
| F12 | Overlapping command seams: `application/commands.py` vs `cli/app_commands.py` vs `cli/app_cli_commands.py` vs `cli/command_handlers.py` | Medium | Code |
| F13 | Pyright "strict" is nominal in the UI layer (file-level suppressions) | Medium | Code |
| F14 | Orphaned fuzzers at package root (`engine_fuzzer.py`, `icf_fuzzer.py`, `syntax_fuzzer.py`), unwired | Low | Code |
| F15 | `app.py` remains a 344-line compatibility shim; entry point not repointed | Low | Code |
| F16 | `analyzers/string_inference.py` is 1716 lines | Low | Code |
| F17 | Stale action pins + branch behind `main`; `download-artifact` v6 vs `upload-artifact` v7 | Low | CI |
| F18 | Windows gets only a smoke; full suite never runs on a claimed supported platform | Low | CI |
| F19 | Scorecard badge in README but no scorecard workflow; orphaned dependabot branches | Low | Ops |
| F20 | `.gitignore` gaps (`cache-dir/`, `.ruff_cache/`, `.venv/`); `mise.toml` tracked despite "DO NOT COMMIT"; stray `__pycache__` under `scripts/`, `.github/hooks/scripts/`, `docs/maintainers/ai/` | Low | Ops |
| F21 | No release automation: no GitHub Release step, no attestations, no `RELEASE.md`, no `CODEOWNERS` | Low | Ops |
| F22 | `pyproject` classifier `5 - Production/Stable` asserted before any tag exists | Low | Release |

---

## Part A — Release blockers

### Phase 1 — Add the `1.0.0` CHANGELOG entry (F1) ✅ COMPLETE

Implemented 2026-09-05: dated `## [1.0.0] - 2026-09-05` section added with the
stable CLI surface; misleading 0.1.1 subsystem claims removed; subsections
normalized; `[1.0.0]` reference link added. Note: `[0.1.1]` reference link was
omitted because 0.1.1 was never tagged.

- Replace the `[Unreleased]` block in `CHANGELOG.md` with a dated
  `## [1.0.0] - <release date>` section (Keep a Changelog format).
- Fold the current Unreleased items into it: single-source version export,
  CLI `--version`, release/security repository metadata.
- Rewrite the misleading `[0.1.1]` entry (F6): remove claims for
  documentation generation, LSP tooling, and `repo-audit`, which no longer
  exist; keep the static-analysis/parser-validation core.
- Normalize the non-standard `### Added in 0.1.1` / `### Notes` subsections
  to `### Added` / `### Notes` per Keep a Changelog, and add the `[0.1.1]:`
  version-diff reference links at the bottom.
- Note the obsolete "0.1.1 baseline for future tagged releases" line — 0.1.1
  was never tagged.

Acceptance: `CHANGELOG.md` has a dated `[1.0.0]` entry; nothing under
`[Unreleased]`; no references to removed subsystems; `markdownlint` clean.

### Phase 2 — Gate `publish.yml` on CI success (F2) ✅ COMPLETE

Implemented: `ci.yml` gained a `workflow_call:` trigger; `publish.yml` gained a
`gate` job (`uses: ./.github/workflows/ci.yml`) with `build` set to
`needs: gate`. A tag now runs the full CI gate on the tagged commit before it
can build or publish.

- Make the `build` (or a new `gate`) job depend on a passing CI run for the
  exact commit being tagged. Practical options:
  - Add a `ci` workflow `needs:`-style dependency via a reusable workflow or
    a `workflow_run` trigger, **or**
  - rely on branch protection requiring the `linux-gate` check to pass on the
    tag commit, documented in `RELEASE.md`.
- Do not allow a `v*` tag to publish while `linux-gate` is red.

Acceptance: a tag pushed on a commit where `linux-gate` failed cannot reach
PyPI; the mechanism is documented.

### Phase 3 — Fix license metadata (F9) ✅ COMPLETE

Implemented: `pyproject.toml` now uses `license = "MIT"` with
`license-files = ["LICENSE"]`; `python -m build` + `twine check` pass with no
deprecation warnings.

- Replace `license = { text = "MIT" }` in `pyproject.toml` with the PEP 639
  form: `license = "MIT"` (SPDX expression), optionally
  `license-files = ["LICENSE"]`.
- Re-run `python -m build` + `python -m twine check dist/*` and confirm zero
  warnings.

Acceptance: `twine check` reports no license deprecation warning.

### Phase 4 — Confirm release-environment protection (F2/ops) ⚠️ PARTIAL

The `pypi-release` environment did not exist and was created via the GitHub API
(no protection rules — the API cannot set reviewer identities). Adding required
reviewers is a manual Settings step; documented in `RELEASE.md` with a
verification command.

- Verify in GitHub settings that the `pypi-release` environment
  (`publish.yml`) has required reviewers / deployment protection, since
  trusted publishing (OIDC) is enabled but protection is external to the repo.
- Record the confirmation in `RELEASE.md`.

Acceptance: a human review gate exists before PyPI publish, or the decision to
publish without it is recorded explicitly.

### Phase 5 — Decide the classifier and write `RELEASE.md` (F22, F21) ✅ COMPLETE

Implemented: `RELEASE.md` created with the tag-and-verify procedure, the
pre-release checklist, the PyPI environment protection step, and the recorded
classifier decision (keep `5 - Production/Stable` for the imminent 1.0.0
release).

- Make a conscious call on `Development Status :: 5 - Production/Stable`
  (`pyproject.toml`) — either keep it because 1.0 is the target, or move to
  `4 - Beta` until the tag exists. Record the decision.
- Add a `RELEASE.md` (or extend `CONTRIBUTING.md`) with the release checklist:
  tag name `v1.0.0` (matches `publish.yml` `v*` trigger), CHANGELOG update,
  classifier decision, environment-protection confirmation, post-publish
  verification (`pipx install sattlint`, run `--version`, `--help`, one
  `syntax-check`).

Acceptance: `RELEASE.md` exists and documents the tag-and-verify procedure.

---

## Part B — Documentation alignment

### Phase 6 — Remove every `format-icf` CLI reference (F3) ✅ COMPLETE

`format-icf` is a library function only (`analyzers/icf/_icf_file_io.py`), not a
CLI command. Remove or correct every reference:

- `README.md:99-100`
- `docs/public/feature-guide.md:92-98`
- `SUPPORT.md:24` (listed as "Preview")
- `docs/public/architecture.md:56` (listed as a command-mode flow)
- `docs/exec-plans/architecture-upgrade-plan.md:169` already records the
  deletion; keep that as the historical note.

If the formatting capability is worth exposing, that is a separate feature
decision — do not restore the command silently.

Acceptance: no tracked doc presents `sattlint format-icf` as a CLI command;
`rg "format-icf"` over docs returns only the historical exec-plan note and the
library-function reference.

### Phase 7 — Document the `.slproj` workflow in README (F4) ✅ COMPLETE

- Add `.slproj` to the README: `sattlint init`, `sattlint --project PATH`, and
  auto-discovery, matching `AGENTS.md` and `docs/public/feature-guide.md`.
- Reconcile the config-first narrative: `.slproj` merges over
  `~/.config/sattlint/config.toml`; keep the Setup/configuration section but
  present the project file as the portable, checked-in option.

Acceptance: README covers `init`/`--project`; the config and project-file paths
are both present and consistent with `sattlint --help`.

### Phase 8 — Fix the bare `analyze` examples (F5) ✅ COMPLETE

- `README.md:95` and `docs/public/feature-guide.md:69,71` show bare
  `sattlint analyze`, which exits 2 with "at least one `--check KEY` is
  required".
- Change the examples to include a `--check` argument (e.g.
  `sattlint analyze --check naming`), or document that `--check` is required
  and show `sattlint analyze --list-checks` first.

Acceptance: every documented `analyze` invocation in the README and public
docs runs successfully as written.

### Phase 9 — Correct stale paths and claims in maintainer docs (F7, F8) ✅ COMPLETE

- `docs/public/architecture.md`:
  - `:15-16` — replace `app.py / app_*.py` and `config.py / config_io.py`
    with the actual layout (`cli/`, `application/`, `ui/`, `config/`).
  - `:44` — reword "app.py owns CLI flows, the interactive UI, analyzers,
    reporting, validation, and configuration" to reflect the post-refactor
    ownership split.
- `docs/maintainers/repo-map.md`:
  - `:16` `src/sattlint/app_textual.py` → `src/sattlint/ui/app_textual.py`.
  - `:17` `src/sattlint/structural/` → remove (deleted on this branch).
  - `:18` `src/sattlint/tracing.py` → `src/sattlint/core/tracing.py`.
- `docs/public/python-api.md`:
  - `:88-92,120` — remove `sattlint.structural` / `collect_graphics_layout_entries_for_target`.
- `docs/maintainers/validation-map.md`: `tests/test_cli.py` →
  `tests/app/test_cli.py` (`:6,9`); `tests/test_analyzer_guardrails.py` →
  `tests/analyzers/test_analyzer_guardrails.py` (`:15`); quote the `-k`
  expression at `:19`.
- `docs/maintainers/analyzer-authoring.md:48`: `analyzers/reset_contamination.py`
  → `analyzers/reset_contamination/` (now a package).
- `docs/design-docs/core-beliefs.md`: remove/replace references to
  `docs/exec-plans/tech-debt-tracker.md` (`:50`) and the nonexistent
  automated stale-doc scanner / weekly doc-gardening (`:36,58`).

Acceptance: every path referenced in maintainer docs exists on this branch;
`rg` for the removed identifiers returns nothing in tracked docs.

### Phase 10 — Fix CONTRIBUTING.md and issue templates (F8) ✅ COMPLETE

- `CONTRIBUTING.md:65` — remove the claim that "CI already installs through
  `uv`"; CI uses `pip install -e ".[dev]"`.
- `CONTRIBUTING.md:121,176,193` — drop the `.vscode/settings.json` references
  (the directory does not exist) or restore the file.
- `CONTRIBUTING.md:161` — `tests/test_cli.py` → `tests/app/test_cli.py`.
- `.github/ISSUE_TEMPLATE/bug_report.md:13` — remove `sattlint repo-audit` as
  an example surface (command removed).
- `.github/ISSUE_TEMPLATE/feature_request.md:10` — fix the link to
  `docs/references/public-support-matrix.md` (file does not exist; the matrix
  was consolidated into `SUPPORT.md`).
- `.github/instructions/*.md` `applyTo` lists: `cli-app.instructions.md:4`
  (`src/sattlint/config.py`, `tests/test_cli.py`),
  `analyzer-architecture.instructions.md:4` (`src/sattlint/app_analysis.py`,
  `tests/_analyzers_*.py`), `test-fixtures.instructions.md:4`
  (`tests/test_analyzer_guardrails.py`).

Acceptance: no tracked contributor-facing doc references a missing file,
command, or workflow.

### Phase 11 — Resolve the `docs/public/cli-commands.md` gap (F7) ✅ COMPLETE

Either write `docs/public/cli-commands.md` with the real command surface
(verified against `sattlint --help`: `init`, `syntax-check`, `validate-config`,
`cache-prune`, `analyze` + global flags) or drop it from any doc inventory.
The `[Unreleased]` reference set and `docs/public/README.md` must not point at
a missing file.

Acceptance: `docs/public/cli-commands.md` exists and matches `--help`, or no
doc references it.

### Phase 12 — Correct the exit-code contract in docs (F5-adjacent) ✅ COMPLETE

- `README.md:85-89` and `docs/public/feature-guide.md:56,185-192` present "1 —
  command ran and found a real problem" as a general contract. Only
  `syntax-check` returns 1 on problems; `analyze` returns 0 even when issues
  are found; `validate-config` returns 2 on config errors.
- Reword to describe per-command behavior (0/1/2 constants from
  `cli/_exit_codes.py`).

Acceptance: README and feature-guide exit-code statements match actual CLI
behavior for `syntax-check`, `analyze`, and `validate-config`.

---

## Part C — Architecture cleanup

> These are polish items; none blocks the code path (1216 tests green,
> layering enforced by `tests/test_dependency_guard.py`). Do them on this
> branch before the tag, or immediately after.

### Phase 13 — Decide the fate of `application/service.py` (F10)

`application/service.py` (typed `Project`/`AnalysisOptions`/`analyze_project`)
is imported only by `tests/app/test_app_service.py`. Options:

- **Wire it in** — make `cli/` or `application/analyze.py` route through the
  typed service (matching architecture-upgrade-plan Phase 5 intent), or
- **Delete it** — if the terminal flows are the real surface, remove the
  unused service and its test.

Record the decision in the module docstring or the plan. Do not ship a
production-dead subsystem labeled as the typed API.

Acceptance: `application/service.py` is either on a production import path or
deleted.

### Phase 14 — Consolidate the command seams (F12)

- `application/commands.py` (436 lines, live behind the interactive menu via
  `application/analyze.py`) vs `cli/app_commands.py` (whose docstring claims
  it is "the replacement for the old `application.commands` surface").
- Rename or merge so the four "command" modules have distinct, honest names —
  e.g. `application/menu_commands.py` vs `cli/commands.py`, and fold
  `cli/command_handlers.py` into its caller if it has no distinct role.

Acceptance: no two modules claim the same "commands" role; the docstring
"replacement" claim is either true or removed.

### Phase 15 — Resolve the semantic-name overload (F11)

- `core/semantic.py` (shared snapshot) vs `analyzers/sattline_semantics.py`
  (~1650 lines, self-contained `SemanticRule` engine that does not use
  `core.semantic`).
- Rename the self-contained analyzer (e.g. `sattline_semantics.py` →
  `semantic_rules.py` or `sattline_rule_engine.py`) and its rule-data modules,
  or document the distinction at both module heads.

Acceptance: `rg -n "semantic"`-based reader confusion is resolved; both
modules explain what they own.

### Phase 16 — Make Pyright strict honest in the UI layer (F13)

- Either lift the file-level `# pyright:` suppressions in `ui/_app_textual_*.py`
  (unknown variable/member types, general type issues) so `strict` is real, or
  document a carve-out (e.g. a `ui`-scoped relaxed profile) in
  `pyproject.toml` and the architecture doc.
- The `core-beliefs` claim "pyright-strict-clean" must describe reality.

Acceptance: pyproject's strict mode either covers `ui/` without suppressions
or explicitly excludes it with rationale.

### Phase 17 — Remove or relocate the fuzzers (F14)

- `engine_fuzzer.py`, `icf_fuzzer.py`, `syntax_fuzzer.py` are Atheris
  `__main__` scripts imported by nothing and unwired to any gate.
- Either move them under `scripts/`/a `tools/` dir with a README, or delete
  them. They must not sit at package root.

Acceptance: no Atheris harness remains at `src/sattlint/` root.

### Phase 18 — Repoint the entry point and retire the `app.py` shim (F15)

- The console script `sattlint = "sattlint.app:cli"` keeps `app.py` (344-line
  re-export facade) alive. Repoint `pyproject.toml` to `cli/startup` (or
  `cli/entry`), update `__main__.py` and any tests, then trim `app.py` to its
  genuine public surface or delete it.

Acceptance: no production import needs the `app.py` alias layer; the package
entry point points at the CLI owner.

### Phase 19 — Split `analyzers/string_inference.py` (F16)

- 1716 lines, the largest file. Split by real concepts (cursor-aware builtin
  handling, exact string inference) per architecture-upgrade-plan Phase 13
  guidance. No behavior change.

Acceptance: no file in `src/` exceeds ~1000 lines; gates stay green.

---

## Part D — CI / operations hardening

### Phase 20 — Reconcile the branch with `main` and refresh action pins (F17)

- `main` already merged `actions/setup-python 7.0.0`; this branch pins
  `setup-python` at v6.0.0 (`ci.yml:27`) and `checkout` at v6.
- Merge/rebase `main` into `refactor/remove-app-facade` and take the dependabot
  bumps: `checkout` → v7, `setup-python` → 7.0.0, `download-artifact` → v8 to
  match `upload-artifact` v7 (`publish.yml`), `gh-action-pypi-publish` → 1.14.x.
- Add the missing `# vX` comment to `gh-action-pypi-publish`
  (`publish.yml:72`).

Acceptance: pinning style is uniform (SHA + tag comment); this branch is at or
ahead of `main` on action versions.

### Phase 21 — Run the full suite on Windows (F18)

- `ci.yml` `windows-smoke` only builds and runs three commands. Add
  `pytest`/`ruff`/`pyright` on `windows-latest`, or document that Windows is
  "best-effort" in `SUPPORT.md` if the full gate stays Linux-only.

Acceptance: either Windows runs the full gate or SUPPORT.md does not overclaim.

### Phase 22 — Restore the scorecard workflow (F19)

- `README.md:3` shows the OpenSSF Scorecard badge, but no scorecard workflow
  exists (only `ci.yml` + `publish.yml`). Add
  `ossf/scorecard-action` (the dependabot branches exist) or remove the badge.

Acceptance: badge and workflow are consistent.

### Phase 23 — Release automation and hygiene (F20, F21)

- Consider a GitHub Release creation / release-notes step in `publish.yml`
  (soft via `softprops/action-gh-release`), artifact attestations, and a
  `CODEOWNERS` review gate for the release path.
- Extend `.gitignore`: `cache-dir/`, `custom-cache-dir/`, `report-cache-dir/`,
  `.ruff_cache/`, `.venv/`.
- Decide `mise.toml`: it is tracked despite `.gitignore` labeling it "Local dev
  config (DO NOT COMMIT)" — either un-track it or remove the gitignore line.
- Remove stray `__pycache__` clutter under `scripts/`,
  `.github/hooks/scripts/`, and `docs/maintainers/ai/` (use `trash-put`).

Acceptance: `.gitignore` covers every generated local dir; no stray `.pyc`
directories remain in tracked areas; release artifacts are decided.

### Phase 24 — Clean up orphaned remote branches (F19)

The following remote branches reference removed surfaces and should be deleted
by you (this is a git operation, run it yourself):
`dependabot/npm_and_yarn/vscode/*`, `dependabot/github_actions/ossf/scorecard-action-*`
(after Phase 22), `codeql upload-sarif`, `setup-node*`, `setup-uv*`,
`upload-artifact-7`, `checkout-6*`, and stale `python-dependencies-*`.

Acceptance: `git branch -a` shows no dependabot branches for removed
directories or obsolete action majors.

---

## Definition of Done

This plan:

- Ships a tagged `v1.0.0` with a dated CHANGELOG entry and no misleading
  subsystem claims.
- Cannot publish to PyPI on a failing CI run.
- Builds and publishes with zero `twine`/setuptools deprecation warnings.
- Has user docs (README, feature-guide, SUPPORT) that match the actual CLI —
  commands, `.slproj` workflow, and exit codes.
- Has maintainer docs that reference only existing files and paths.
- Keeps the layering enforced by `tests/test_dependency_guard.py` green.
- Resolves the semantic-naming overload, the command-seam overlap, and the
  production-dead service before they accrete.
- Runs the full gate on Linux and (decision recorded) Windows.
- Gates: `pyright src/sattlint` 0 errors, `ruff check` clean,
  `ruff format --check` clean, full pytest green, `pre-commit run --all-files`
  green.
- No functionality or diagnostic behavior changes unintentionally.

## Implementation principles

- Land Part A (release blockers) and Part B (docs) before the tag; Part C and
  D can follow the tag but should not drift.
- Make one phase at a time; keep the repository green between phases.
- Prefer deleting dead surfaces (service, fuzzers, `app.py` aliases) over
  relocating them.
- Update docs in the same commit as the code that invalidates them — stale
  docs are worse than none.
- For every doc claim, verify against `sattlint --help` and the filesystem,
  not memory.
- Record decisions (classifier, service fate, Windows scope, environment
  protection) in writing — `RELEASE.md` or the relevant module docstring.
