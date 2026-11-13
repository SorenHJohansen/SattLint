# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses calendar versioning (`vYYYY.M.number`) to match
`sattline-parser`.

## [Unreleased]

## [2026.11.4] - 2026-11-12

SattLint 2026.11.4 pairs with `sattline-parser==2026.11.4` and completes the
parser AST migration.

### Fixed

- A target that fails to load no longer produces a successful headless run.
  Diagnostics are captured with the run output, the command exits with a
  target-loading error, and the partial run is not saved to run history. JSON
  and NDJSON commands keep stderr machine-readable, and the interactive shell
  reports that the run was incomplete.
- Report cache keys include the analyzer settings under `analysis`, so changing
  a threshold or naming option cannot reuse a report computed with other
  settings.
- Change Review reports declaration initializer and modifier changes, root
  module parameter declarations, and sequence fork target or break changes.
- Function calls inside expressions apply their declared output writes, so a
  later condition does not treat the previous value as still current. Shared
  dependency-usage and scan-order collection use the same argument directions.
- Graphics bindings contribute their references and call signatures to the
  semantic index again. Quoted symbols in tails no longer count as variable
  reads or writes.
- Opening a project preserves the user's saved run-history, output-retention,
  and Change Review settings. Root module parameters now resolve, are indexed
  as parameter definitions, and participate in variable analysis.
- Run history reports a failed save instead of returning an identifier for a
  run that was not written, and old runs are pruned only after a successful
  save.
- Parser validation diagnostics no longer depend on the removed severity field.
  Every final diagnostic is an error, and diagnoses the parser marks as
  tentative become notices.
- Module definition code blocks are read from `equationblocks`, matching the
  parser model.
- Graphics companion records, bindings, and picture display correlations live on
  the project graph instead of on the parser's AST. Attachments resolve for the
  merged base picture the analyzers receive, and parser `var` bindings are
  normalized to `VarRef` at the graphics seam.
- Module type resolution reads library dependencies from the project graph.
- Source loading uses the parser's `load_source_text` and `source_text_for_parse`
  helpers, so byte-coded streams and compressed sources keep the parser's
  character coordinates instead of a SattLint-local decode pipeline.
- Comment placement is left to the parser grammar. The commented-out-code
  detector reads keyword facts from the parser constants instead of a local
  keyword list.

### Changed

- Parser access in shipped code goes through one module,
  `sattlint.parser_api`, so a parser release that moves internal modules cannot
  break `src/` imports. Tests may reach `sattline_parser` directly for surface
  contract coverage. The unused `sattlint.models.ast_model` compatibility
  wrapper is removed.
- Analyzer traversal reads the parser model through typed fields and the
  `walk` API. The shared variable and call-site collectors in
  `sattlint.core.ast_tools` are filters over that walk.
- Requires `sattline-parser` 2026.11.4, pinned exactly.
- Added reference-visibility tests over real parser output for text objects,
  pick buttons, header arguments, clipping tails, procedure calls, interactor
  bodies, and literal versus variable parameter mappings. The corpus manifests
  pass under 2026.11.4, and the differential against a 2026.11.3 worktree
  produced an identical finding set.
- Change Review now derives layout ignoring from parser field metadata instead
  of a global field-name list. Bound tails (`Enable_`, `Module_In_View`,
  coordinate tails, clipping tails) are semantic, spans and parser-marked
  layout fields are not, and comment streams stay a small SattLint policy
  exception. Assignment targets are collected with the parser `walk` API.
- Bumped the AST, project graph, foundation, and analysis report cache
  identities so cached graphs and reports from the previous parser release or
  analyzer settings are not reused.
- Call signatures and graphics validation messages now derive from the parser's
  `BuiltinFunction` and `GraphicsMessage` types instead of field-for-field
  copies. The four suppressed language diagnostics carry a written reason at
  the suppression site.

### Removed

- The reflective traversal layer: mapping, sequence, dataclass, `children`, and
  `__dict__` guessing in the analyzer path. A guard test rejects those patterns
  in `src/sattlint/analyzers`.
- The parser compatibility tests that exercised the retained parse tree. The
  exact-pin checks now live in the parser surface contract test.
- Tests that fed hand-built legacy tuple, dictionary, and
  `SimpleNamespace(children=...)` shapes to analyzer traversal helpers.
- The duplicate comment-placement pre-scan; the parser grammar now owns that
  check.
- The historical parser upgrade plan moved from the repository root to
  `docs/parser-upgrade-plan.md`.

## [2026.11.3] - 2026-11-05

### Fixed

- Restored installs against the published parser. The previous range
  `>=2026.11.3,<2027` accepted `sattline-parser` 2026.11.4, which changes the
  AST surface before the analyzer migration lands, so a fresh install failed at
  import. This release pins the parser to the supported version.

### Changed

- Upgraded `sattline-parser` to `2026.11.3` and pinned it exactly. The parser
  now checks internal builtin registrations, carries the full
  configuration-defined record field tables, resolves SFC element names
  program-wide, keeps base-picture module parameters, and defaults project
  loads to invoked validation scope. The pin moves only together with the
  analyzer migration.

## [2026.11.2] - 2026-11-02

### Added

- Headless CLI for automation and agents: `sattlint project show`,
  `sattlint analyzers list`, `sattlint analyze --format json|ndjson|text`,
  `sattlint findings`, and `sattlint show <finding-id>`. Commands are
  non-interactive, keep data on stdout and diagnostics on stderr, emit a
  versioned JSON envelope, and use stable content-derived finding IDs.
  `analyze` supports `--project`, `--analyzer`, `--target`, `--module`,
  `--no-cache`, `--no-save`, `--fail-on {any,none}`, `--output`, and
  `--quiet`; `findings` supports run lookup (`latest` or an ID/prefix),
  analyzer/target/module/kind/rule filters, module-prefix grouping, and
  `--limit`. Text and Markdown output use human-readable finding labels;
  machine IDs stay in JSON and NDJSON. Pure syntax and project validation
  remain owned by the external `sattline-parser` tool.
- The results view can group findings by analyzer or by module. The module
  view collapses single-child module chains into one node, so long paths use
  less vertical space.
- `analyze` reports the id of the saved run in its JSON payload, and
  `--no-save` skips run-history persistence for one-off runs.

### Changed

- Field-level variable analysis aggregates reads and writes across every
  instance of a datatype before reporting, so partial-field findings describe
  the analyzed target instead of one instance. Whole-record access stays
  directional.
- Module parameters are treated as contract values: unused-assignment
  findings apply to locals only, including module-type parameters.
- SFC dataflow discards pending writes and constant traces between step
  phases (enter, active, exit) while transition conditions still see the
  latest values. Literal `TRUE`/`FALSE` conditions no longer produce
  always-true or always-false findings.
- Frame modules inherit their parent's parameter keys, so inherited
  parameters are treated as contract values rather than uninitialized locals.
- Change Review builds its semantic model from root-origin modules and skips
  dependency internals.
- Commented-code detection ignores abbreviated control-structure templates
  such as `IF Cond THEN ... ENDIF` instead of skipping every comment that
  contains an ellipsis.
- Min/Max bound detection also recognizes the marker before a trailing path
  segment, for example `_Min_Mn.Value`.
- PictureDisplay checks treat an existing `.emf`/`.wmf` asset as present and
  report that content inspection is not implemented instead of unresolved.
- `.slproj` analysis overrides survive merging with the default configuration.

### Fixed

- Field read-only and never-read findings were duplicated or reported per
  instance instead of per analyzed datatype.
- Unused-assignment findings were reported for module parameters.
- Literal conditions produced always-true and always-false dataflow findings.
- Dead-overwrite and conflicting-constant findings crossed SFC step phases.
- Frame-module parameters were classified as uninitialized locals.
- Existing `.emf`/`.wmf` PictureDisplay assets were reported as unresolved.
- Template ellipses suppressed commented-code findings for real code.
- `.slproj` analysis settings were dropped when the project configuration was
  merged with defaults.

## [2026.11.1] - 2026-11-01

### Changed

- Validation is now single-source in `sattline-parser`. `sattlint syntax-check`
  and the analyzer type helpers consume `sattline_parser.validation`; SattLint
  keeps only policy and error shapes. The duplicated rule modules, builtin
  signature tables, builtin datatype tables, and datecode comparison are
  removed, and the parser validation suite is the rule oracle. Builtin call
  checks understand optional trailing async/debug parameters and object handle
  types, so existing projects do not gain false arity or type findings.
- Project loading consumes the parser project layer directly: per-program
  diagnostics, library and resolved-base provenance, datecode conflicts, and
  cycle paths come from the loaded project. Definition datecode conflicts are
  now compared against the full loaded registry instead of first-wins maps, so
  real projects can surface conflicts that were previously missed.
- Graphics companions consume the parser's `GraphicsModel`. SattLint keeps the
  workspace asset checks, code correlation, and notice wording, and the second
  binding and record scanner is deleted.
- Parser-core compatibility wrappers are gone. Grammar constants and the
  transformer are imported from `sattline_parser` directly.
- The parser adapter no longer reads a refresh mode. AST-only refreshes pass
  `LoadValidation.NONE` to the parser and skip the program view explicitly,
  instead of branching inside the adapter.
- Upgraded `sattline-parser` to `>=2026.11.2,<2027`.
- Project loading now uses the parser's invoked validation scope. The selected
  target is validated in full; dependency libraries are limited to the module
  types the target invokes, transitively, so unused library internals no longer
  add findings.
- Validation performance improved substantially through the parser release:
  the type graph is reused per program instead of per expression, and a warm
  cache load no longer unpickles every AST just to prune it.
- The `sattline-parser` 2026.10.1 API migration is included:
  `read_text_cp1252` (strict Windows-1252, no encoding fallback)
  replaces `read_text_with_fallback`; `SEQFORK`/`SEQBREAK` are now a suffix on
  `SFCStep.fork`/`SFCTransition.fork` (`SFCBreak` is gone); optional
  `SFCSubsequence.name` values are handled. Analyzer, validation, change-review,
  test, and corpus-fixture call sites were updated to the new model.
- Sequence validation treats a fork suffix as terminating the linear path, so
  nodes after a `SEQFORK` are left to the reachability analyzer instead of being
  reported as consecutive steps or transitions.

- Final parser project-layer milestone: the `SattLineProjectLoader` shell is
  fully retired. `project/loader.py`, `project/loader_base.py`, and the final
  loader seams are deleted; all loads now route through
  `loader_config.build_parser_binding` (returns a `ParserProjectBinding`) into
  `parser_adapter.load_parser_project`/`convert_project_into_graph`. `loading.py`
  owns the `_load_parser_graph`/`_visit_target_into_graph` seams and reads
  dependency names via `parser_adapter.find_dependency_path`/`read_dependency_names`;
  reverse-consumer resolution passes injected callables into
  `loading_support._include_reverse_library_consumers`. `engine.py` re-exports
  `ParserProjectBinding` and the parser-adapter errors.
- Phase 6 of the parser project layer: retired the old recursive-loader
  machinery from SattLint. `loader_lookup.py` is deleted; `CacheManager`,
  `cache/classes.py`, and `cache/__init__.py` no longer track the parser-owned
  `FileLookupCache`/`FileASTCache` (the parser owns those behind its own
  `cache_dir=None` contract, keeping the SattLint adapter hermetic); the
  `use_file_ast_cache` seam, `ast_cache_counts`, the `ast_cache_save` refresh
  stage, the `contextual_lookup`/`SattLineProjectLoaderDependencies` plumbing,
  and the legacy `**kwargs` loader-factory path are all removed.
- Phase 7 docs and cleanup: `ARCHITECTURE.md`, `AGENTS_REFERENCE.md`,
  `PYTHON_API.md`, and the `README.md` project-files section describe the
  parser-adapted project loading (`loader_config.build_parser_binding` +
  `parser_adapter` → parser project layer → `ProjectGraph` reindex) and the
  parser-owned cache split.

### Added

- Phase 5 parser project layer: the SattLint project loader delegates all
  SattLine discovery, dependency resolution, and parsing to `sattline-parser`'s
  project layer through `sattlint.project.parser_adapter`, with
  `SattLineProjectLoader` in `sattlint.project.loader` reduced to a thin
  temporary compatibility shell. Per-program semantic validation, graphics
  companion handling, dependency version-conflict detection, library naming,
  and indexing behavior are preserved; the corpus, app-loader, analyzer, and
  new adapter test suites all pass.

### Removed

- The duplicated invalid corpus fixtures and their unreferenced manifests are
  removed. Language-validation fixtures live in `sattline-parser`; the SattLint
  corpus keeps analyzer and semantic fixtures only.
- The `sattlint.grammar` constants shim, the `sattlint.transformer` package, the
  `sattlint.validation` facade, the dead external-datatype validation flags, and
  the temporary parity snapshot scripts are removed.

## [2026.9.3] - 2026-09-16

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
  picture-display-paths, icf, sfc, comment-code,
  spec-compliance, alarm-integrity, cyclomatic-complexity, same-cycle,
  dataflow, version-drift), with the version-drift and datatype-mismatch
  semantic rules reframed to match.
- Analyzer execution no longer has a dependency graph: `AnalyzerSpec.requires`,
  the registry validation/order helpers, the dispatcher requirement-expansion
  helpers, and `plugin.requires` are gone. Each analyzer is self-contained and
  selection is exact — the analyzers that run are exactly the selected ones.
- Analyzers now declare a `scope` (`per-target` or `per-run`); `icf` is
  `per-run` and runs exactly once per session, and the checks runner splits the
  batch by scope instead of branching on the ICF key.

### Removed

- All CLI subcommands and flags: `sattlint` is now a single no-argument TUI
  launch. `analyze`, `cache-prune`, `syntax-check`, `init`, `--project`,
  `--config`, `--no-cache`, `--quiet`, `--debug`, `--version`, `--ui`, and the
  rest are gone; every capability is reachable from the Textual UI.
- The cross-analyzer `derived_reports` memoization compartment
  (`ReportsByKey`) and `run_registry_analyzer(use_shared_artifacts=...)`, along
  with the now-dead semantic reuse counters. The opportunistic per-target
  foundation / collected-views cache remains.
- The `loop-stability` analyzer (conflicting-setpoint findings): superseded by
  the dataflow `conflicting-constants` finding, its semantic rule
  (`semantic.loop-conflicting-setpoint`) is hard-deleted.
- The `mms-interface` analyzer (duplicate-tag / datatype-mismatch / dead-tag
  findings) along with its registry spec/delivery templates, `mms` package,
  `mms_report`, corpus manifests, and fixtures. Its MMS datatype-mismatch and
  version-drift semantic-rule reframes followed.
- The `depends_on_analyzers` delivery metadata field (both template and
  `AnalyzerDeliveryMetadata`); it had no consumers.
- `picture-display-paths` no longer suppresses `missing_program` findings for
  library targets: `Program:`-coupling references in libraries are always
  reported (`picture_display_paths.unresolved`). `missing_parent` (above-base)
  stays suppressed for library targets.
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

[2026.11.4]: https://github.com/SorenHJohansen/SattLint/releases/tag/v2026.11.4
[2026.9.3]: https://github.com/SorenHJohansen/SattLint/releases/tag/v2026.9.3
[2026.9.2]: https://github.com/SorenHJohansen/SattLint/releases/tag/v2026.9.2
[2026.9.1]: https://github.com/SorenHJohansen/SattLint/releases/tag/v2026.9.1
