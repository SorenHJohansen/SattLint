# SattLint

[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/SorenHJohansen/SattLint/badge)](https://securityscorecards.dev/viewer/?uri=github.com/SorenHJohansen/SattLint)

SattLint is a Python toolkit for SattLine projects. It provides syntax-checking, configurable static analysis, ICF validation and formatting, graphics-rule analysis, and an interactive terminal UI.

---

## What SattLint Does

- Check whether a SattLine file parses correctly
- Analyze a full program or library together with its dependencies
- Find issues such as unused variables, written-but-never-read variables, and shadowing
- Validate and format ICF files and check graphics rules
- Inspect parser outputs when something looks wrong

---

## Requirements

- **Windows** or **Linux**
- **Python 3.13 or newer**
- **pipx** (for clean, isolated installation)
- A local copy of your SattLine code

---

## Installation

### 1. Get the source

```bash
git clone https://github.com/SorenHJohansen/SattLint.git
cd SattLint
```

### 2. Install pipx

#### Linux

```bash
python3 -m pip install --user pipx
python3 -m pipx ensurepath
```

Restart your terminal after this.

#### Windows

```powershell
py -m pip install --user pipx
py -m pipx ensurepath
```

Restart your terminal after this.

### 3. Install SattLint

```bash
pipx install .
```

This installs SattLint globally in an isolated environment.

### 4. Verify

```bash
sattlint --version
sattlint syntax-check tests/fixtures/sample_sattline_files/SattLineFullGrammarTest.s
```

---

## Quick Start

```bash
sattlint syntax-check path/to/Program.s
```

Output:

- `OK` — valid file
- Error message — invalid file

Exit codes:

- `0` — success
- `1` — command ran and found a real problem
- `2` — invalid arguments or configuration

### Available Commands

```bash
sattlint syntax-check path/to/Program.s
sattlint analyze
sattlint analyze --list-checks
sattlint validate-config
sattlint cache-prune
sattlint format-icf
sattlint format-icf --check
```

Shared flags for config-driven commands:

```bash
sattlint --config path/to/config.toml analyze
sattlint --config path/to/config.toml --no-cache analyze
```

For the full command reference, run `sattlint --help`.

---

## Interactive Shell

```bash
sattlint
```

Opens the Textual interactive terminal UI with the following views:

- **Analyze** — queue curated reports and additional analyzers
- **Setup** — configure paths, targets, mode, and cache settings
- **Tools** — run self-checks, inspect dumps, refresh caches
- **Help** — first-time guidance and workflow explanation

---

## First-Time Setup

The first time SattLint runs, it creates a config file automatically:

- **Windows:** `%APPDATA%\sattlint\config.toml`
- **Linux:** `~/.config/sattlint/config.toml`

### Configuration

1. Start SattLint with `sattlint`
2. Select **Setup**
3. Configure the following:

   - `program_dir` — your SattLine program folder
   - `ABB_lib_dir` — shared or ABB libraries
   - `other_lib_dirs` — any additional libraries
   - `analyzed_programs_and_libraries` — what to analyze
   - `icf_dir` — directory used for ICF validation and formatting
   - `Edit graphics rules` — define expected module invocation or clipping rules (saved as JSON)

4. Save with **Save configuration**
5. Select **Tools** and run **Self-check diagnostics**

> **Note:** Use names without file extensions (e.g. `MyProgram`, not `MyProgram.s`).

---

## Updating

```bash
pipx install --force .
```

---

## Graphics Rule Configuration

1. Open **Setup**, then **Edit graphics rules** to add or update expected invocation coordinates, flags, and clipping-related values
2. Use `unit:` selectors when a module should look the same in every detected unit (e.g. `unit:L1` or `unit:L1.L2.UnitControl`)
3. Use `equipment:` selectors when a module should look the same inside every equipment module (e.g. `equipment:L1.L2.EquipModPanelShort`)
4. Open **Analyze**, then run **Validate graphics rules** from **Structure & modules** to report modules that are not to spec
5. Open **Tools**, then run **Self-check diagnostics** to confirm the graphics rules JSON path is valid

---

## Common Problems

### `sattlint` not found

pipx is not on your PATH. Run `pipx ensurepath` and restart your terminal.

### Python version error

Install Python 3.13+ and reinstall with `pipx install --force .`.

### Targets not found

- Names must not include file extensions
- Paths in config must be correct
- Mode (`official` / `draft`) must match your files

### Missing libraries

Add missing folders to `ABB_lib_dir` or `other_lib_dirs`.

### Results look outdated

Run **Force refresh cached AST** from the Tools menu, or use `sattlint --no-cache analyze`.

---

## For Developers

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, tests, and tooling.

---

## License

SattLint is released under the MIT License.
