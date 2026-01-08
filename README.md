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
3. [Project Layout](#project-layout)
4. [Core Components](#core-components)
5. [Configuration](#configuration)
6. [Extending the Tool](#extending-the-tool)
7. [Testing & Debugging](#testing--debugging)
8. [License & Contributing](#license--contributing)

---

## Features

- **Interactive menu-driven application**.
- **Full SattLine parsing** using a Lark grammar (`grammar/sattline.lark`).  
- **Recursive dependency resolution** across a configurable set of library directories, with optional vendor-library exclusion.  
- **Variable-usage analysis** reports:  
  - Unused variables  
  - Read-only variables not declared `CONST`  
  - Variables that are written but never read  
- **Merge-project capability** – creates a synthetic `BasePicture` that aggregates all datatype and module-type definitions, allowing analysis across file boundaries.  
- **DOCX documentation generation** (`generate_docx`) produces a human-readable specification of the project.  
- **Debug mode** (`--debug` / `DEBUG`) prints detailed tracing of file discovery, parsing, and analysis steps.  
- **Strict mode** (`--strict`) aborts on missing files or parse errors, useful for CI pipelines.  

---

## Quick Start

### Prerequisites

- Python 3.11 or newer  
- Git (optional, for cloning)  
- A working SattLine codebase (expects a root program and its dependent libraries)  

### Installation

```bash
# Clone the repository
git clone <repo-url>
cd sattline-tool

# Install the package in editable mode
pip install -e .
```

Dependencies are declared in `pyproject.toml`:

```toml
lark-parser>=0.11.0
python-docx>=0.8.11  # Only needed if generating .docx files
```

### How to Run

From the project directory:

```python
python app.py
```

This starts the interactive SattLint application.

### Interactive Usage

When started, SattLint presents a menu similar to:
=== SattLint ===
How to use SattLint
------------------

• Navigate using the number keys shown in each menu
• Press Enter to confirm a selection
• Changes are NOT saved until you choose "Save config"
• Use "Configuration" to change settings
• Use "Run analysis" to analyze the configured root program
• Use "Dump outputs" to inspect parse trees, ASTs, etc.
• Press 'q' at any time in the main menu to quit

1) Show config
2) Configuration
3) Run analysis
4) Dump outputs
5) Save config
6) Self-check diagnostics
q) Quit

## Project Layout

```
sattline-tool/
│
├─ app.py                  # Interactive application entry point
├─ engine.py               # Loader, parser creation, orchestration
├─ sl_transformer.py       # Lark Transformer → AST
├─ variables.py            # Variable usage analyzer
├─ constants.py            # Grammar constants & regexes
├─ config.toml             # Example configuration file
├─ pyproject.toml          # Dependencies & build metadata
│
├─ models/                 # Dataclasses defining AST nodes
│   ├─ ast_model.py
│   └─ project_graph.py
│
├─ analyzers/              # Additional static analyses
│   └─ sattline_builtins.py
│
├─ docgenerator/           # Optional DOCX generator
│   └─ docgen.py
│
└─ grammar/
    └─ sattline.lark       # Lark grammar file (required at runtime)
```

---

## Core Components

- **main.py** – Workspace setup, parser creation, project loading, merging BasePicture  
- **cli.py** – CLI argument parsing, logging, DOCX generation, debug/dump options  
- **sl_transformer.py** – Lark Transformer → concrete AST objects, handles all language constructs  
- **variables.py** – VariablesAnalyzer walks AST, records usage, generates reports  
- **docgenerator/** – `generate_docx(project_bp, out_path)` renders a structured Word document  
- **models/** – AST node dataclasses (`BasePicture`, `Module`, `Variable`, etc.)  
- **constants.py** – Grammar literals, regex patterns, tree-tag keys  

---

## Configuration

All settings are stored in config.toml, which is the single source of truth.

`config.toml` example:

```toml
# ----------------------------
# General project configuration
# ----------------------------
root = "KaGCK7SlutLib"
mode = "official"          # "official" or "draft"
ignore_vendor = false
scan_root_only = false
debug = false

# ----------------------------
# Paths
# ----------------------------
vendor_libs_dir = "/mnt/vendor_dir"
programs_dir = "/mnt/projects/sattline/unitlib"

libs_dirs = [
  "/mnt/projects/sattline/commonlib",
  "/mnt/projects/sattline/pplibs",
  "/mnt/projects/sattline/externallibs",
]```python
import tomllib
from pathlib import Path
import main as main_mod

cfg = tomllib.loads(Path("config.toml").read_text())
loader = main_mod.SattLineProjectLoader(
    Path(cfg["programs_dir"]),
    [Path(p) for p in cfg["libs_dirs"]],
    main_mod.CodeMode.OFFICIAL if cfg["mode"] == "official" else main_mod.CodeMode.DRAFT,
    scan_root_only=False,
)
graph = loader.resolve(cfg["root"])
```

---

## Extending the Tool

- Add new analyses under `analyzers/`, register in `main.py` or expose via CLI  
- Support additional output formats by plugging in renderers in `docgenerator/`  
- Extend grammar (`grammar/sattline.lark`) and update `constants.py`  
- Customize vendor-library handling with `IGNORE_VENDOR_LIB` or `_is_ignored_base`  

---

## Testing & Debugging

- **Unit tests** – place under `tests/` and run with `pytest`  
- **Logging** – respects `--verbose` and `--debug`; set `DEBUG=True` in `main.py` for step-by-step prints  
- **Interactive exploration**:

```python
from main import SattLineProjectLoader, CodeMode

loader = SattLineProjectLoader(Path("unitlib"), [Path("commonlib")], CodeMode.OFFICIAL)
graph = loader.resolve("MyRoot")
graph.ast_by_name["MyRoot"].modulecode.sequences[0].code
```

---

## License & Contributing

- Released under the **MIT License**  
- Contributions welcome: fork, create a feature branch, and submit a PR  
- Follow existing code style (PEP 8, type hints, docstrings)
