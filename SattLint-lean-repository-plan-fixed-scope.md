# Lean Repository and Test-Suite Plan

> Outcome: SattLint contains only supported SattLine behavior and the smallest
> standard toolchain needed to ship it with confidence. Optimize for regression
> signal per unit of maintenance, not test count, coverage, or dashboard scores.
> Preserve broad static-issue detection: repository reduction must not narrow the
> analyzer engine merely because an advanced rule is sophisticated.

Last reviewed: 2026-08-31

This plan replaces the old "CI Green Plan". It also supersedes the overlapping
`removal-plan.md` and `consolidated-review.md`; delete those plans after their
still-valid requirements have been captured here. Delete this plan when its exit
criteria are met.

## Why the old plan should not be executed

The previous plan was already stale and aimed at the wrong outcome:

| Finding on current `main` | Consequence |
|---|---|
| All files under "Dead files to delete" are already absent | Re-baseline instead of preserving a stale file list |
| It reports 483 total test-type errors but attributes about 498 to one category | Do not use copied error counts as a backlog |
| Pyright configuration includes `tests`, while CI and pre-commit check only `src/sattlint` | Make the supported typing scope explicit |
| Removed features still have large skipped test bodies | Delete obsolete tests completely; Git history is the archive |
| `ci.yml` has a pytest command ending in `|| true` | Required CI must not hide failures |
| Full pytest and Pyright are repeated across workflows and operating systems | Keep one canonical run for each distinct signal |
| The dependency-audit job skips the editable project after installing only the audit tool | Remove it or replace it with a check that actually audits the shipped environment |
| Generated reports, ratchets, and quality dashboards are tracked and tested | Remove self-maintaining evidence that drives no maintenance action |
| Maintainer docs describe workflows that no longer exist | Prefer a few authoritative docs over mirrored status documents |

CI is the source of truth for current results. This plan records scope and
exit criteria, not a hand-maintained table of pass counts.

## Definition of success

A retained file, test, dependency, command, workflow, or document must do at
least one of the following:

- protect a supported user-facing contract;
- protect a real bug regression or important SattLine semantic edge;
- validate a necessary package, operating-system, path, or encoding boundary;
- provide authoritative domain knowledge that is not cheaper to obtain elsewhere.

For analyzers, "supported" includes heuristic rules that detect plausible static
issues before they are common in the regression corpus. Judge their signal by
diagnostic value, precision, deterministic behavior, and explainability—not by
whether a maintainer used the rule recently.

Everything else is a candidate for deletion. Prefer deletion over moving code to
an archive, extracting another framework, or adding a tool that measures the
problem.

## Non-goals

- Making strict Pyright pass over every test mock, lambda, and third-party parser object.
- Preserving a global coverage percentage by testing internal maintenance tools.
- Splitting files solely to satisfy line-count or complexity budgets.
- Keeping skipped tests as tombstones for removed features.
- Building compatibility shims for unreleased or internal-only surfaces.
- Replacing custom maintenance machinery with different custom maintenance machinery.

## Fixed product boundary

The supported product has already been chosen. The cleanup must work inside this
boundary:

| Category | Scope |
|---|---|
| High-confidence cleanup now | Remove the ignored pytest step, stale plan contents, removed-feature test tombstones, generated artifacts, temporary probe leakage, dead LSP/editor references, and empty extras; align Ruff and Pyright scope; either consume or remove `uv.lock` |
| Supported product—must remain | Syntax checking, parser adapters, analyzer engine, `.slproj` and project loading, non-interactive analysis, ICF and graphics analysis, Textual UI, and advanced heuristic analyzers |
| Out of scope as public features—remove | DOCX generation, LSP/editor facade, simulation, telemetry summary, source diff, trace commands, repository audit/pipelines, and repository/AI governance machinery |
| Supporting internals—keep only when directly used | Cache implementation, shared findings/configuration models, parser integration code, and UI adapters |
| Operational defaults | Treat the Python modules as internal unless already covered by an explicit compatibility promise; keep deterministic parser-adapter regressions here; use a focused Windows installed-package smoke; retain publishing only for an active release channel |
| Preserve regardless of cleanup shape | Real regression fixtures, the full-grammar fixture, one honest Linux gate, and an evidence-based Windows signal |

This is not a product-discovery exercise. Do not remove or downgrade a supported
surface based on file count, test count, complexity, or recent usage. Items marked
out of scope should be removed, subject only to the consumer and compatibility
checks in Phase 3.

## Phase 0: Establish a fresh baseline

Run this phase in a current checkout before executing any deletion. Tie the
baseline to a commit and date; do not copy numbers from this review.

> Baseline recorded 2026-08-31 at commit `00b909c9d2639ae329767e4525230d2a77407a94`.

```bash
git log -1 --format=%H
python -m pytest --collect-only -q
python -m pytest -q --tb=short -rs --durations=25
python -m ruff check .
python -m ruff format --check .
python -m pyright src/sattlint
rg -n '@pytest\.mark\.(skip|xfail)|pytest\.skip' tests
rg -n 'reportPrivateUsage|reportArgumentType|import \*|_part[0-9]+' tests pyproject.toml
```

Record the following once before cleanup and once after it:

| Measure | Before | After |
|---|---:|---:|
| Production Python files and lines | 412 files / 109,096 lines | TBD |
| Test and test-support files and lines | 226 files / 77,035 lines | TBD |
| Collected / passed / skipped / xfailed tests | 1996 / 1842 / 154 / 0 | TBD |
| Full-suite wall time and slowest tests | ~22s collect; ~22-57s run | TBD |
| Runtime and development dependencies | 9 runtime; extras: test, dev | TBD |
| Installed console entry points | 11 (sattlint + 10 devtools/trace) | TBD |
| Required workflows, jobs, and CI minutes | 6 workflows (ci, fuzz, nightly, publish, scorecard, typing) | TBD |
| Tracked generated-artifact bytes | artifacts/ 80M; metrics/ 12K | TBD |

Also inventory every public command from `pyproject.toml`, `README.md`, `--help`,
and release workflows. They must agree before cleanup starts.

## Execution status

> Progress since baseline `00b909c9d2639ae329767e4525230d2a77407a94`. The After
> measurements are updated as vertical slices land; entry points and dependencies
> are the current live numbers.

| Measure | Before | After (current) |
|---|---:|---:|
| Production Python files and lines | 412 files / 109,096 lines | TBD (post-deletion) |
| Test and test-support files and lines | 226 files / 77,035 lines | TBD (post-bundle deletion) |
| Installed console entry points | 11 (sattlint + 10 devtools/trace) | **1 (`sattlint`)** |
| Runtime dependencies | 9 + extras test/dev | **5 (`lark`, `sattline-parser`, `tomli_w`, `rich`, `textual`)** |
| Removed runtime deps | — | `regex`, `openpyxl`, `defusedxml` deleted |
| Removed dev/test deps | — | `pytest-mock`, `pytest-xdist`, `interegular`, `pytest-benchmark`, `bandit`, `pip-audit`, `semble`, `vulture`, `types-openpyxl`, `types-regex` |
| Reproducibility | `uv.lock` (272K, unused) | **Removed**; CI uses `pip install -e ".[dev]"` |
| DOCX dependency push | `python-docx` | **Removed** |
| Trace console script | `sattlint-trace` | **Removed** |

### Phase-by-phase state

| Phase | Status | Notes |
|---|---|---|
| 0 Baseline | Done | Recorded at commit `00b909c9d2...`; `tests/__init__.py` aggregation blocker fixed |
| 1 Encode boundary | Not started | Public-contract/`SUPPORT.md` work; folded into later doc collapse |
| 2 Honesty fixes | **Done** | Pyright `include→src/sattlint`; removed empty `tui`/`telemetry` extras; temp probe trashed; `--cov*` removed from pytest addopts; ruff rev aligned; old-plan stale content superseded here |
| 3 Vertical removals | **In progress** | DOCX, source-diff, repo-audit CLI, and trace command surfaces removed; `devtools`→`structural` relocation done |
| 4 Retained-test simplify | **Done** | Bundle/gov test files deleted; retained test files now 85, full collection 1240 tests / 0 errors |
| 5 Replace CI | **Done** | Governance bundle (`scripts/`, `.github/hooks`, `.github/actions`, `artifacts/`, `metrics/`, 6 workflows) removed; minimal honest `ci.yml` (ruff/pyright/full pytest + wheel smokes Linux+Windows) + corrected `publish.yml`; stale pre-commit/PR template/repo instructions fixed; `repo-audit.instructions.md` removed |
| 6 Packaging/deps | **Done** | Only `sattlint` entry point; runtime deps trimmed to 5 (removed `regex`/`openpyxl`/`defusedxml`); unused dev/test deps removed; empty leftover dirs (`sattline_parser`, `sattlint_lsp`, `docgenerator` pycache) trashed; stale `build/` cleaned so wheel is honest; `uv.lock` removed; clean-wheel smoke passes |
| 7 Docs/metadata collapse | Pending | `SUPPORT.md`, README, feature-guide, ai-agent-reference LSP/trace/DOCX claims |

### Completed vertical slices (Phase 3)

| Slice | What was removed | Status |
|---|---|---|
| DOCX generation | `menu-reports-generate-docx` route + `python-docx` dep | **Done** |
| Source-diff command | `_app_source_diff.py`, `run_source_diff_report`, CLI/menu routes, tests, textual actions | **Done** |
| Repo-audit CLI | `repo_audit_fn`/`source_diff_fn` handlers, `_load_devtools_module`, CLI routes | **Done** |
| Trace command | `trace` subcommand, `_load_trace_module`, dispatch, `sattlint-trace` entry point, `run_trace_command`; `tracing.py` trimmed to `AnalysisTraceRecorder` + `detect_transform_invariant_violations` (engine-internal) | **Done** |
| `devtools` → `structural` | 10 files moved to `sattlint/structural/` (retained graphics dependency); 9 devtools entry points removed | **Done** |

### Verification notes

- Use the **system Python** (`/home/sqhj/.local/share/mise/shims/python`) for
  validation; the repo `.venv` has a stale `sattline_parser` (namespace package).
- Pyright diagnostics about `sattline_parser.models.ast_model` are venv-parser
  noise, not edit regressions.
- New CI uses direct standard-tool commands (no composite setup wrappers). CI
  smoke runs `sattlint syntax-check` on
  `tests/fixtures/sample_sattline_files/SattLineFullGrammarTest.s` (verified to
  exit 0 locally).

## Phase 1: Encode the fixed product boundary

Update `SUPPORT.md`, README, package metadata, installed commands, and `--help` so
they state the fixed boundary above. This phase records the supplied scope; it
does not ask maintainers to choose it again. Treat the following table as a
constraint for every later deletion.

| Surface | Status | Required contract |
|---|---|---|
| Syntax checking and parser adapters | Keep | Parse supported SattLine inputs consistently and report syntax failures with useful locations |
| Analyzer engine | Keep | One reusable engine produces deterministic findings for both front ends |
| `.slproj`, project loading, and non-interactive analysis | Keep | `.slproj` is the canonical project model, with only minimal global defaults; analysis works without the UI |
| ICF and graphics analysis | Keep | Their static issues use the same findings model and project context as source analysis |
| Textual/Rich interactive UI | Keep | A thin presentation layer over the same project loader and analyzer engine; no duplicated analysis logic |
| Advanced/heuristic analyzers | Keep | Each rule has a stable identity, useful explanation and location, a configuration/suppression policy, positive coverage, false-positive coverage, and regression cases where available |
| DOCX documentation generation | Remove | It is outside the static-analysis product; remove its code, tests, docs, commands, and exclusively owned dependencies |
| LSP/editor facade | Remove | It is outside the confirmed product and its current metadata/documentation are contradictory |
| Simulation, telemetry summary, source diff, and trace commands | Remove | They are outside the confirmed workflow unless an implementation is strictly internal to a retained analyzer |
| Cache management | Keep only as hidden infrastructure if required | It must be transparent to correctness; avoid making cache administration a separate product surface |
| `repo-audit` and internal analysis pipeline | Remove from the shipped product | Repository maintenance is not SattLine static analysis |
| Doc gardener, layer linter, structural ratchets, review, and observability tools | Remove by default | Prefer standard development tools and direct tests |
| AI work maps, context-health gates, edit hooks, prompts, and coordination state | Collapse to minimal guidance | Keep short repository-specific instructions only |
| ClusterFuzzLite and local fuzz harnesses | Move upstream or schedule only if actionable | Parser-owned defects belong near `sattline-parser`; retain deterministic adapter regressions here |
| Unadvertised subpackages and helpers | Map to a retained surface or remove | Importability alone is not a product contract |

For each retained surface, record:

1. its public command or API contract;
2. the modules, tests, dependencies, fixtures, and documentation it owns;
3. the failure classes its tests protect;
4. the maintainer responsible for changes to that contract.

If external users depend on a released surface marked for removal, use the normal
deprecation policy; otherwise prefer clean removal.

### Product architecture constraint

Keep one analysis path:

1. parser adapters normalize supported SattLine inputs;
2. `.slproj` and project loading assemble source, ICF, graphics, and configuration;
3. the analyzer engine and rule registry produce one findings model;
4. the non-interactive CLI and Textual UI render those findings.

No UI, command, or format adapter should implement a second analyzer pipeline.
New static checks should normally be a rule plus focused fixtures—not a new
command, report framework, or orchestration layer.

Use the analyzer registry as the single source of truth for rule IDs, descriptions,
default severity, applicability, and configuration. CLI/UI rule discovery and any
generated reference should derive from it at runtime; do not maintain parallel
catalogs by hand. Adding a rule should require little more than its implementation,
registration, and focused examples.

## Phase 2: Make immediate honesty fixes

These changes do not alter the supported SattLine product and can land before
larger vertical removals:

1. Remove the stale file names and copied error totals from the old plan.
2. Delete complete test functions for removed features. Do not keep their skip
   markers, empty bodies, or mock setup.
3. Investigate and remove `tests/_tmp_cli_probe_input_should_not_persist__.txt`
   if it is test leakage rather than a deliberate fixture.
4. Align Pyright configuration with the actual gate. Recommended default:
   strict-check production code under `src/sattlint`, not `tests`.
5. Delete the non-gating duplicate pytest step in `ci.yml`, or make it the one
   canonical real gate. Remove `|| true` either way.
6. Align the Ruff version used by the development environment and pre-commit.
7. Remove empty optional-dependency groups and other configuration with no effect.
8. Remove or correct the dependency-audit job: a job that installs only
   `pip-audit` and uses `--skip-editable` does not demonstrate that SattLint's
   installed dependency set is safe.

Validation for each batch:

```bash
python -m pytest --collect-only -q
python -m pytest <focused-paths> -q --tb=short
python -m ruff check <touched-paths>
python -m pyright src/sattlint
python -m pytest -q --tb=short
```

## Phase 3: Remove unsupported surfaces vertically

Remove one out-of-scope surface per reviewable change. A vertical deletion includes
all of its ownership, not just its obvious module:

- console entry points and CLI/menu routes;
- production modules, assets, and compatibility adapters;
- tests, helpers, fixtures, benchmarks, and type suppressions;
- runtime and development dependencies;
- workflows, pre-commit hooks, scripts, metrics, and generated reports;
- user, maintainer, architecture, and AI documentation.

The recommended first large deletion is the repository self-governance bundle,
which is outside the fixed product boundary. Review together:

- repo/context-health dashboard scripts and their renderer helpers;
- AI edit gates, `.github/hooks`, work-map tests, and coordination state;
- doc-gardener, layer-linter, structural-ratchet, and repo-audit policy code;
- analysis-pipeline, artifact-readiness, and owner-coverage machinery;
- related `test_ai_*`, pipeline, artifact, repo-health, and tool-wrapper tests;
- tracked `artifacts/`, `metrics/`, scorecards, ratchets, and audit snapshots.
- shared editor tasks and MCP/editor setup for the removed machinery; the current
  task list includes a command for a `vscode/` subtree that is no longer present.

Generated output belongs in ignored local directories or CI artifacts. A real
regression fixture belongs under `tests/fixtures` and should be minimal and
human-readable.

Do not accept "zero Python imports" as sufficient deletion proof. Search tests,
entry points, workflows, scripts, documentation, release smoke tests, and known
external use. For example, the existing removal plan calls
`SattLineFullGrammarTest.s` unused even though README and release verification use
it.

After each vertical deletion, build and install the package in a clean environment
and smoke every retained public command. Do not add a compatibility layer merely
to make deleted internal tests pass.

## Phase 4: Simplify the retained tests

### Keep

- public CLI exit codes and stable output contracts;
- real SattLine regression cases and semantic edge cases;
- analyzer findings at stable behavior boundaries, including advanced heuristics;
- negative and realistic false-positive cases for heuristic rules;
- one registry-level invariant test for unique rule IDs and complete required
  metadata, rather than duplicated catalog tests;
- project/config loading and path resolution;
- ICF and graphics analysis through the shared findings model;
- Textual user workflows and state transitions at the UI boundary;
- Windows-specific path, encoding, and filesystem behavior;
- clean-wheel installation and one representative end-to-end workflow.

### Delete

- tests for removed features or internal maintenance tools;
- permanent skips with no supported behavior to restore;
- lower-level tests that fail for exactly the same defect as a stronger boundary test;
- assertions that only verify mock calls or private wiring;
- Textual tests that pin only widget construction, callback identity, or private
  message routing when a user-visible behavior test covers the same risk;
- orphan support modules and fixtures after repository-wide consumer checks;
- tests whose only purpose is increasing coverage of code that should not exist.
- private compatibility facades such as `_reset_contamination_test_api.py` when
  tests can assert public analyzer findings instead.

### Consolidate or rewrite

- Replace repeated setup/action/assertion shapes with readable parameter tables.
- Replace numbered `part1` to `partN` organization with behavior names when doing
  so materially improves navigation; avoid rename-only churn.
- Before consolidating analyzer suites, build a compact rule matrix: rule/public
  behavior × positive case × negative or false-positive case × real regression.
  Use it to find overlap without deleting semantically distinct coverage.
- Replace wildcard imports and barrel-style test support with explicit imports
  and a few small typed AST/fixture builders; then remove the Ruff F403/F405 test
  exceptions if they have no remaining consumer.
- Prefer observable findings and outputs over private-call choreography.
- Keep direct private-function tests only for substantial domain logic that is
  difficult to exercise clearly through a stable boundary.
- Extract a shared helper only when several retained tests become simpler. Avoid
  another logic-heavy test-support framework.

The rule matrix is a temporary coverage inventory, not a generated dashboard.
Encode its durable content as parameterized tests and compact rule metadata. Do
not delete a supported heuristic solely because it lacks a historical bug fixture;
give it representative positive and false-positive cases instead.

Every remaining unconditional skip or xfail must have a supported behavior, a
tracking issue, an owner, and a removal condition. Platform/dependency skips must
state the exact unavailable condition. Quarantine is temporary, never a storage
class.

Keep only markers that CI or maintainers use to select a meaningful lane. Remove
category markers already expressed by paths/names, and do not keep a permanent
quarantine lane that merely hides failures.

### Test typing and upstream parser types

Production typing remains required:

```bash
python -m pyright src/sattlint
```

Full strict typing of tests is out of scope unless it is separately justified and
made a real CI gate. Do not add file-wide private-usage or unknown-lambda
suppressions simply to improve a non-gating number.

Parser annotation defects should be fixed and tracked in `sattline-parser`. In
SattLint, pin a compatible parser version and keep a small integration test at the
adapter boundary. Do not maintain a local inventory of hundreds of cascading
third-party type errors.

### Coverage

Re-baseline coverage after unsupported production surfaces are deleted. Apply the
floor to retained production code. Coverage is a backstop, not a reason to keep
duplicate tests, private-wiring tests, or internal devtools.

Move coverage flags out of global pytest `addopts` and into the canonical full CI
command. Focused local test runs should be fast and should not fail because they
did not execute the whole codebase.

## Phase 5: Replace CI with a small, honest signal path

The target is one required pull-request workflow, a release workflow only if
releases are still planned, and at most one scheduled maintenance workflow whose
findings are acted on. Prefer managed CodeQL and grouped dependency updates over
repository-specific security orchestration.

| Lane | Required signal |
|---|---|
| Linux PR gate | Clean install, Ruff lint/format, Pyright on production, one full pytest run with coverage, package smoke |
| Windows PR gate | Clean wheel install plus public-command and Windows path/encoding smoke tests |
| Release | If retained: build, metadata check, clean-wheel smoke, and publish only on explicit release intent |
| Scheduled maintenance | Only distinct actionable checks such as dependency audit or retained fuzzing |

Implementation rules:

- No required command may use `|| true`, `continue-on-error`, or an equivalent
  failure mask.
- Run Pyright once; its result is not operating-system dependent.
- Keep the existing full Windows run until failure history and a focused smoke
  suite demonstrate which distinct bugs it catches; narrow it only after that
  evidence exists.
- Use direct standard-tool commands in CI. Remove wrappers and composite setup
  actions that exist only to orchestrate this repository's custom gates.
- Keep pre-commit as developer convenience, not a second bespoke CI framework.
- Keep managed CodeQL and dependency updates as the low-maintenance security
  baseline. Remove custom scorecards, misleading audits, and PR fuzzing unless
  they regularly produce findings that this repository owns and fixes.
- Group dependency updates on a low-noise cadence.
- Run Vulture during this cleanup; keep it as a required gate only if its signal
  continues to justify triage cost.

Migrate required check names safely: record the branch-protection settings, add
and observe the replacement workflow on pull requests and `main`, update branch
protection, and only then delete the superseded workflows. Do not accidentally
turn a required check into a permanently pending or absent check.

## Phase 6: Shrink packaging and dependencies

1. Prefer one installed entry point, `sattlint`, with subcommands for retained
   features. Keep a separate entry point only when an external protocol genuinely
   needs one.
2. Do not ship repository-maintenance commands from `src/sattlint` to users.
3. Remove runtime dependencies with the deleted feature that owned them.
   Textual/Rich and dependencies genuinely required by retained ICF or graphics
   analysis are product dependencies, not cleanup candidates by default.
4. Use optional extras only for a retained optional feature whose combinations
   are tested. Delete empty extras.
5. Remove development dependencies with no retained command, test, or workflow.
   Candidates require verification and include benchmark, parallel-test, security,
   semantic-search, and typing-stub packages.
6. Choose one reproducibility model: use `uv.lock` in CI with a locked sync, or
   remove the unused lock. The current install path does not consume the large
   lock file; do not maintain a lock that validation ignores.
7. Make README, package metadata, entry points, and `sattlint --help` agree. In
   particular, resolve the current LSP claim.

## Phase 7: Collapse documentation and repository metadata

Keep the smallest authoritative set:

| Document | Purpose |
|---|---|
| `README.md` | User value, installation, and a five-minute workflow |
| `CONTRIBUTING.md` | Development setup and canonical validation commands |
| `ARCHITECTURE.md` | Retained product boundaries and dependency direction |
| `AGENTS.md` | Short repository-specific AI constraints only |
| `CHANGELOG.md`, `LICENSE`, `SECURITY.md`, `SUPPORT.md` | Release and community contract |

Keep SattLine reference material only when it is authoritative, permitted to
redistribute, and used. Remove or merge:

- stale roadmaps, completed execution plans, and duplicate repo maps;
- manually mirrored CI command/status documents;
- generated quality scores, debt ledgers, audit summaries, and trend dashboards;
- AI prompts, hooks, instructions, and workspace metadata without demonstrated value;
- shared editor tasks whose target scripts or directories no longer exist;
- tracked runtime artifacts that can be regenerated.

Publish one support contract—preferably `SUPPORT.md`—that settles LSP, DOCX,
configuration, public Python API, platforms, and stable versus preview commands.
It must list syntax analysis, `.slproj` project analysis, ICF/graphics analysis,
the Textual UI, and heuristic analyzers as supported, while removing LSP and DOCX
claims.
README, package metadata, and feature guides should link to it rather than define
competing matrices.

Collapse the overlapping scoped instruction files to a few files containing only
SattLine-specific invariants and test/CLI gotchas. Remove bundled generic Textual
guidance and generic review prompts; upstream documentation and regression tests
are cheaper to maintain. Keep policy JSON only when a retained automated check
consumes it, and never use `metrics/` for generated status snapshots.

Replace the current exception-heavy ignore policy with a short conventional one
after generated outputs are untracked. Source fixtures that use normally ignored
SattLine or text extensions should be allowed in their fixture directory, not via
repo-wide ad hoc exceptions.

Do not add a doc-gardening system to maintain a small doc set. Prefer links to
`sattlint --help` and a single source for command behavior over copied command
inventories.

## Guardrails for every phase

- Delete before refactoring.
- Search all consumer types before deletion; imports alone are insufficient.
- Preserve real regression fixtures and real-world SattLine edge cases.
- Do not use arbitrary file/line reduction targets as proxies for clarity.
- Do not add broad type suppressions for a non-gated metric.
- Do not move dead material into an in-repository archive.
- Do not introduce a new custom gate unless a standard tool cannot enforce a
  retained critical contract and a real prior failure justifies it.
- Do not delete a documented stable command, change required check names, or
  remove release automation without first verifying its external compatibility,
  branch-protection, or release impact.
- Keep each change focused on one hypothesis and run its narrow validation before
  the full suite.

## Final verification

Run from a clean environment on Linux, then run the distinct package and path
smokes on Windows:

```bash
python -m ruff check .
python -m ruff format --check .
python -m pyright src/sattlint
python -m pytest -q --tb=short -rs
python -m build
sattlint --version
sattlint --help
sattlint syntax-check tests/fixtures/sample_sattline_files/SattLineFullGrammarTest.s
```

Add one smoke command for each other retained surface: analysis from a minimal
`.slproj`, ICF analysis, graphics analysis, and headless Textual startup. Do not
add DOCX or LSP smokes after those surfaces are removed.

## Exit criteria

- Every retained product surface has an explicit owner and public contract.
- Syntax, project, ICF, graphics, CLI, and Textual routes all use the same analyzer
  engine and findings model.
- Every supported analyzer has a stable rule identity and focused positive and
  negative/false-positive coverage; meaningful heuristic breadth is preserved.
- The analyzer registry is the only rule catalog, and adding a rule does not
  require editing duplicated CLI, UI, documentation, or pipeline registries.
- Every remaining test maps to a retained contract, a named regression, or a
  necessary platform/package boundary.
- There are no removed-feature test tombstones and no unexplained permanent skips.
- Retained analyzer behavior is represented in a reviewed rule matrix; obsolete
  numbered suites, wildcard barrels, and private test compatibility namespaces
  have no remaining consumers.
- Required CI contains no ignored failures and no duplicate job without a distinct purpose.
- Pyright configuration, local documentation, pre-commit, and CI use the same scope.
- README, package metadata, installed entry points, and `--help` describe the same product.
- Generated reports, temporary probes, ratchets, and dashboards are not tracked.
- There is one authoritative support contract, CLI reference, architecture
  source, setup path, and canonical validation command.
- A clean wheel installs and retained command smokes pass on Linux and Windows.
- Before/after measurements show a smaller maintenance surface without losing
  coverage of the retained contract.
- `removal-plan.md`, `consolidated-review.md`, and this completed plan are deleted.

## Recommended execution order

1. Baseline and encode the fixed product boundary in the public contract.
2. CI/Pyright/Ruff honesty fixes and obsolete skipped-test deletion.
3. Repository self-governance removal as one or more vertical slices.
4. Remove DOCX, LSP, and other non-product surfaces vertically, one at a time.
5. Retained-test consolidation and fixture cleanup.
6. CI, packaging, dependency, and documentation collapse.
7. Clean-environment verification, before/after report, and plan deletion.
