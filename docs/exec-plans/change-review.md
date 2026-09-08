# SattLint Change Review

> Status: Implemented (2026-09-08) — see `src/sattlint/change_review/`,
> `src/sattlint/application/change_review.py`, the Analyze-view
> `Generate Change Review` button, and the `review.output_dir` app setting.
> Depends on: existing `SemanticSnapshot` / `SemanticIndex` infrastructure
> Replaces: nothing (new capability, orthogonal to static analysis)

## Goal

Add a new SattLint capability that turns two versions of a SattLine project —
an **official** (baseline) version and a **draft** (modified) version — into a
single compact **Change Review** artifact that is equally useful to a human code
reviewer and to an external AI-assisted reviewer.

Given roughly 17 MB of official source and 17 MB of draft source, SattLint
should produce a self-contained review such as:

```
Change Review
  12 changed symbols
  34 impacted symbols
  70 KB relevant source
```

The Change Review is fundamentally a **semantic diff and impact analysis**
problem. It must be driven by SattLint's existing `SemanticSnapshot` /
`SemanticIndex` and dependency graph, not by grep/regex/line-based text diffing.
Text is only a presentation detail: original source text is preserved where a
comparison or context window is needed.

This feature is explicitly **not** part of static analysis:
no analyzers run, no findings are collected, and analyzer success/failure is
never a prerequisite for generation.

## Scope

Responsible for:

- comparing two versions of a project (semantic, not textual),
- identifying semantic changes (added/removed/modified symbols, changed
  statements/expressions/constants/variables/implementations/calls/parameters/
  connections/S88 relationships/state transitions/alarm-interlock logic as
  represented by the semantic model),
- determining impacted/relevant code from the semantic dependency graph,
- selecting the smallest useful source context,
- generating a canonical, presentation-independent `ChangeReview` model,
- serializing it to JSON and Markdown,
- writing the artifact(s) to a user-configured output location,
- exposing a single TUI action that triggers generation.

Out of scope:

- a CLI command for Change Review (TUI only),
- any static-analysis integration, analyzer execution, or diagnostic collection,
- an in-TUI review browser (beyond the generation action),
- a second independent semantic model (the `SemanticSnapshot` stays the source
  of truth).

## Context

### Existing architecture (verified)

- **Loader / project graph**: `SattLineProjectLoader` +
  `SattLineProjectLoaderConfig(program_dir, other_lib_dirs, abb_lib_dir, mode,
  debug)` in `src/sattlint/project/loader_config.py`. `mode` is a `CodeMode`
  (`official` | `draft`); official code files use `.x`, draft files use `.s`
  (`code_ext`/`deps_ext` in `src/sattlint/core/syntax.py`). Loading a target
  returns a `ProjectGraph` with `ast_by_name`, `root_origins`, moduletype and
  datatype defs, library dependencies, `source_files`, and failures.
- **Semantic snapshot**: `SemanticSnapshot` (frozen facade) in
  `src/sattlint/core/_semantic_snapshot.py` wraps a `SemanticIndex`
  (`src/sattlint/core/_semantic_index.py`):
  `symbol_table`, `type_graph`, `definitions` (`SymbolDefinition`: canonical
  path, kind, datatype, declaration module path, field path, source file/library,
  declaration span), `references_by_definition_key`
  (`DefinitionKey -> tuple[SymbolReference]`), `call_signatures`
  (`CallSignatureOccurrence`: name, call_kind, module_path, source file/library),
  `_accesses_by_definition_key` (read/write `AccessEvent`s),
  `_effect_flow_edges` (`DefinitionKey -> tuple[DefinitionKey, ...]` data-flow
  edges), `_effect_flow_display_names`.
- **Snapshot builders** in `src/sattlint/core/semantic.py`:
  `load_workspace_snapshot(entry_file, ...)`,
  `build_snapshot_from_loaded_project(base_picture, project_graph, entry_file,
  workspace_root, ...)`, and the app-layer
  `load_program_ast(cfg, program_name) -> (BasePicture, ProjectGraph)` in
  `src/sattlint/project/loading.py` /
  `src/sattlint/application/project.py`.
- **AST model** (external `sattline-parser`): `BasePicture` → `submodules`
  (`SingleModule`/`FrameModule`/`ModuleTypeInstance`), `moduletype_defs`
  (`ModuleTypeDef`), `localvariables` (`Variable` with `declaration_span`),
  `modulecode` (`ModuleCode` → `Sequence`/`Equation`), `Sequence.code` is SFC
  body items (`SFCStep` with `SFCCodeBlocks` enter/active/exit, `SFCTransition`
  with condition, alternatives/parallels), code items are
  `Assignment`/`FuncCallStmt`/`IfStmt`/`CodeComment`. Statements and expressions
  (`src/sattline_parser/models/expressions.py`) are **frozen dataclasses** with
  an optional `SourceSpan` (`start`/`end` offsets into the original source, plus
  one-based `line`/`column`). Nodes therefore support structural comparison once
  spans are normalized away.
- **TUI**: the Textual shell (`src/sattlint/ui/_app_textual_app.py`) composes
  mixins: actions, analyze, settings, results, setup. The Analyze view has a
  toolbar (`#analyze-actions-primary`) with action buttons; actions run through
  `_start_action(label, fn, action_id=...)` in a managed worker thread with live
  output (`_emit_output_from_thread`). Handler functions are registered in
  `analysis_handler_fns()` in `src/sattlint/cli/startup.py` and looked up by key
  in `_execute_analyze_plan` (`src/sattlint/ui/_app_textual_analyze.py`).
- **Settings**: app-level settings live under `TOP_LEVEL_CONFIG_FIELDS` in
  `src/sattlint/config/defaults.py`, typed in `src/sattlint/config/types.py`
  (`ConfigDict`/`ConfigOverrideDict`), persisted via
  `save_app_settings`/`APP_LEVEL_CONFIG_KEYS` in `src/sattlint/config/io.py`,
  and edited on the Settings view (`src/sattlint/ui/_app_textual_settings.py`
  + compose block in `_app_textual_app.py`). The existing app-level sections are
  `debug`, `run_history`, and `output`.
- **No production dependency on `tests/fixtures/corpus`**: tests use inline
  SattLine source strings or `tests/fixtures/sample_sattline_files` fixtures.

### Refactoring direction

- Small, composable, typed modules (no giant orchestration classes).
- Objects over dicts, no avoidable `Any`, Pyright strict-clean, typed dispatch
  over reflection.
- No application facades / global registries / compatibility shims.
- Reuse the existing semantic snapshot and dependency graph as the source of
  truth; do not duplicate parser or semantic-graph construction.

## Design

### Architecture

```
Official project          Draft project
      │                        │
    parse/build            parse/build
      │                        │
Official SemanticSnapshot      │
      └──────────┬─────────────┘
                 ▼
           SemanticDiff          (semantic_diff/)
                 │  changed symbols
                 ▼
           ImpactAnalysis        (impact/)
                 │  impacted symbols + relevant context
                 ▼
           ChangeReview          (review/ — canonical model, presentation-independent)
                 │
        ┌────────┴─────────┐
        ▼                  ▼
   JSON serializer     Markdown serializer   (review/serialization/)
        │                  │
        └──────┬───────────┘
               ▼
      configured output location  (TUI action triggers all of the above)
```

### Module layout

```
src/sattlint/change_review/
    __init__.py            # public facade: generate_change_review(...)
    loader.py              # load official + draft snapshots from one config
    semantic_diff.py       # diff model (ChangeChange) + comparison
    comparison.py          # span-normalized AST equality + change classification
    impact.py              # dependency traversal + relevance filtering
    review.py              # ChangeReview model + context extraction
    source.py              # original-source extraction (lines/declarations)
    serialization/
        __init__.py
        json_serializer.py
        markdown_serializer.py
    settings.py            # review output-location setting keys/defaults helpers
```

The `SemanticSnapshot` for official and draft is built once each and reused for
diff, impact, and context extraction. No parser or graph is rebuilt.

### Semantic diff

`SemanticDiff` compares two `SemanticSnapshot`s:

- **Symbol level**: definitions keyed by canonical key. Added (key only in
  draft), removed (key only in official), modified (both sides; compare kind,
  datatype, declaration span presence, and the underlying AST).
- **Code level**: for code-bearing symbols, compare the owning AST subtree with
  `span` fields normalized to `None` so formatting-only changes do not become
  review changes. Changed nodes are classified by node type:
  `expression_changed`, `statement_changed`, `constant_changed`,
  `declaration_changed`, `implementation_changed`, `call_changed`,
  `parameter_changed`, `connection_changed`, `s88_changed`,
  `transition_changed`.
- **Relationship level**: compare `references_by_definition_key` to detect new
  calls/dependencies, and `call_signatures` to detect caller/callee changes.
  Compare `effect_flow_edges` to detect data-dependency changes.
- Each `ChangeChange` records: symbol identity (canonical path + display module
  path), change kind, official representation, draft representation, source
  locations, containing symbol, and relevant semantic relationships.

The diff API answers: what changed, where, which symbols were
added/removed/modified, and what references/dependencies changed.

### Impact / relevance analysis

Relevance is determined by the **semantic role** of each entity in
understanding a change, not by a blind dependency-hop traversal. Every
contextual entity carries an explicit reason and a priority; the result is
ranked and capped by a context-size budget (`max_symbols`, default 60) so the
review never grows to the size of the project.

```
Changed node
    │
    ├── referenced symbols (reads)          priority 90
    ├── definitions of referenced symbols   (facts: type, kind, defined-by)
    ├── data origins (producers of reads)   priority 85
    ├── outputs produced by changed node    priority 90
    ├── consumers of outputs                priority 85
    ├── direct callers / callees            priority 80
    ├── containing module/object            priority 60
    ├── containing S88 sequence/state       priority 70
    └── S88 parent chain                    priority 70
```

Each change carries a `ChangeSemanticContext` (reads, produces, producers,
consumers, callers/callees, containing object, sequence name, previous/next
state, containing state), and the review exposes `relevant_symbols` with their
facts and inclusion reasons.

### ChangeReview model

Presentation-independent dataclasses:

```
ChangeReview
    metadata (official/draft project info, revisions, counts, timestamps)
    changes (tuple[ChangeChange, ...])
    impacted_symbols (tuple[ImpactedSymbol, ...])
    context (tuple[ReviewContextBlock, ...])
    size_stats (total_project_source_size, selected_size, reduction, counts)
```

`ReviewContextBlock` groups: symbol identity, role (`changed`,
`dependency`, `s88_context`), `official_source`, `draft_source` (both only when
comparison is useful), `context_source` (once for unchanged context).

### Context extraction & minimization

For every meaningful change:

- changed statements → include the changed statement span from official and
  draft,
- surrounding declaration → include the declaration (`Variable.declaration_span`
  or module/function-block boundary),
- called function/function block whose full implementation is needed to
  understand behaviour → include complete implementation once,
- unchanged contextual dependencies → include once, never duplicated,
- unrelated code in the same source file → excluded.

Original SattLine source text is preserved (slice the original file text by
`SourceSpan`), never reconstructed artificially. `total project source size`,
`selected review context size`, `reduction %`, and change/impact/context counts
are tracked.

### Output location setting

- New app-level setting `review.output_dir` (default `<config dir>/change-review`
  or equivalent; follow `config.paths` conventions).
- Registered in `TOP_LEVEL_CONFIG_FIELDS`, typed in `config/types.py`, added to
  `APP_LEVEL_CONFIG_KEYS` so it persists with app settings, and editable from
  the Settings view.
- Filename: deterministic `<project>-change-review-<timestamp>.json` and
  `.md`, or `change-review.json`/`change-review.md` in the configured directory,
  following existing generated-artifact naming conventions. Both JSON and
  Markdown are written for the same `ChangeReview`.

### TUI integration

- New action button "Generate Change Review" in the Analyze view toolbar.
- The action uses the currently configured project (targets from
  `analyzed_programs_and_libraries`), loads official (`mode=official`) and draft
  (`mode=draft`) versions, builds both snapshots once, runs diff + impact +
  context, serializes, writes artifacts, and reports the output path in the
  session output panel.
- Handler registered as `generate_change_review` in `analysis_handler_fns()`;
  executed through the existing `_start_action` worker pattern. No new CLI
  command, no new TUI view.

### No static analysis

The generation pipeline never imports or invokes analyzers. The
`generate_change_review` app function loads snapshots directly from the loader
and semantic builders. Nothing in the review depends on analyzer results.

## Phases

### Phase 1 — Semantic diff core

Build the diff model and comparison engine:

- `change_review/comparison.py`: span-normalized structural equality for AST
  nodes; node-type classification; declaration/constant/expression/statement
  fingerprints.
- `change_review/semantic_diff.py`: `SemanticDiff`, `ChangeChange`,
  `ChangeKind`; symbol add/remove/modify detection; code-level diff for
  code-bearing symbols; relationship diff via references, call signatures, and
  effect-flow edges.

Acceptance: focused tests prove added/removed/modified detection, changed
expression/statement/declaration/implementation/call/transition detection, and
that formatting-only differences produce no changes.

### Phase 2 — Impact analysis

- `change_review/impact.py`: bounded BFS over reverse references,
  effect-flow edges, call signatures, and module/S88 hierarchy; relevance role
  tagging; depth and cardinality limits; deduplication.

Acceptance: tests cover changed dependency, changed caller/callee, S88/state
changes, unrelated-code exclusion, shared-dependency dedup.

### Phase 3 — ChangeReview model + context extraction

- `change_review/review.py`: canonical model.
- `change_review/source.py`: original-source extraction by span and by
  declaration boundary (with surrounding lines).
- `change_review/loader.py`: load official + draft snapshots once per project.

Acceptance: tests cover source-location preservation, official/draft source
association, context minimization, and size-stats correctness.

### Phase 4 — Serialization

- `change_review/serialization/json_serializer.py` and
  `.../markdown_serializer.py`: JSON and Markdown from one `ChangeReview`.
- `change_review/serialization/__init__.py`: artifact writing to a directory
  with deterministic naming.

Acceptance: JSON and Markdown correspond to the same model; both write to the
configured output location.

### Phase 5 — Setting + TUI action

- `config/defaults.py`, `config/types.py`, `config/io.py`: add
  `review.output_dir` (app-level, persisted, validated).
- `ui/_app_textual_settings.py` + compose block in `_app_textual_app.py`:
  edit row for the output directory.
- `ui/_app_textual_analyze.py` + `cli/startup.py`: "Generate Change Review"
  button + `generate_change_review` handler wiring; output-path report to the
  session panel.

Acceptance: TUI action generates the expected artifact; configured output
location is respected; setting persists; no CLI command is added.

### Phase 6 — Tests, docs, gates

Tests (pytest, unit-marked, inline SattLine source or `sample_sattline_files`):

1. No changes → empty review.
2. One changed expression.
3. Added symbol.
4. Removed symbol.
5. Changed variable declaration.
6. Changed function/function-block implementation.
7. Changed call relationship.
8. Changed dependency.
9. Changed caller/callee.
10. S88 hierarchy change.
11. State/transition change.
12. Multiple independent changes.
13. Unrelated code excluded from context.
14. Shared dependencies not duplicated.
15. Source locations preserved.
16. Official/draft sources correctly associated.
17. Formatting-only differences produce no changes.
18. Context size ≪ complete project for a realistic project.
19. JSON and Markdown correspond to the same `ChangeReview`.
20. TUI action generates the expected artifact.
21. Configured output location respected.
22. Settings persist correctly.
23. No static analyzer invoked during generation.
24. No CLI command introduced.

Documentation: feature guide + architecture note; update repo map and
`docs/maintainers/validation-map.md` if the map lists surfaces.

## Definition of Done

- Official and draft snapshots built once each; reused for diff/impact/context.
- Change detection is semantic (no grep/regex/line diff as the primary driver).
- `ChangeReview` is presentation-independent; JSON + Markdown from one model.
- TUI action generates and reports artifacts; output location setting persists.
- Zero static-analyzer coupling; no CLI command.
- Full suite green: `python -m ruff check .`, `python -m ruff format --check .`,
  `python -m pyright src/sattlint tests`, `python -m pytest -q --tb=short`.

## Gates

- Focused pytest on the touched slice after each phase.
- Pre-commit: `python -m pre_commit run --all-files`.
- Full local: the four commands in Definition of Done.
