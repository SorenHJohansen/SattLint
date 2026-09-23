# Python API Reference

This document describes the public Python API surface for `sattlint` and `sattline_parser`.

> **Note:** The stable public contract is the CLI surface. Python APIs are still evolving and may change across minor versions.

---

## `sattlint` Package

### `sattlint.analyzers`

The analyzers package does not export any public symbols directly. Individual analyzer subpackages should be imported explicitly.

### `sattlint.analyzers.dataflow`

| Export | Description |
|--------|-------------|
| `DataflowAnalyzer` | Full dataflow analysis entrypoint |
| `DataflowConditionMixin` | Condition analysis mixin |
| `DataflowIssueReportingMixin` | Issue reporting mixin |
| `DataflowStateMixin` | State tracking mixin |
| `DataflowTraversalMixin` | Traversal mixin |
| `analyze_dataflow` | Convenience function running the full analysis |
| `INITIALIZED`, `OLD_PREFIX`, `PENDING_PREFIX`, `UNKNOWN` | Constants |
| `ResolvedRef`, `ScalarValue`, `StateMap` | Data types |

### `sattlint.analyzers.icf`

| Export | Description |
|--------|-------------|
| `validate_icf_entries_against_program` | Validate ICF entries against a base picture |
| `parse_icf_file` | Parse `.icf` key/value entries |
| `resolve_leaf_datatype`, `resolve_record_datatype` | Datatype resolution helpers |

### `sattlint.analyzers.registry`

The registry provides access to all registered analyzers and their metadata. See source for the full `__all__` list.

### `sattlint.analyzers.sfc`

| Export | Description |
|--------|-------------|
| `analyze_sfc` | SFC analysis entrypoint |
| `SfcReachabilityFinding` | Reachability finding type |
| `collect_sfc_reachability_findings` | Reachability collection helper |

### `sattlint.cli`

No public exports. Import submodules directly.

### `sattlint.core`

| Export | Description |
|--------|-------------|
| `SemanticSnapshot`, `SymbolDefinition`, `SymbolReference` | Core semantic types |
| `WorkspaceSourceDiscovery` | Source discovery |
| `build_source_snapshot_from_basepicture`, `load_source_snapshot` | Snapshot loading |

### `sattlint.resolution`

| Export | Description |
|--------|-------------|
| `CanonicalPath`, `CanonicalPathKey`, `ModuleSegment` | Path types |
| `CanonicalSymbolTable`, `SymbolDef`, `SymbolKind` | Symbol table |
| `TypeGraph` | Type graph |
| `AccessEvent`, `AccessGraph`, `AccessKind` | Access tracking |
| `ContextBuilder` | Context builder |

### `sattlint.reporting`

No public exports. Import submodules directly.

### `sattlint.project`

| Export | Description |
|--------|-------------|
| `ParserProjectBinding` | Frozen parser binding (config roots, load mode, `debug_fn`, status/timing hooks); produced by `loader_config.build_parser_binding` and consumed by `load_project`/`load_program_ast`/`parser-loader.cache_manifest_files` |
| `load_project`, `load_program_ast`, `iter_loaded_projects`, `ensure_ast_cache`, `force_refresh_ast` | Orchestration entry points (project-view merge, timings, reverse-consumer loading, analysis-cache handling). Loads route through `loader_config.build_parser_binding` + `parser_adapter.load_parser_project`/`convert_project_into_graph` — the retired `SattLineProjectLoader` shell is gone |
| `loader_config` | `build_parser_binding(cfg, *, status_update_fn, refresh_mode, stage_timing_sink, graphics_timing_sink)` plus `validate_loader_config` and the load-timing sink types |
| `SattLintProjectFile` | `.slproj` wrapper model |
| `CircularDependencyError`, `DependencyVersionCompatibilityError` | Project-layer errors re-exported through `sattlint.engine` |

### `sattlint.transformer`

No public exports. Import submodules directly.

---

## `sattline_parser` Package (external dependency)

`sattline_parser` is provided by the external `sattline-parser` package (from PyPI), not this repository.

| Export | Description |
|--------|-------------|
| `build_lark_parser` | Build a Lark parser instance |
| `parse_source_text` | Parse SattLine source text |
| `read_text_with_fallback` | Read source with encoding fallback |
| `fuzz_parse_text` | Fuzz-targeted parse with timeout |
| `run_random_fuzz` | Run random fuzz rounds |

#### Project layer (`sattline_parser.project`)

| Export | Description |
|--------|-------------|
| `SattLineProject` | Owns search roots, load mode, file discovery, dependency resolution, and the resolved dependency graph (`load(roots, mode, targets, *, strict, debug, cache_dir)`); `cache_dir=None` keeps loads hermetic |
| `SattLineProgram` | One logical SattLine program/library: parsed code AST, graphics model, declared dependency names, source/format info |
| `ProjectLoader`, `read_dependency_names` | Recursive resolution and `.l`/`.z` dependency-name reading |
| `DependencyGraph` | Resolved, casefolded dependency graph |
| `LoadMode`, `ProgramFormat`, `ArtifactKind` | Mode / format / artifact-kind enums |
| `ProjectLookup`, `SourceIndex`, `ordered_lookup_bases`, `shared_lookup_root_for` | Discovery and ordered search-root lookup |
| `FileASTCache`, `FileLookupCache` | Parser-owned per-file AST and lookup caches (behind `cache_dir`) |
| `parse_graphics_text`, `parse_graphics_file`, `resolve_graphics_companion_path` | `.g`/`.y` graphics companion parsing |
| `ProjectLoadError`, `ArtifactLoadError`, `DependencyNotFoundError`, `DependencyParseError` | Structured project-layer errors |

See the `sattline-parser` source for the full `__all__` listing.

---

## Stability

| Surface | Stability |
|---------|-----------|
| `sattlint.cli.startup:cli` (entrypoint) | Stable |
| `sattlint` CLI commands | Stable |
| `sattline_parser.api` | Stable |
| `sattline_parser.project` (project layer) | Preview |
| `sattlint.analyzers.*` | Preview |
