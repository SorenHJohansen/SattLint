# SattLint

**SattLint** is a Python-based static-analysis and documentation-generation utility for SattLine projects.  
It parses SattLine source files, resolves dependencies across libraries, builds a unified abstract syntax tree (AST), runs a variable-usage analyzer, and can generate a nicely formatted Word document (`.docx`) describing the whole project.

---

## Table of Contents

1. [Features](#features)
2. [Quick Start](#quick-start)  
   - [Prerequisites](#prerequisites)  
   - [Installation](#installation)  
   - [Running the CLI](#running-the-cli)
3. [Project Layout](#project-layout)
4. [Core Components](#core-components)
5. [Configuration](#configuration)
6. [Typical Workflows](#typical-workflows)
7. [Extending the Tool](#extending-the-tool)
8. [Testing & Debugging](#testing--debugging)
9. [License & Contributing](#license--contributing)

---

## Features

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

- Python 3.10 or newer  
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

### Running the CLI

The command-line entry point is installed as `sattline`. Example invocation:

```bash
sattline \
    --programs-dir /path/to/unitlib \
    --libs-dirs /path/to/commonlib,/path/to/pplibs,/path/to/externallibs \
    --mode official \
    --docx output/project_spec.docx \
    KaGCK7SlutLib
```

#### Key Options

| Flag | Description |
|------|-------------|
| `--programs-dir`, `-p` | Directory holding root program files (`*.x` for official, `*.s` for draft) |
| `--libs-dirs`, `-l` | Comma-separated list of additional library directories |
| `--mode`, `-m` | "official" (default) or "draft" – selects file extensions used |
| `--scan-root-only` | Parse only the root file, ignoring dependencies |
| `--strict` | Fail on missing files or parse errors |
| `--no-debug` | Disable verbose debug prints |
| `--vendor-ignore` | Exclude the vendor library (SL_Library) from the search path |
| `--docx`, `-d` | Path to write generated Word document |
| `--show-missing` | Print summary of missing files or parse failures |
| `--verbose`, `-v` | Increase logging verbosity (INFO level) |
| `--dry-run` | Resolve dependency graph only; no parsing or analysis |
| `--dump-parse-tree` | Write raw Lark parse tree to a file |
| `--dump-ast` | Serialize the final AST to a file |

**Example – variable-usage report only:**

```bash
sattline KaGCK7SlutLib --show-missing
```

Output:

```
Variable issues in KaGCK7SlutLib:
  - Unused variables:
      * [BasePicture] localvariable 'temp_counter' (INTEGER)
  - Read-only but not Const variables:
      * [BasePicture] localvariable 'max_speed' (REAL)
  - Written but never read variables:
      * [BasePicture] localvariable 'debug_flag' (BOOL)
```

---

## Project Layout

```
sattline-tool/
│
├─ main.py                 # Loader, parser creation, orchestration
├─ cli.py                  # CLI arguments and logging
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

`config.toml` example:

```toml
root = "KaGCK7SlutLib"
mode = "official"
ignore_vendor = false

programs_dir = "/mnt/projects/sattline/unitlib"
libs_dirs = [
    "/mnt/projects/sattline/commonlib",
    "/mnt/projects/sattline/pplibs",
    "/mnt/projects/sattline/externallibs"
]
```

Load it in Python:

```python
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

## Typical Workflows

- **Static analysis only** – quickly verify variable usage:

```bash
sattline MyRootProgram --show-missing
```

- **Generate full spec document**:

```bash
sattline MyRootProgram -d ./specs/MyProjectSpec.docx
```

- **CI integration** – enforce strict parsing:

```yaml
# .github/workflows/ci.yml
- name: Run SattLine analysis
  run: |
    sattline MyRootProgram --strict --show-missing
```

- **Debug parse failures**:

```bash
sattline MyRootProgram --dump-parse-tree parse.txt
```

- **Dependency-only check**:

```bash
sattline MyRootProgram --dry-run
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
