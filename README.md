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
- `1` — a real problem was found (e.g. `syntax-check` found a syntax error)
- `2` — invalid arguments or configuration

`analyze` reports issues in its output but exits `0` once the analysis runs;
among the CLI commands, only `syntax-check` uses exit code `1` for findings.

### Available Commands

```bash
sattlint syntax-check path/to/Program.s
sattlint init                    # scaffold a .slproj project file
sattlint analyze --list-checks   # list available analyzers
sattlint analyze --check naming-consistency
sattlint validate-config
sattlint cache-prune
```

Shared flags for config-driven commands:

```bash
sattlint --config path/to/config.toml analyze --check naming-consistency
sattlint --config path/to/config.toml --no-cache analyze --check naming-consistency
sattlint --project path/to/project.slproj analyze --check naming-consistency
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
- **Help** — first-time guidance and workflow explanation

---

## Project Files (.slproj)

A `.slproj` project file captures all analysis settings in a single
checked-in file: targets, directories, mode, and output/cache paths. Paths
inside a `.slproj` are relative to the file itself, so projects are portable
across machines.

- `sattlint init` scaffolds a new `.slproj` in the current directory.
- `sattlint --project PATH <command>` uses an explicit project file.
- Without `--project` or `--config`, SattLint auto-discovers a `.slproj` by
  walking up from the current working directory.
- Project settings merge over `~/.config/sattlint/config.toml` defaults.

Prefer a `.slproj` project file over editing `~/.config/sattlint/config.toml`
directly.

---

## First-Time Setup

The first time SattLint runs, it creates a config file automatically:

- **Windows:** `%APPDATA%\sattlint\config.toml`
- **Linux:** `~/.config/sattlint/config.toml`

For a portable, checked-in setup, create a `.slproj` project file with
`sattlint init` instead; project settings merge over these config defaults
(see [Project Files](#project-files-slproj)).

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
5. Select **Analyze** to run checks

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
5. Run `sattlint validate-config` to confirm the graphics rules JSON path is valid

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

Use `sattlint --no-cache analyze` to skip the AST cache, or run `sattlint cache-prune` to remove stale cache artifacts before re-analyzing.

---

## For Developers

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, tests, and tooling.

---

## License

SattLint is released under the MIT License.
