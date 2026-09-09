# Agent Reference

Consolidated operating reference for SattLint agents: repository map,
quality gates, validation map, core beliefs, and deferred-work tracking.
`AGENTS.md` is the table of contents; this file is the depth behind it.

## Repository Map

### Core Surfaces

| Path | Role | First validation |
| --- | --- | --- |
| `sattline-parser` (external) | Parser grammar, AST, transformer, strict syntax behavior | `sattlint syntax-check` or targeted parser pytest |
| `src/sattlint/cli/` | CLI entrypoints and command handlers | Targeted owner pytest, then Ruff and Pyright |
| `src/sattlint/analyzers/` | Heuristic analyzers and the rule registry | Targeted analyzer pytest |
| `src/sattlint/core/` | Shared semantic snapshot, document helpers, and the engine-internal analysis trace recorder (`core/tracing.py`) | Targeted pytest |
| `src/sattlint/project/` | `.slproj` project model and loading | `tests/project/`, targeted pytest |
| `src/sattlint/` (ICF, graphics, validation, engine) | ICF analysis, graphics rules, strict syntax validation | Targeted owner pytest |
| `src/sattlint/ui/` | Textual interactive UI | `tests/app/test_app_textual*.py` |
| `src/sattlint/change_review/` | Semantic diff + impact analysis between official/draft project versions | `tests/change_review/`, `tests/app/test_app_textual_change_review.py` |
| `tests/` | Owner suites and regression proofs | Narrow pytest slice first |
| `.github/` | CI workflows and scoped instructions | Diagnostics or config validation, then workflow run if needed |

### Primary Entrypoints

- `sattlint`
- `python -m pre_commit run --all-files`
- `python -m ruff check .`
- `python -m pyright src/sattlint`
- `python -m pytest -q --tb=short`

### Actual Runtime Map

- Stable CLI commands enter at `src/sattlint/cli/startup.py` and dispatch
  through `src/sattlint/cli/commands.py` into the shared app helpers, analyzers,
  reporting, and parser-backed semantic loaders.
- The interactive Textual menu also starts at `src/sattlint/cli/startup.py`
  (no subcommand) and runs the `ui/` shell; its UX contract is looser than the
  stable CLI commands.

### Assistant Anchors

- `AGENTS.md` is the stable AI table of contents and owns context loading order
  and default workflow rules.
- `ARCHITECTURE.md` captures the short architecture boundary summary.

---

## Quality Gates

SattLint has a small, honest lint, type, and test path. This section defines the
layered operating contract so single-chat assistant work and human workflows use
the same gate names.

### Validation Stages

| Stage | Responsibility | Required commands | Expected proof |
| --- | --- | --- | --- |
| Focused local | Immediate correctness on the touched slice | Focused pytest, touched-file Pyright when Python files changed | One focused executable check before widening |
| Pre-commit | Fast local hygiene before sharing work | `python -m pre_commit run --all-files` | Ruff fix, Ruff format, Pyright on `src/sattlint tests`, SattLine syntax-check on staged fixtures |
| Full local | Broader branch health | `python -m ruff check .`, `python -m ruff format --check .`, `python -m pyright src/sattlint tests`, `python -m pytest -q --tb=short` | Full lint, type, and test pass |
| CI | Full trust on PRs and main | `ci.yml`: clean install, the full local set, clean-wheel smokes (Linux + Windows) | Deterministic install and retained-command smokes |

### Focused Local Contract

1. Start from the controlling file or symbol.
2. Make the smallest local edit.
3. Run the first focused executable validation immediately.
4. Only widen after the local check passes.
5. Summarize outcome and remaining risk directly in the final response when needed.

### Pre-Commit Gate

`python -m pre_commit run --all-files`

This is the default local safety gate. It is fast and file-scoped: Ruff
autofix, Ruff format, Pyright on `src/sattlint tests` (with the existing
per-file suppressions in test files), SattLine syntax-check on staged SattLine
fixtures, and the standard pre-commit-hooks checks.

### CI Gate

`ci.yml` is the single required workflow. It runs Ruff lint and format, Pyright
on production code and tests, the full pytest suite (with an aggregate coverage
floor of 80% that only ratchets up), a bounded `fuzz-smoke` over SattLint-owned
`.icf`/graphics readers, and clean-wheel install smokes on Linux and Windows.
No required command masks failures.

`publish.yml` builds distributions, checks metadata, smokes a clean wheel, and
publishes to PyPI only on explicit `v*` tag pushes.

---

## Validation Map

Canonical first-check command source for SattLint maintainer surfaces.

- Parser, grammar, transformer, AST, or strict validation:
  `python -m pytest tests/app/test_cli.py -x -q --tb=short`
  or `sattlint syntax-check <target>`
- CLI routing or argparse behavior:
  `python -m pytest tests/app/test_cli.py -x -q --tb=short`
- Interactive / menu / Textual app behavior:
  `python -m pytest tests/app/test_analysis_*.py tests/app/test_app_textual.py tests/app/test_cli.py -x -q --tb=short`
- Analyzer behavior (rule-specific):
  `python -m pytest tests/analyzers/test_<rule>.py -x -q --tb=short`
- Analyzer registry / guardrail invariants:
  `python -m pytest tests/analyzers/test_analyzer_guardrails.py -x -q --tb=short`
- Project / config loading:
  `python -m pytest tests/project/ -x -q --tb=short`
- ICF and graphics analysis:
  `python -m pytest -k "icf or graphics" -x -q --tb=short`
- Python behavior with a nearby focused test:
  `python -m pytest <test_file> -x -q --tb=short`
- Finish gate for touched Python files:
  `python -m ruff check <touched_python_files>`
  then
  `python -m pyright <touched_python_files>`
- Fast local hygiene gate:
  `python -m pre_commit run --all-files`
- Full local validation before push:
  `python -m ruff check . && python -m ruff format --check . && python -m pyright src/sattlint && python -m pytest -q --tb=short`

---

## Core Beliefs - Golden Principles for SattLint

Agent-first principles that keep this codebase legible, consistent, and maintainable.

### Governance

#### 0. If It Cannot Be Enforced, It Will Drift (Meta-Principle)

Every important rule should map to:

- lint rule
- CI check
- automated agent review
- or required PR template item

#### 2. AGENTS.md Is Table of Contents, Not Encyclopedia

- Keep it short and pointed — a table of contents, not an encyclopedia
- Point to deeper docs, don't duplicate them
- Update only on material change to architecture/invariants

### Enforcement

#### 10. No Silent Fallbacks

Failures must be explicit and actionable.

- Parser: clear error messages with remediation hints
- Analyzers: confidence levels, not guesswork

#### Enforcement Mechanisms

Every principle must have enforcement:

- Architecture boundaries → `tests/test_dependency_guard.py`
- Doc freshness → reviewed during each exec-plan pass (no automated stale-doc scanner)
- Casefold enforcement → `tests/test_casefolding_guard.py`
- Shared utility reuse → shared helpers live in `src/sattlint/analyzers/shared/` and `src/sattlint/utils/`; duplication is caught in review (no automated detector)
- File size → reviewed during each exec-plan pass (no mechanical cap)

### Repository Knowledge

#### 1. Repository Knowledge Is System of Record

Knowledge lives in-repo or it doesn't exist for agents.

- No external docs (Google Docs, Slack threads, oral tradition)
- Design decisions and plans live in-repo as root-level records
- Tech debt → tracked in `DEFERRED_WORK.md` and in-repo tracking

### Docs Rot

#### 11. Docs Rot Is Technical Debt

Stale documentation is worse than no documentation.

- Docs are checked for staleness during each review pass; links must be valid; dead links are lint errors
- Version docs with code (same PR when behavior changes)
- Links must be valid; dead links are lint errors

### Security

#### 12. Security By Default

No secrets, PII, or machine-specific paths in outputs.

- Redact by type/category, not raw values
- Report `SQHJ`-style paths as sensitive
- Prefer repo-relative paths in all artifacts

### Architecture

#### 7. Strict Boundaries, Local Autonomy

Enforced architecture with freedom inside boundaries.

- Parser core never imports application code
- CLI/TUI → Core → Analyzers/Engine → Parser (dependency direction)
- Within a module, agent has freedom of expression

#### 8. Machine-Readable Outputs

Reports serve both humans and agents.

- Findings: structured (severity, confidence, location)
- Logs: key=value, issue-scoped
- No pretty-printed tables that hide structure

### Boundaries

#### 4. Parse, Don't Validate

Data shapes validated at boundaries (parser, config, analyzer inputs).

- Use AST models, not dicts with magic keys
- Validate early, fail clearly, no silent fallbacks
- `sattlint syntax-check` is strict by design

**Construction-time parsing**: Transform data into stronger types at construction, not at validation.

- Use `__post_init__` in dataclasses to parse and normalize on construction
- Make invalid states unrepresentable by construction
- If parsing fails, fail immediately with clear error—don't return "invalid" objects

Key insight: Parsing subsumes validation. When you parse, you don't need to
validate separately—the validation is a natural side effect of construction.

### Shared Utilities

#### 5. Shared Utilities Over Hand-Rolled Helpers

Centralize invariants in shared code.

- Common patterns → `src/sattlint/core/` or the external `sattline-parser` package
- Don't replicate logic across analyzers
- When in doubt, refactor to shared utility

### Complexity

#### 16. Namespaces and File Structure

Filesystem is the agent's primary interface.

- Treat directory structure as an interface
- Name files descriptively: `billing/compute.py` over `utils/helpers.py`
- Prefer many small well-scoped files
- Small files reduce truncation risk in context loading

#### 17. Complexity Budget

- Max file size: 500 lines preferred, 800 hard cap
- Max function size: 50 lines preferred
- Max cyclomatic complexity thresholds
- Refactor before extending oversized modules
- Large files trigger decomposition PRs

### Typing

#### 14. End-to-End Static Types

Eliminate illegal states through typing.

- Every data layer has typed representation (AST, config, DB)
- OpenAPI contracts for external APIs
- Types shrink the search space of possible actions

#### 26. Objects Over Dicts/Tuples

Typed objects (dataclasses/classes) over ad-hoc dicts/tuples for data shapes.

- Named attribute access, never positional/numeric indexing (`item.value`, never `item[0]`)
- Multi-value returns are typed result objects, not tuples
- No "stringly-typed" dicts with magic keys (extends #4)
- Invalid states are unrepresentable by construction (see #4)

#### 27. Strict Typing by Default

Prefer the strictest sound typing the codebase supports.

- Touched files stay Pyright strict-clean
- Eliminate avoidable `Any`; `Any` is a documented, justified exception, not a default
- Typed boundaries over loose `dict[str, object]` plumbing

### Development Workflow

#### 13. Fast Ephemeral Dev Environments

Agent workflow spawns many processes. Make it cheap.

- One command creates fresh environment
- Worktree-per-feature when working with agents
- Ports, caches, DBs must be configurable or conflict-free

### Testing

#### 6. Case-Insensitive Identifiers Everywhere

SattLine identifiers are case-insensitive.

- Compare with `.casefold()` always
- Tests must cover mixed-case scenarios
- No silent case-sensitive shortcuts

#### 9. Tests Are Contracts

Tests document expected behavior; failures are spec violations.

- New feature → new test (same PR)
- Changing behavior → update tests (same PR)
- No disabling tests to make suite pass

#### 15. Tests Are Executable Proof (Refined)

100% coverage is a phase change.

- 100% line coverage target
- Mutation testing for critical paths
- Behavior-focused tests over superficial execution
- Coverage is necessary, not sufficient
- At 95% you're making decisions about "important enough"
- At 100% there's no ambiguity—if a line isn't covered, you just added it
- Coverage report becomes the todo list
- Tests force the agent to demonstrate behavior, not just "seem right"

### Change Isolation

#### 18. Local Change Radius

AI can unintentionally create broad regressions.

- PRs should minimize touched files
- Refactors separate from behavior changes
- Mechanical changes isolated
- Broad rewrites require explicit justification
- Agents should prefer smallest viable delta

### AI Optimization

#### 3. Progressive Disclosure

Agents start with small, stable entry point (`AGENTS.md`), follow pointers to depth.

- `AGENTS.md` -> `ARCHITECTURE.md` -> domain-specific docs
- Subsystem instructions in `.github/instructions/*.md`
- Never dump 1000-line manual into context

#### 19. Deterministic Style

- One formatter only
- One import sorter
- One type checker
- One test framework
- No style debates in PRs
- Generated code must be reproducible

#### 20. Minimize Cognitive Surface Area

- Prefer explicit APIs over implicit conventions
- Avoid deep inheritance
- Avoid metaprogramming unless essential
- Avoid "magic" registries without clear contracts
- Every subsystem should have:
  - clear entrypoint
  - clear invariants
  - bounded context

#### 21. Observable by Default

- Structured logs
- Reproducible failures
- Debug artifacts
- Explainable analyzer outputs
- Every major decision path traceable

#### 22. Dependency Skepticism

- Prefer stdlib first
- New dependency requires explicit justification
- Every dependency adds:
  - maintenance burden
  - security risk
  - context complexity
- Remove unused dependencies aggressively

#### 23. One Path Forward

- Deprecated paths must have removal timelines
- No parallel architectures without sunset plan
- Temporary compatibility layers documented
- Dead code removal prioritized

#### 29. Typed Dispatch Over Reflection

Typed callables over `getattr`/attribute-name strings for dispatch.

- Analyzer execution and command routing use statically typed callables
- No runtime reflection for dispatch when a typed callable works
- Avoid "magic" registries without clear contracts (see #20)

### Quality

#### 25. Root Cause Before Remedy

- Symptom fixes incomplete without cause analysis
- Solve bug classes, not individual bugs
- Shared solutions preferred over local patches
- Repeated issue classes trigger architectural review
- Every fix must reduce future issue probability

#### 28. Right Solution, Not Safe Solution

Do the correct, root-cause fix even when a compatibility shim lands faster.

- "Safe" workarounds that preserve the wrong shape are deferred debt
- No new compatibility seam without a removal timeline (see #23)
- Delete indirection rather than relocate it
- Change callers rather than preserving obsolete internal APIs

### Agent Guardrails

#### 24. Agent Guardrails

- No speculative refactors without evidence
- No deleting unfamiliar code without replacement validation
- No broad renames without dependency analysis
- No TODO placeholders in merged code
- Uncertainty must be surfaced explicitly

---

## Deferred Work

Tracking items the team decided to defer. Each entry records the decision, the
reason, and any pointers to the affected surface so it can be picked up later.

### Remove the `contract-mismatch` detection kind

**Status:** deferred by user request.

**Decision (2026-09-08):** SattLint's `CONTRACT_MISMATCH` (`contract_mismatch`)
detector should be **removed**, because it duplicates / shadows SattLine's own
mismatch detection. Keep `STRING_MAPPING_MISMATCH` (SattLine does **not** detect
string mapping mismatches, so that one stays).

**Scope considered** — `IssueKind.CONTRACT_MISMATCH` is referenced from:
- `src/sattlint/reporting/variables_report.py`
- `src/sattlint/models/_variable_issues.py`
- `src/sattlint/analyzers/_sattline_semantic_rules_data.py`
- `src/sattlint/analyzers/variable_analyses.py`
- `src/sattlint/analyzers/_sattline_semantic_issue_mapping.py`
- `src/sattlint/analyzers/variables/_variables_contracts.py`
- `src/sattlint/analyzers/variables/_variables_execution.py`
- `src/sattlint/analyzers/variables/__init__.py`
- `src/sattlint/analyzers/shared/_validators.py`
- `src/sattlint/analyzers/interface_contracts.py`

**Open questions before implementing:**
- Confirm whether `CONTRACT_MISMATCH` overlaps SattLine fully or only in the
  array/dynamic-array and validator emission paths.
- Whether `interface-contracts` should keep `UNKNOWN_PARAMETER_TARGET` and
  `REQUIRED_PARAMETER_CONNECTION`.

Also related fixture note: `ValveMissing` omitting `CmdClose` triggered both
SattLine ("parameter CmdClose not connected") and the SattLint
`REQUIRED_PARAMETER_CONNECTION` finding — another possible overlap to revisit.

### `scan_cycle.resource_usage` triple-reporting dedup

**Status:** deferred by user request (earlier session).

Do **not** dedup the triple-reporting of `scan_cycle.resource_usage` for now.
Revisit if it becomes a correctness issue.

### Completed: Remove the `sorting.loop_output_refactor` analyzer (2026-09-08)

**Status:** done. SattLine already detects the combinatorial/logic loop, so
SattLint should not re-report it. Removed across the full surface (module,
registry wiring, rule profiles, tests, corpus manifests, fixtures). Gates: full
suite 1316 passed, ruff + format clean, pyright 0 errors.
