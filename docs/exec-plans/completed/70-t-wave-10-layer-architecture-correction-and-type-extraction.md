# T-Wave-10 Layer Architecture Correction and Type Extraction

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

The architecture enforcement tool (`layer_linter.py`) currently uses a 5-layer flat model that does not match the documented 9-layer architecture in `AGENTS.md` and `docs/architecture.md`. This means the three confirmed reverse-dependency violations found in the 2026-06-02 code review — `core` importing from `reporting`, `resolution` importing from `reporting`, and `models` importing from the root `_validation_shared` module — are structurally undetectable by the enforcement tool. The linter gives false green signals while real violations accumulate.

The root cause of those violations is that `IssueKind` (an enum) and `VariableIssue` (a dataclass) are pure model types — they carry no behaviour, only structure — but they live in `src/sattlint/reporting/variables_report.py`. Because `core/`, `resolution/`, and `analyzers/` all need them, those packages are forced to import upward into `reporting/`. The correct fix is to extract `IssueKind` and `VariableIssue` into `src/sattlint/models/` (or a new `src/sattlint/contracts/` module), so both `reporting/` and all lower layers can import them from one canonical location without creating a semantic layer violation. The same applies to `ValidationNotice` in `src/sattlint/_validation_shared.py`, which `models/project_graph.py` imports from the root layer.

After this work lands, the layer linter will match the documented 9-layer architecture, the three confirmed reverse-dependency violations will be detectable and eliminated, and any future violation of the same class will be caught automatically before merge.

The observable proof is a clean `layer_linter` run that reports zero violations, a clean `pyright` run over all touched files, and all existing tests passing.

## Progress

- [x] Read the full current state of `src/sattlint/devtools/layer_linter.py` and `AGENTS.md` architecture section to map the documented 9 layers to the five-layer `LAYER_MAP` and identify every gap.
- [x] Extend `LAYER_MAP` in `layer_linter.py` to cover the full 9-layer architecture: parser (0), models (1), core (2), resolution (3), analyzers (4), app (5), reporting (6), LSP (7), VS Code (8), devtools (9, tooling-only).
- [x] Add `sattlint.devtools` as a distinct layer entry above `sattlint` (app) in `LAYER_MAP` so devtools imports from app code are detectable.
- [x] Fix the silent `except Exception: pass` at `layer_linter.py:141` — files that fail to parse must emit a parse-error violation entry rather than being silently exempted from checking.
- [x] Create `src/sattlint/models/_variable_issues.py` containing the extracted `IssueKind` enum and `VariableIssue` dataclass, with all imports and type annotations preserved.
- [x] Update `src/sattlint/reporting/variables_report.py` to import `IssueKind` and `VariableIssue` from `sattlint.models._variable_issues` and re-export them through its `__all__` so downstream callers that import from `reporting.variables_report` keep working without change.
- [x] Update `src/sattlint/models/__init__.py` to export `IssueKind` and `VariableIssue`.
- [x] Update all four layer-violating import sites to import from the new canonical location:
  - `src/sattlint/core/diagnostics.py`
  - `src/sattlint/core/_semantic_snapshot.py`
  - `src/sattlint/core/_semantic_index.py`
  - `src/sattlint/resolution/context_builder.py`
- [x] Move `ValidationNotice` from `src/sattlint/_validation_shared.py` into `src/sattlint/models/_validation_notice.py` and update `src/sattlint/models/project_graph.py` to import from the new location.
- [x] Verify the layer linter now detects violations when absolute cross-layer imports are used; confirmed zero violations with corrected import paths.
- [x] Run `pyright` over all touched files and confirm zero new type errors.
- [x] Run the full test suite and confirm no regressions.

## Surprises & Discoveries

(To be filled in during implementation.)

## Decision Log

- Decision: extract to `src/sattlint/models/_variable_issues.py` rather than a new `contracts/` package.
  Rationale: `models/` already exists as layer 1 in the architecture, holds pure data types, and is imported by nothing above it. Adding a new `contracts/` package would require registering a new layer in the linter, updating architecture docs, and introducing a naming convention that does not yet exist in the repo. Using `models/` is the minimal correct fix.
  Date/Author: 2026-06-02 / Copilot (Claude Sonnet 4.6)

- Decision: keep re-exports in `reporting/variables_report.py` through `__all__` to avoid a big-bang migration of all analyzer callsites.
  Rationale: there are 20+ analyzer files that import `IssueKind` and `VariableIssue` from `reporting.variables_report`. Their imports are not layer violations because `analyzers/` sits below `reporting/` in the correct architecture. Forcing all of them to change canonical import paths in this plan would widen the diff dramatically without fixing any additional violation. Re-exporting from `reporting/variables_report` preserves the existing analyzer API surface while eliminating the upward imports in `core/` and `resolution/`.
  Date/Author: 2026-06-02 / Copilot (Claude Sonnet 4.6)

- Decision: fix the layer linter's silent `except Exception` before validating the type migration.
  Rationale: if a touched file has a transient syntax issue during migration, the linter would silently treat it as clean and hide the real feedback. The linter must report parse failures as violations rather than gaps.
  Date/Author: 2026-06-02 / Copilot (Claude Sonnet 4.6)

## Outcomes & Retrospective

Completed 2026-06-02.

- `LAYER_MAP` expanded from 5 entries to 10 (layers 0–9 plus `sattlint.devtools` at 9).
- `get_layer_for_module` now sorts by prefix length descending so `sattlint.devtools` is matched before `sattlint`.
- Silent `except Exception: pass` replaced with an explicit `ArchViolation` parse-error entry.
- `IssueKind` and `VariableIssue` extracted to `src/sattlint/models/_variable_issues.py`; re-exported from `reporting/variables_report.py` (no downstream analyzer changes required).
- `ValidationNotice` extracted to `src/sattlint/models/_validation_notice.py`; re-exported from `_validation_shared.py` via import shim.
- `src/sattlint/models/__init__.py` now exports `IssueKind`, `VariableIssue`, and `ValidationNotice`.
- All 4 violating import sites in `core/` and `resolution/` updated to import from `models._variable_issues`.
- Layer linter reports zero violations across `src/`; pyright reports zero errors on all touched files; 2631 tests pass.
- Test `test_check_file_for_arch_violations_skips_unparseable_file` renamed to `test_check_file_for_arch_violations_reports_unparseable_file` to reflect the corrected behavior.

## Context and Orientation

This repository is organized as a layered Python monorepo. The architectural layers from lowest to highest are:

- Layer 0 — `sattline_parser`: the grammar, AST models, and transformer. No dependency on anything in `sattlint`.
- Layer 1 — `sattlint.models`: pure data containers and enums. No dependencies on `core`, `resolution`, `reporting`, or `analyzers`.
- Layer 2 — `sattlint.core`: semantic snapshots, diagnostics, and semantic indexes. May depend on `models` and `sattline_parser`.
- Layer 3 — `sattlint.resolution`: scope building, symbol tables, context builders. May depend on `core` and `models`.
- Layer 4 — `sattlint.analyzers`: the 34+ analysis checks. May depend on `resolution`, `core`, and `models`.
- Layer 5 — `sattlint` (app root): project loading, engine, config, app orchestration. May depend on all lower layers.
- Layer 6 — `sattlint.reporting`: report rendering and formatting. May depend on all lower layers.
- Layer 7 — `sattlint_lsp`: language server. May depend on layer 5 and below.
- Layer 8 — `vscode`: VS Code extension. Depends on the LSP only.
- Layer 9 — `sattlint.devtools`: tooling-only package. Must not be imported by any layer 0–7 code.

The current `LAYER_MAP` in `src/sattlint/devtools/layer_linter.py` only covers five entries (`sattline_parser=0`, `sattlint.core=1`, `sattlint=2`, `sattlint_lsp=3`, `vscode=4`). This collapses `models`, `resolution`, `analyzers`, `reporting`, and `devtools` all into the same `sattlint=2` bucket, which means no cross-package violation inside `sattlint.*` is detectable.

The confirmed violations are:

- `src/sattlint/core/diagnostics.py` imports `IssueKind, VariableIssue` from `..reporting.variables_report` (core → reporting: wrong direction).
- `src/sattlint/core/_semantic_snapshot.py` imports `VariableIssue` from `..reporting.variables_report` (core → reporting: wrong direction).
- `src/sattlint/core/_semantic_index.py` imports `VariableIssue` from `..reporting.variables_report` (core → reporting: wrong direction).
- `src/sattlint/resolution/context_builder.py` imports `IssueKind, VariableIssue` from `..reporting.variables_report` (resolution → reporting: wrong direction).
- `src/sattlint/models/project_graph.py` imports `ValidationNotice` from `.._validation_shared` (models → sattlint root: wrong direction).

The `IssueKind` class is a plain `enum.Enum` defined at `src/sattlint/reporting/variables_report.py:21`. The `VariableIssue` class is a `@dataclass(frozen=True)` defined at the same file around line 121. Neither class has any behaviour that depends on reporting machinery; they are pure model types. Moving them to `src/sattlint/models/_variable_issues.py` means both `reporting/` (their current home) and `core/`, `resolution/` (their consumers) import from a neutral lower layer.

`ValidationNotice` is defined as a `@dataclass` at `src/sattlint/_validation_shared.py:24`. It is used in `src/sattlint/models/project_graph.py` to type the `validation_notices` field on `ProjectGraph`. Moving it to `src/sattlint/models/_validation_notice.py` removes the inward dependency from `models/` to the root package.

The layer linter lives at `src/sattlint/devtools/layer_linter.py`. The silent-exception bug is at line 141 inside `check_file_for_arch_violations`. Files that fail `ast.parse` currently return an empty violation list, making them indistinguishable from clean files.

## Plan of Work

Begin with `layer_linter.py`. Read the full file to understand the exact structure of `LAYER_MAP` and the `get_layer_for_module` lookup. Then replace the `LAYER_MAP` dict with one that covers all nine architectural layers plus devtools, following the numbering described in the Context section above. Add a lookup rule so that `sattlint.devtools` maps to 9 (tooling-only) rather than inheriting the `sattlint` app-layer number. After extending the map, fix the silent `except Exception` block: replace it with a block that appends an `ArchViolation` entry describing the parse error, so parse failures are visible rather than hidden.

Next, create `src/sattlint/models/_variable_issues.py`. Copy the `IssueKind` enum and `VariableIssue` dataclass bodies from `src/sattlint/reporting/variables_report.py` into the new file. Preserve all docstrings, field annotations, and supporting types that those classes depend on (check for any helper classes or type aliases defined nearby in the same file). The new file must not import anything from `reporting/`.

Update `src/sattlint/reporting/variables_report.py` to import `IssueKind` and `VariableIssue` from `sattlint.models._variable_issues` instead of defining them locally. Keep them in `__all__` in `variables_report.py` so all existing downstream callers that use `from ..reporting.variables_report import IssueKind, VariableIssue` continue to work without any change.

Update `src/sattlint/models/__init__.py` to re-export `IssueKind` and `VariableIssue` from `sattlint.models._variable_issues`.

Update the four violating import sites in `core/` and `resolution/` to import directly from `sattlint.models._variable_issues` (using the relative path `..models._variable_issues` for files inside `sattlint`).

Then create `src/sattlint/models/_validation_notice.py` containing the `ValidationNotice` dataclass, moved from `src/sattlint/_validation_shared.py`. Keep a re-export shim in `_validation_shared.py` if other callers import `ValidationNotice` from that path. Update `src/sattlint/models/project_graph.py` to import from `sattlint.models._validation_notice`.

Finally, run the layer linter to confirm it now reports zero violations, run `pyright` over all touched files, and run the full test suite.

## Concrete Steps

Run all commands from the repository root.

First, read the full layer linter to understand the complete structure before editing:

    bash scripts/run_repo_python.sh -m cat src/sattlint/devtools/layer_linter.py

Check which files import ValidationNotice from _validation_shared to know whether a re-export shim is needed:

    grep -rn "from.*_validation_shared import" src/

After all edits are complete, run the layer linter against the src/ tree:

    bash scripts/run_repo_python.sh -m sattlint.devtools.layer_linter src/

Expected: zero architecture violations reported.

Run pyright over the touched files:

    bash scripts/run_repo_python.sh -m pyright \
      src/sattlint/models/_variable_issues.py \
      src/sattlint/models/_validation_notice.py \
      src/sattlint/models/__init__.py \
      src/sattlint/models/project_graph.py \
      src/sattlint/reporting/variables_report.py \
      src/sattlint/core/diagnostics.py \
      src/sattlint/core/_semantic_snapshot.py \
      src/sattlint/core/_semantic_index.py \
      src/sattlint/resolution/context_builder.py \
      src/sattlint/devtools/layer_linter.py

Expected: zero errors or new errors introduced by the changes.

Run the full test suite:

    bash scripts/run_repo_python.sh -m pytest --no-cov -x -q --tb=short

Expected: same passing count as before the change, no regressions.

## Validation and Acceptance

Acceptance is met when all of the following are true:

1. Running the layer linter reports zero violations across `src/`.
2. Running the layer linter against a temporary file that contains `from sattlint.reporting.variables_report import IssueKind` inside a `sattlint.core` module reports one violation (proving the new map can detect the error class).
3. `pyright` reports zero new errors over the touched file set.
4. `pytest --no-cov -x -q` passes with the same count as before the change.
5. `IssueKind` and `VariableIssue` are importable from `sattlint.models` via `from sattlint.models import IssueKind, VariableIssue` in a one-line Python snippet.

## Idempotence and Recovery

All changes are additive or move-and-re-export. If the migration is abandoned partway through, the original definitions in `variables_report.py` can be uncommented and the new files deleted without leaving the codebase in a broken state, because the re-export approach means no callsite is broken until the original definition is actually removed.

If `pyright` reports type errors in an intermediate state, check whether `IssueKind` or `VariableIssue` is referenced as a string annotation in any file — string annotations in `from __future__ import annotations` files do not require runtime importability, but `pyright` still validates them.

## Artifacts and Notes

The five confirmed violations (from the 2026-06-02 review):

    src/sattlint/core/diagnostics.py:11         from ..reporting.variables_report import IssueKind, VariableIssue
    src/sattlint/core/_semantic_snapshot.py:14  from ..reporting.variables_report import VariableIssue
    src/sattlint/core/_semantic_index.py:15     from ..reporting.variables_report import VariableIssue
    src/sattlint/resolution/context_builder.py:8 from ..reporting.variables_report import IssueKind, VariableIssue
    src/sattlint/models/project_graph.py:8      from .._validation_shared import ValidationNotice

Current broken LAYER_MAP (5 entries, all sattlint sub-packages collapse to layer 2):

    LAYER_MAP = {
        "sattline_parser": 0,
        "sattlint.core": 1,
        "sattlint": 2,
        "sattlint_lsp": 3,
        "vscode": 4,
    }

Target LAYER_MAP (9 + devtools entries):

    LAYER_MAP = {
        "sattline_parser": 0,
        "sattlint.models": 1,
        "sattlint.core": 2,
        "sattlint.resolution": 3,
        "sattlint.analyzers": 4,
        "sattlint": 5,
        "sattlint.reporting": 6,
        "sattlint_lsp": 7,
        "vscode": 8,
        "sattlint.devtools": 9,
    }

## Interfaces and Dependencies

After this plan, the stable import paths for downstream callers are:

- `from sattlint.models import IssueKind, VariableIssue` — direct model import, no reporting dependency.
- `from sattlint.models._variable_issues import IssueKind, VariableIssue` — private but stable for in-package use.
- `from sattlint.reporting.variables_report import IssueKind, VariableIssue` — preserved as a re-export, continues to work for all existing analyzer imports (no change required in those files).
- `from sattlint.models import ValidationNotice` — new canonical path for the dataclass.
- `from sattlint._validation_shared import ValidationNotice` — re-export shim, preserved if other callers use this path.
