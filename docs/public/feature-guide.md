# SattLint Feature Guide

Comprehensive guide to the SattLint tools, CLI commands, and TUI workflows.

---

## Overview

SattLint is a Python toolkit for SattLine projects. It provides:

- **Syntax validation** — strict single-file parsing
- **Static analysis** — semantic checks, variable analysis, dataflow, architecture validation
- **ICF and graphics analysis** — validate and format ICF files and check graphics rules
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
pip install -e .
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

### `sattlint cache-prune`

Prune the AST analysis cache.

```bash
sattlint cache-prune
```

### `sattlint format-icf`

Format Industrial Control Format (ICF) files.

```bash
sattlint format-icf
sattlint format-icf --check
```

### Shared Flags

```bash
sattlint --config path/to/config.toml <subcommand>
sattlint --quiet <subcommand>
sattlint --no-cache <subcommand>
```

---

## Interactive TUI

Running `sattlint` with no arguments opens the Textual interactive shell.

### Views

| View | Purpose |
|------|---------|
| **Analyze** | Queue reports and analyzers. Start with the planner for a broad pass, then add focused reports. |
| **Setup** | Configure paths (program_dir, ABB_lib_dir, icf_dir, other_lib_dirs), targets, mode, cache settings. |
| **Tools** | Run self-check diagnostics, inspect dumps, refresh caches. |
| **Help** | First-run guidance, workflow explanations. |

### Graphics Layout Specification

1. Open **Setup > Edit graphics rules** to add expected invocation coordinates, flags, and clipping values.
2. Use `unit:` selectors (e.g., `unit:L1`) for modules that look the same in every unit.
3. Use `equipment:` selectors (e.g., `equipment:L1.L2.EquipModPanelShort`) for equipment-scoped rules.
4. Moduletype rules identify modules by resolved `ModuleType` name, optionally narrowed with `unit:`, `equipment:`, or exact-path selectors.
5. Run **Analyze > Validate graphics rules** to report modules not matching spec.
6. Run **Tools > Self-check diagnostics** to confirm the graphics rules JSON path is valid.

### Keyboard & Mouse

- **Sidebar**: Click view names to switch between Analyze, Setup, Tools, and Help.
- **Buttons**: Click action buttons to start tasks.
- **Scrolling**: All text areas support scrollbars.

### Status Bar

Shows current action and task progress (e.g., "Self-check running...").

---

## Configuration

First run creates a default config file:

- **Windows:** `%APPDATA%\sattlint\config.toml`
- **Linux:** `~/.config/sattlint/config.toml`

Override with `--config path/to/custom.toml`. Project analysis uses `.slproj` project files.

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

Run the retained validation locally before changes:

```bash
python -m ruff check .
python -m pyright src/sattlint
python -m pytest -q
python -m build
```

CI runs automatically on PR and push to `main`.

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
- [SUPPORT.md](../../SUPPORT.md) — support contract, stable vs preview status, removed surfaces
- [CONTRIBUTING.md](../../CONTRIBUTING.md) — development setup and workflow
- [README.md](../../README.md) — source checkout quick start
