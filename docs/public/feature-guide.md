# SattLint Feature Guide

Comprehensive guide to all SattLint tools, CLI commands, TUI workflows, and their relationships.

---

## Overview

SattLint is a Python toolkit for SattLine projects. It provides:

- **Syntax validation** — strict single-file parsing
- **Static analysis** — semantic checks, variable analysis, dataflow, architecture validation
- **Repository auditing** — health checks, quality gates, CI integration
- **Documentation generation** — DOCX output from SattLine sources
- **Language server** — LSP endpoint for editor integration (VS Code)
- **Interactive TUI** — Textual-based menu for guided workflows

---

## Installation

```bash
pipx install .
```

For development:

```bash
git clone https://github.com/SorenHJohansen/SattLint.git
cd SattLint
pip install -e ".[dev,lsp]"
```

Requirements: Python 3.13+, Windows or Linux.

---

## Stable CLI Commands

These commands carry the SattLint v1.0 compatibility promise.

### `sattlint --version`

Print the installed version.

```bash
sattlint --version
```

### `sattlint syntax-check`

Validate a single SattLine file for syntax errors. Accepts `.s`, `.x`, `.g`, `.y` files. When validating `.s` or `.x`, automatically checks the matching graphics sidecar.

```bash
sattlint syntax-check path/to/Program.s
```

Exit codes: 0 = valid, 1 = problem found, 2 = invalid arguments.

### `sattlint repo-audit`

Run repository-level health and quality checks. Supports `--profile quick` for fast iteration and `--profile full` for comprehensive CI gate.

```bash
sattlint repo-audit --profile quick
sattlint repo-audit --profile full
sattlint repo-audit --fail-on high
```

### `sattlint-lsp`

Start the Language Server Protocol server. Used by the VS Code extension.

```bash
sattlint-lsp
```

---

## Preview CLI Commands

These commands are functional but may change in future releases.

### `sattlint analyze`

Run semantic analysis on the configured project.

```bash
sattlint analyze
sattlint analyze --list-checks
sattlint --config path/to/config.toml analyze
sattlint --no-cache analyze
```

### `sattlint validate-config`

Validate the SattLint configuration file.

```bash
sattlint validate-config
sattlint --config path/to/config.toml validate-config
```

### `sattlint docgen`

Generate Word (DOCX) documentation from SattLine sources.

```bash
sattlint docgen --output-dir docs-out
sattlint docgen --output-path docs-out/Main_FS.docx
```

### `sattlint format-icf`

Format Industrial Control Format (ICF) files.

```bash
sattlint format-icf
sattlint format-icf --check
```

### `sattlint source-diff`

Build a review-friendly diff report between draft `.s` and official `.x` source pairs.

```bash
sattlint source-diff --workspace-root path/to/workspace --discover-pairs
sattlint source-diff --workspace-root path/to/workspace --draft-file WidgetReview.s --official-file WidgetReview.x
```

### Shared Flags

```bash
sattlint --config path/to/config.toml <subcommand>
sattlint --quiet <subcommand>
sattlint --no-cache <subcommand>
```

---

## DevTools Commands

These are internal repository-tooling entry points. They ship with the package but are designed for maintainer and CI use.

| Command | Purpose | Profile |
|---------|---------|---------|
| `sattlint-repo-audit` | Full repository audit entry point | `--profile quick/full` |
| `sattlint-analysis-pipeline` | Shared CI pipeline runner | `--profile full --check <name>` |
| `sattlint-layer-lint` | SattLine module hierarchy layer validation | — |
| `sattlint-structural-ratchet` | Structural budget ratchet verification | `--json` |
| `sattlint-doc-gardener` | Documentation structure and reference validation | `--check-only` |
| `sattlint-release-smoke` | Pre-publish wheel smoke test | `--wheel ... --sample-file ...` |
| `sattlint-corpus-runner` | Regression test corpus execution | — |
| `sattlint-review` | Code review assistant (advisory) | — |
| `sattlint-trace` | Parser and analyzer execution tracer | — |
| `sattlint-observability` | Performance profiling and metrics snapshot | — |

---

## Interactive TUI

Running `sattlint` with no arguments opens the Textual interactive shell.

### Views

| View | Purpose |
|------|---------|
| **Analyze** | Queue reports and analyzers. Start with the planner for a broad pass, then add focused reports. |
| **Documentation** | Preview unit scope and generate DOCX output. |
| **Setup** | Configure paths (program_dir, ABB_lib_dir, icf_dir, other_lib_dirs), targets, mode, cache settings. |
| **Tools** | Run self-check diagnostics, inspect dumps, refresh caches, open tracing tools. |
| **Results** | View formatted output of previous actions. Click history entries for details. |
| **Help** | First-run guidance, workflow explanations. |

### Graphics Layout Specification

1. Open **Setup > Edit graphics rules** to add expected invocation coordinates, flags, and clipping values.
2. Use `unit:` selectors (e.g., `unit:L1`) for modules that look the same in every unit.
3. Use `equipment:` selectors (e.g., `equipment:L1.L2.EquipModPanelShort`) for equipment-scoped rules.
4. Moduletype rules identify modules by resolved `ModuleType` name, optionally narrowed with `unit:`, `equipment:`, or exact-path selectors.
5. Run **Analyze > Validate graphics rules** to report modules not matching spec.
6. Run **Tools > Self-check diagnostics** to confirm the graphics rules JSON path is valid.

### Keyboard & Mouse

- **Sidebar**: Click view names to switch between Analyze, Config, Docs, Tools, Results.
- **Buttons**: Click action buttons to start tasks.
- **History**: Click entries in Results view for details.
- **Scrolling**: All text areas support scrollbars.

### Status Bar

Shows current action and task progress (e.g., "Self-check running...", "Documentation generation finished").

---

## Configuration

First run creates a default config file:

- **Windows:** `%APPDATA%\sattlint\config.toml`
- **Linux:** `~/.config/sattlint/config.toml`

Override with `--config path/to/custom.toml`.

### Key settings

| Setting | Description |
|---------|-------------|
| `program_dir` | SattLine program folder |
| `ABB_lib_dir` | ABB shared library directory |
| `icf_dir` | ICF file directory for validation and formatting |
| `other_lib_dirs` | Additional library directories |
| `analyzed_programs_and_libraries` | Analysis targets |
| `mode` | `"official"` or `"draft"` |
| `include_reverse_library_consumers` | Expand analysis scope for library consumers |

Use names without file extensions: `MyProgram`, not `MyProgram.s`.

---

## Quality Gates

| Gate | Command | When |
|------|---------|------|
| Pre-commit | `python -m pre_commit run --all-files` | Before every commit |
| AI drift | `sattlint-repo-audit --profile full --check-my-changes --output-dir artifacts/audit` | After AI-assisted edits |
| Pre-push | `sattlint-repo-audit --profile full --output-dir artifacts/audit` | Before pushing |
| CI | Automatic on PR and push to `main` | Via GitHub Actions |
| Nightly | Scheduled full audit with trend snapshots | Daily |

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Command ran and found a real problem |
| 2 | Invalid arguments or configuration |

---

## See Also

- [Architecture overview](architecture.md) — system layering and runtime entry points
- [CLI commands reference](cli-commands.md) — full command surface
- [Public support matrix](../references/public-support-matrix.md) — stable vs preview contract
- [CONTRIBUTING.md](../../CONTRIBUTING.md) — development setup and workflow
- [README.md](../../README.md) — source checkout quick start
