# SattLint

**SattLint** is a Python-based static-analysis and documentation-generation utility for SattLine projects.
It parses SattLine source files, resolves dependencies across libraries, builds a unified abstract syntax tree (AST), runs a variable-usage analyzer, and can generate a nicely formatted Word document (`.docx`) describing the whole project.

---

## Table of Contents

1. [Features](#features)
2. [Quick Start](#quick-start)
   - [Prerequisites](#prerequisites)
   - [Installation](#installation)
   - [How to run](#how-to-run)
   - [Interactive usage](#interactive-usage)
3. [Core Components](#core-components)
4. [Configuration](#configuration)
5. [License & Contributing](#license--contributing)

---

## Features

- **Interactive menu-driven application**.
- **Non-interactive syntax check** for a single SattLine file via `sattlint syntax-check <file>`.
- **Full SattLine parsing** using a Lark grammar (`grammar/sattline.lark`).
- **Recursive dependency resolution** across a configurable set of library directories, with optional vendor-library exclusion.
- **Variable-usage analysis** reports:
  - Unused variables
  - Read-only variables not declared `CONST`
  - Variables that are written but never read
  - Min/Max mapping name mismatches
- **SFC analysis** reports parallel-branch write races.
- **Merge-project capability** – creates a synthetic `BasePicture` that aggregates all datatype and module-type definitions, allowing analysis across file boundaries.
- **DOCX documentation generation** (`generate_docx`) produces an FS-style specification grouped by detected equipment modules, operations, and parameter categories.
- **Unit-scoped documentation** lets you limit DOCX generation to selected unit roots from the Documentation menu without storing that scope in config.
- **Debug mode** (`--debug` / `DEBUG`) prints detailed tracing of file discovery, parsing, and analysis steps.
- **Strict mode** (`--strict`) aborts on missing files or parse errors, useful for CI pipelines.
- **Language Server Protocol support** via `sattlint-lsp` plus a local VS Code client in `vscode/sattline-vscode/` for syntax diagnostics, go-to-definition, and completion.

---

## Quick Start

### Prerequisites

- Python 3.11 or newer
- Git (optional, for cloning)
- pipx
- A working SattLine codebase (expects a root program and its dependent libraries)

### Installation

```bash
# Clone the repository
git clone <repo-url>
cd SattLint
```

Install pipx:

```bash
python3 -m pip install --user pipx
```

```bash
# Install the package
pipx install sattlint
```

Dependencies are declared in `pyproject.toml` like:

```toml
lark-parser>=0.11.0
python-docx>=0.8.11
```

### How to Run

In the terminal just type:

```bash
sattlint
```

This starts the interactive SattLint application.

To validate that a single SattLine file parses and transforms cleanly, run:

```bash
sattlint syntax-check path/to/Program.s
```

The command prints `OK` and exits with code `0` when the file is valid. If parsing or transformation fails, it prints a compact error message with location information when available and exits non-zero.

The syntax check also performs strict post-transform validation for structural mistakes that the grammar alone may accept. Current checks include consecutive `SEQSTEP` blocks with no intervening `SEQTRANSITION`, missing `SEQINITSTEP` at the start of a sequence, unknown `SEQFORK` targets, duplicate names in the same declaration scope, `OLD`/`NEW` access on non-`STATE` variables, and identifier names longer than 20 characters.

### Interactive Usage

When started, SattLint presents a menu similar to:

```bash
=== SattLint ===
How to use SattLint
------------------
- Navigate using the number keys shown in each menu
- Press Enter to confirm a selection
- Changes are NOT saved until you choose "Save config"
- Use "Configuration" to change settings
- Use "Run analysis" to analyze the configured root program
- Use "Dump outputs" to inspect parse trees, ASTs, etc.
- Press 'q' at any time in the main menu to quit

1) Show config
2) Configuration
3) Run analysis
4) Dump outputs
5) Save config
6) Self-check diagnostics
q) Quit
```

---

## Core Components

- **app.py** – Main entry point
- **engine.py** – Workspace setup, parser creation, project loading, merging BasePicture
- **sl_transformer.py** – Lark Transformer → concrete AST objects, handles all language constructs
- **variables.py** – VariablesAnalyzer walks AST, records usage, generates reports
- **docgenerator/** – `generate_docx(project_bp, out_path, documentation_config=...)` renders an FS-style Word document; `classification.py` maps modules into documentation sections using config-driven rules
- **Documentation menu** – preview unit candidates, choose scope by instance path or moduletype name, and generate filtered DOCX output from the interactive app
- **models/** – AST node dataclasses (`BasePicture`, `Module`, `Variable`, etc.)
- **constants.py** – Grammar literals, regex patterns, tree-tag keys

---

## Cross-Platform Development

SattLint supports development on both Linux and Windows platforms:

### Development Environments
- **Linux**: Recommended with Neovim + LSP (pyright/ruff)
- **Windows**: Recommended with Visual Studio Code + Python extension

### Quick Setup

#### Linux (Neovim)
```bash
# Install Python version manager
mise install python@3.13

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate

# Install in development mode
pip install -e .[dev]

# Install development tools (already in pyproject.toml)
```

#### Windows (VS Code)
```powershell
# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# Install in development mode
pip install -e .[dev]

# VS Code will prompt to install Python extension and use .vscode/settings.json
```

### VS Code SattLine Extension

The repository includes a no-build VS Code extension client under `vscode/sattline-vscode/` plus a Python LSP server exposed as `sattlint-lsp`.

Set up the Python server first:

```powershell
.venv\Scripts\Activate.ps1
pip install -e .[lsp]
```

Install the VS Code client by copying or symlinking `vscode\sattline-vscode` into your user extensions directory as `local.sattline-vscode-0.1.0`, then reload the VS Code window.

On Windows, that target directory is typically:

```text
%USERPROFILE%\.vscode\extensions\local.sattline-vscode-0.1.0
```

There is no npm or TypeScript build step for local development. The extension launches `python -m sattlint_lsp.server` over stdio, supports `.s`, `.x`, `.l`, and `.z` files, and ships a TextMate grammar for syntax highlighting.

If you want a `.vsix`, package it from WSL in the extension folder:

```bash
cd /mnt/c/Users/SQHJ/OneDrive\ -\ Novo\ Nordisk/Workspace/GitHub.com/SattLint/vscode/sattline-vscode
npm run package:vsix
```

That command produces `sattline-vscode-0.1.0.vsix` in `vscode/sattline-vscode/`.

Useful settings:
- `sattlineLsp.pythonPath` to override interpreter detection
- `sattlineLsp.entryFile` when editing `.l`/`.z` files in a workspace with multiple root programs
- `sattlineLsp.mode` to switch between `draft` and `official` resolution
- `sattlineLsp.scanRootOnly` to skip recursive dependency loading
- `sattlineLsp.enableVariableDiagnostics` to disable analyzer-backed warnings
- `sattlineLsp.maxCompletionItems` to cap completion results

### Code Quality Tools
- **Formatting**: Black (configured in pyproject.toml)
- **Linting**: Ruff (configured in pyproject.toml)
- **Type Checking**: MyPy (configured in pyproject.toml)
- **Testing**: Pytest (configured in pyproject.toml)

### Git Workflow
The repository is configured for seamless development across platforms:
- `.editorconfig` ensures consistent formatting across editors
- `.vscode/settings.json` provides VS Code workspace configuration
- All settings are committed to git for consistency between machines

---

## Configuration

All settings are stored in config.toml, which is the single source of truth.

`config.toml` example:

```toml
# ----------------------------
# General project configuration
# ----------------------------
analyzed_programs_and_libraries = ["ProgramName"]
mode = "official"          # "official" or "draft"
scan_root_only = false
debug = false

# ----------------------------
# Paths
# ----------------------------
ABB_lib_dir = "/mnt/vendor_dir"
program_dir = "/mnt/projects/sattline/unitlib"
other_lib_dirs = [
  "/mnt/projects/sattline/commonlib",
  "/mnt/projects/sattline/externallibs",
]

# ----------------------------
# Documentation generation
# ----------------------------
[documentation]
[documentation.classifications.ops]
desc_label_equals = ["NNEMESIFLib:MES_StateControl"]

[documentation.classifications.em]
desc_label_equals = ["nnestruct:EquipModCoordinate"]

[documentation.classifications.rp]
name_contains = ["RecPar"]

[documentation.classifications.ep]
name_contains = ["EngPar"]

[documentation.classifications.up]
name_contains = ["UsrPar"]
```

The documentation rules are editable. The defaults above are designed around the common NNE/ABB patterns discovered in the loaded project graph.
The FS section order follows the reference template in code and is not configured in `config.toml`. Unit scope is selected at runtime from the Documentation menu by unit instance path or unit moduletype name.

---

## License & Contributing

- Released under the **MIT License**
- Contributions welcome: fork, create a feature branch, and submit a PR
- Follow existing code style (PEP 8, type hints, docstrings)
