# Deferred Work

Tracking items the team decided to defer. Each entry records the decision, the
reason, and any pointers to the affected surface so it can be picked up later.
Resolved items are listed under "Completed" at the bottom.

## Remove the `contract-mismatch` detection kind

**Status:** deferred by user request.

**Decision (2026-09-08):** SattLint's `CONTRACT_MISMATCH` (`contract_mismatch`)
detector should be **removed**, because it duplicates / shadows SattLine's own
mismatch detection. Keep `STRING_MAPPING_MISMATCH` (SattLine does **not** detect
string mapping mismatches, so that one stays).

**Scope considered** — `IssueKind.CONTRACT_MISMATCH` is referenced from:
- `src/sattlint/reporting/variables_report.py` (section title, kind lists, accessor, formatter)
- `src/sattlint/models/_variable_issues.py` (kind enum + metadata)
- `src/sattlint/analyzers/_sattline_semantic_rules_data.py` (semantic rule entry)
- `src/sattlint/analyzers/variable_analyses.py` (`"18"` cross-module contract mismatches)
- `src/sattlint/analyzers/_sattline_semantic_issue_mapping.py` (issue→rule mapping)
- `src/sattlint/analyzers/variables/_variables_contracts.py` (dedup set, emit at `_append_array_contract_mismatch`)
- `src/sattlint/analyzers/variables/_variables_execution.py` (kind filter list)
- `src/sattlint/analyzers/variables/__init__.py` (selected-kind gate)
- `src/sattlint/analyzers/shared/_validators.py` (emits `CONTRACT_MISMATCH` in two places)
- `src/sattlint/analyzers/interface_contracts.py` (kind set, summary order, section title, formatter)

**Open questions before implementing:**
- Confirm whether `CONTRACT_MISMATCH` overlaps SattLine fully or only in the
  array/dynamic-array and validator emission paths — a gate for deciding which
  emission sites to remove.
- Whether `interface-contracts` should keep `UNKNOWN_PARAMETER_TARGET` and
  `REQUIRED_PARAMETER_CONNECTION` (also need to verify these do not duplicate
  SattLine errors, given the fixture work surfaced `"Submodule ... parameter
  X not connected"` from SattLine).

Also related fixture note: `ValveMissing` omitting `CmdClose` triggered both
SattLine ("parameter CmdClose not connected") and the SattLint
`REQUIRED_PARAMETER_CONNECTION` finding — another possible overlap to revisit.

## `scan_cycle.resource_usage` triple-reporting dedup

**Status:** deferred by user request (earlier session).

Do **not** dedup the triple-reporting of `scan_cycle.resource_usage` for now.
Revisit if it becomes a correctness issue.

## Completed

### Remove the `sorting.loop_output_refactor` analyzer (2026-09-08)

**Status:** done. Same principle as the deferred contract-mismatch item —
SattLine already detects the combinatorial/logic loop, so SattLint should not
re-report it.

Removed across the full surface:
- `src/sattlint/analyzers/loop_output_refactor.py` (module deleted)
- Registry wiring: `registry/__init__.py` (import, `DEFAULT_CLI_ANALYZER_KEYS`,
  monkeypatch surface, `__all__`), `_registry_spec_templates.py`,
  `_registry_delivery_data.py`
- `src/sattlint/analyzers/rule_profiles.py` (the `sorting.loop_output_refactor`
  `SemanticRule`)
- Tests: `tests/analyzers/test_loop_output_refactor.py` (deleted), the two
  functions in `tests/analyzers/variables/test_adjacent_analyzers.py`,
  `tests/helpers/analyzers_variables_support.py` imports,
  `tests/analyzers/suites/test_versiondrift_registry.py` (monkeypatch + expected
  CLI key set)
- Corpus manifests: `analyzer-loop-output-refactor.json` and
  `analyzer-loop-output-refactor-clean.json` (deleted);
  `semantic-data-dependency.json` no longer expects `semantic.loop-output-refactor`
- Fixture: `Refactor` / `RefactorFeedback` equation blocks (and the now-unused
  `A`/`B` locals) removed from `EveryIssueMain.s`

Gates: full suite 1316 passed, ruff + format clean, pyright 0 errors.
