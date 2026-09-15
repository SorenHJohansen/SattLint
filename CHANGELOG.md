# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses calendar versioning (`vYYYY.M.number`) to match
`sattline-parser`.

## [Unreleased]

### Added

- Change Review: a TUI-only semantic diff and impact analysis between the
  official and draft versions of a configured project, producing a compact
  JSON + Markdown review artifact. Triggered from the Analyze view via the
  `Generate Change Review` button; output directory configured through the
  App Settings `review.output_dir` setting.
- Dataflow `conflicting_constants` finding: the same variable is assigned two
  different constant values on one path with a read in between (path-sensitive,
  so branch-exclusive constants do not fire). Replaces the removed
  `loop-stability` conflicting-setpoint analyzer.
- Cyclomatic-complexity equation-block finding (`equation.cyclomatic_complexity`)
  that flags equation blocks exceeding the configured threshold.
- Configurable engineering-spec prefixes under `analysis.spec_compliance`
  (`step_prefix`, `transition_prefix`, `sequence_prefix`, `equation_prefix`),
  with opt-in sequence-name and equation-block-name prefix checks.
- PictureDisplay above-base finding (`picture_display_paths.above_base`) for
  paths that escape above the base picture of the declaring module.
- Configurable analyzer thresholds and token sets under `analysis`:
  `cyclomatic_module_threshold`, `cyclomatic_step_threshold`,
  `cyclomatic_equation_block_threshold`, `fan_in_out_threshold`, and
  `unsafe_default_tokens`.

### Changed

- Analyzer descriptions rewritten for plain-English clarity and concrete
  examples across the whole catalog (variables, datatype-fields,
  picture-display-paths, mms-interface, icf, sfc, comment-code,
  spec-compliance, alarm-integrity, cyclomatic-complexity, same-cycle,
  dataflow, version-drift), with the version-drift and MMS datatype-mismatch
  semantic rules reframed to match.
- Analyzer execution no longer has a dependency graph: `AnalyzerSpec.requires`,
  the registry validation/order helpers, the dispatcher requirement-expansion
  helpers, and `plugin.requires` are gone. Each analyzer is self-contained and
  selection is exact — the analyzers that run are exactly the selected ones.
- Analyzers now declare a `scope` (`per-target` or `per-run`); `icf` is
  `per-run` and runs exactly once per session, and the checks runner splits the
  batch by scope instead of branching on the ICF key.

### Removed

- The cross-analyzer `derived_reports` memoization compartment
  (`ReportsByKey`) and `run_registry_analyzer(use_shared_artifacts=...)`, along
  with the now-dead semantic reuse counters. The opportunistic per-target
  foundation / collected-views cache remains.
- The `loop-stability` analyzer (conflicting-setpoint findings): superseded by
  the dataflow `conflicting-constants` finding, its semantic rule
  (`semantic.loop-conflicting-setpoint`) is hard-deleted.
- Variables findings that duplicated the parameter-mapping contract layer:
  UI/display-only variables, naming-to-behavior role mismatches, name
  collisions, and required-but-unconnected parameters (display-only variables
  and collisions now surface through the remaining UNUSED / READ_ONLY_NON_CONST
  / parameter-mapping findings).
- The orphaned `layout_overlap` label and the unused `symbolic_lite.py`
  symbolic-execution engine together with its registry delivery template.
- The `numeric-constraints` analyzer (limit-violation findings) and the
  `parameter-drift` analyzer, together with their registry spec/delivery
  templates, semantic rules, corpus manifests, and fixtures.
- The display-only metadata layer on analyzer findings: `severity`,
  `confidence`, `category`, and `applies_to` are gone from `Issue`,
  `AnalysisFinding`, `SemanticRule`, and the rule-metadata catalog. Findings
  are now identified by `rule_id`, `explanation`, and `suggestion` only, and
  the `SimpleReport` / SattLine semantics summaries no longer print a
  severity/confidence column. The per-analyzer `supports_live_diagnostics`
  spec flag and the library-target `severity="info"` branch in
  picture-display-paths were removed with it.
- The standalone `shadowing` analyzer: the finding now folds into the
  `variables` analyzer (`IssueKind.SHADOWING`, reported by default).
- The standalone `unsafe-defaults` analyzer: the unsafe-boolean-default
  finding now folds into the `variables` analyzer as a lifecycle kind
  (`unsafe_boolean_default`, reported by default).
- The standalone `signal-lifecycle` and `data-dependency` analyzers: their
  read-before-write and initialization-order findings merge into one
  `variables` lifecycle finding (`read_before_write`, reported by default)
  with a single exclusion policy (init value / module parameters /
  same-module declaration). The old `semantic.signal-lifecycle-*` and
  `semantic.data-dependency-*` rule ids are hard-deleted; the merged rule is
  `semantic.read-before-write`.
- The SFC transition always-true/always-false findings: folded into dataflow's
  `condition_always_true` / `condition_always_false` (dataflow already
  evaluates every transition guard); the SFC guard-truth engine is gone and
  `semantic.transition-always-*` ids are hard-deleted.
- The parallel write-race finding moved from `sfc` to `same-cycle`, sharing
  the existing parallel-branch hazard collection; `sfc` no longer runs a
  second SFC-aware variables traversal for it.
- The non-state multi-site finding moved from `same-cycle` to `dataflow` as
  `dataflow.non_state_multi_site`; the old `same_cycle_non_state_multi_site_hazard`
  kind and `semantic.same-cycle-non-state-multi-site` id are hard-deleted
  (new rule id `semantic.non-state-multi-site`).

## [2026.9.2] - 2026-09-10

### Fixed

- The released wheel was missing `sattlint/ui/app_textual.tcss`, so a bare
  `sattlint` invocation (interactive Textual shell) crashed with
  `FileNotFoundError`. The UI stylesheet is now declared as package data so it
  ships in the wheel.
- Added a clean-wheel smoke check (`import sattlint.ui.app_textual`) to the
  Linux, Windows, and publish gates so missing package data fails CI instead of
  breaking installs after release.

## [2026.9.1] - 2026-09-09

### Added

- Strict single-file syntax validation via the `syntax-check` CLI command.
- Configurable heuristic static analysis (`analyze`) over `.slproj` project files.
- `.slproj` project scaffolding via `sattlint init`, explicit `--project PATH`,
  and auto-discovery from the current working directory.
- ICF validation and graphics-rule analysis.
- Textual interactive UI for guided setup, analysis, and tools workflows.
- Config validation (`validate-config`) and cache pruning (`cache-prune`).
- Single-source package version export via `sattlint.__version__`.
- CLI `--version` support.
- Release and security repository metadata.

## [0.1.1] - 2026-04-23

### Added

- Static analysis and parser validation for SattLine projects.
- Non-interactive `syntax-check` CLI command for strict single-file validation.
- Analysis pipeline entry points.

### Notes

- This entry establishes the changelog baseline for future tagged releases.

[2026.9.2]: https://github.com/SorenHJohansen/SattLint/releases/tag/v2026.9.2
[2026.9.1]: https://github.com/SorenHJohansen/SattLint/releases/tag/v2026.9.1
