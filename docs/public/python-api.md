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
| `ICFFormatResult` | ICF formatting result type |
| `format_icf_file`, `format_icf_text`, `parse_icf_file` | ICF formatting and parsing |
| `resolve_leaf_datatype`, `resolve_record_datatype` | Datatype resolution helpers |

### `sattlint.analyzers.mms`

| Export | Description |
|--------|-------------|
| `analyze_mms_interface_variables` | MMS interface variable analysis |
| `collect_icf_inventory_entries`, `collect_mms_inventory_entries`, `load_icf_entries_from_config` | Inventory collection |

### `sattlint.analyzers.registry`

The registry provides access to all registered analyzers and their metadata. See source for the full `__all__` list.

### `sattlint.analyzers.sfc`

| Export | Description |
|--------|-------------|
| `analyze_sfc` | SFC analysis entrypoint |
| `SfcReachabilityFinding` | Reachability finding type |
| `StepContract`, `StepSet`, `ExclusiveStepGroup` | SFC data types |

### `sattlint.cli`

No public exports. Import submodules directly.

### `sattlint.core`

| Export | Description |
|--------|-------------|
| `SemanticSnapshot`, `SymbolDefinition`, `SymbolReference` | Core semantic types |
| `CompletionItem`, `SemanticDiagnostic` | LSP-oriented types |
| `WorkspaceSourceDiscovery` | Source discovery |
| `build_source_snapshot_from_basepicture`, `discover_workspace_sources`, `load_source_snapshot`, `load_workspace_snapshot` | Snapshot loading |
| `LineIndex`, `utf16_index_to_codepoint_offset` | Document text helpers |

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

### `sattlint.transformer`

No public exports. Import submodules directly.

### `sattlint.devtools`

See the `sattlint-devtools` CLI surface in [cli-commands.md](cli-commands.md) for the primary tooling entrypoints.

### `sattlint.devtools.ai`, `sattlint.devtools.audit`, `sattlint.devtools.sandbox`

These packages use `__getattr__` to dynamically re-export submodule contents.

### `sattlint.devtools.pipeline`

The pipeline package provides the analysis pipeline entrypoint and supporting utilities.

### `sattlint.devtools.structural`

| Export | Description |
|--------|-------------|
| `collect_structural_budget_report` | Structural budget report collector |
| `summarize_structural_budget_metrics` | Budget metric summarizer |

---

## `sattline_parser` Package

| Export | Description |
|--------|-------------|
| `build_lark_parser` | Build a Lark parser instance |
| `parse_source_text` | Parse SattLine source text |
| `read_text_with_fallback` | Read source with encoding fallback |
| `fuzz_parse_text` | Fuzz-targeted parse with timeout |
| `run_random_fuzz` | Run random fuzz rounds |

See the `sattline_parser` source for the full `__all__` listing.

---

## Stability

| Surface | Stability |
|---------|-----------|
| `sattlint.app:cli` (entrypoint) | Stable |
| `sattlint` CLI commands | Stable |
| `sattline_parser.api` | Stable |
| `sattlint.analyzers.*` | Preview |
| `sattlint.devtools.*` | Internal |
| `sattlint_lsp.*` | Internal |
