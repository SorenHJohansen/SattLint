# SattLint

[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/SorenHJohansen/SattLint/badge)](https://securityscorecards.dev/viewer/?uri=github.com/SorenHJohansen/SattLint)

SattLint is a Python toolkit for SattLine projects. It provides configurable static analysis, ICF validation, graphics-rule analysis, and an interactive terminal UI.

---

## What SattLint Does

- Check whether a SattLine file parses correctly
- Analyze a full program or library together with its dependencies
- Find issues such as unused variables, written-but-never-read variables, and shadowing
- Validate ICF configuration files and graphics companion files

---

## Requirements

- **Windows** or **Linux**
- **Python 3.13 or newer**
- A local copy of your SattLine code

---

## Installation

### 1. Install SattLint

Install the released package with pip.

#### Linux

```bash
python3 -m pip install --user sattlint
```

#### Windows

```powershell
py -m pip install --user sattlint
```

This installs the `sattlint` command for your user account.

### 2. Verify

```bash
sattlint
```

### From source (for development)

To run the latest code from the repository instead of the released package:

```bash
git clone https://github.com/SorenHJohansen/SattLint.git
cd SattLint
python3 -m pip install --user .
```

---

## Quick Start

Start the interactive terminal UI:

```bash
sattlint
```

Open a configuration first (**File → Open Configuration** or **File → New
Configuration**), then use the **Analyze** view to pick analyzers and run
checks.

`sattlint` takes no arguments; all CLI subcommands and flags have been removed
and every capability is reachable from the Textual UI. Supplying arguments
returns a usage error (exit code `2`).

Exit codes:

- `0` — success (the TUI launched and quit cleanly)
- `2` — arguments were supplied to `sattlint`

---

## Interactive Shell

```bash
sattlint
```

Opens the Textual interactive terminal UI. The app starts with no
configuration loaded; use **File → Open Configuration** or **File → New
Configuration** to load or create a project.

Views (switch with `Ctrl+1`…`Ctrl+5` or the tabs at the top):

- **Analyze** — select analyzers to run and start checks
- **Results** — browse and inspect previous analysis runs
- **Configuration Settings** — set directories, targets, and mode
- **App Settings** — run history, logging, and Change Review output
- **Output** — generate Change Review artifacts

The **File** menu also offers **Help** (first-run guidance and keyboard
shortcuts) and **Quit**.

---

## Project Files (.slproj)

A `.slproj` project file captures all analysis settings in a single
checked-in file: targets, directories, mode, and output/cache paths. Paths
inside a `.slproj` are relative to the file itself, so projects are portable
across machines.

- Use **File → New Configuration** in the UI to scaffold a new
  `.slproj` in the current directory.
- Use **File → Open Configuration** to load an existing `.slproj`.
- Project settings merge over `~/.config/sattlint/config.toml` defaults.

Prefer a `.slproj` project file over editing `~/.config/sattlint/config.toml`
directly.

When SattLint analyzes a target, all SattLine discovery, dependency resolution,
and parsing run in `sattline-parser`'s project layer (`SattLineProject.load`);
SattLint then re-validates and re-indexes the result into its `ProjectGraph`
analysis index before running analyzers.

---

## First-Time Setup

The first time SattLint runs, it creates a config file automatically:

- **Windows:** `%APPDATA%\sattlint\config.toml`
- **Linux:** `~/.config/sattlint/config.toml`

For a portable, checked-in setup, create a `.slproj` project file from the
UI's **File → New Configuration** action instead; project settings merge over
these config defaults (see [Project Files](#project-files-slproj)).

### Configuration

1. Start SattLint with `sattlint`
2. Use **File → Open Configuration** or **File → New Configuration** to load a project
3. Select **Configuration Settings** (or press `Ctrl+3`) and configure:

   - `program_dir` — your SattLine program folder
   - `ABB_lib_dir` — shared or ABB libraries
   - `other_lib_dirs` — any additional libraries
   - `analyzed_programs_and_libraries` — what to analyze
   - `icf_dir` — directory containing ICF files used for ICF validation

   Changes are saved automatically to the configuration file.

4. Select **Analyze** to run checks

> **Note:** Use names without file extensions (e.g. `MyProgram`, not `MyProgram.s`).

---

## Updating

Update the released package from PyPI:

```bash
python3 -m pip install --user --upgrade sattlint
```

For a source checkout, reinstall with `python3 -m pip install --user .`.

---

## Graphics Validation

SattLint validates graphics companion files (`.g`) automatically whenever it
loads a program or library. Graphics issues — invalid bindings,
composite-record mismatches, and unresolved picture display paths — are
reported alongside the validation output for the affected target.

To dig deeper from the UI:

- Open **Analyze** and run **PictureDisplay paths** to check that every
  PictureDisplay button path points to a real screen or module.
- Run **ICF configuration** to validate the `.icf` connection files under
  `icf_dir` against their referenced programs.

---

## Common Problems

### `sattlint` not found

The `sattlint` script is not on your PATH. After a `pip install --user`,
scripts are placed in `~/.local/bin` on Linux (or
`%APPDATA%\Python\Python313\Scripts` on Windows); add that directory to your
PATH and restart your terminal.

### Python version error

Install Python 3.13+ and reinstall with `python3 -m pip install --user --upgrade sattlint`.

### Targets not found

- Names must not include file extensions
- Paths in config must be correct
- Mode (`official` / `draft`) must match your files

### Missing libraries

Add missing folders to `ABB_lib_dir` or `other_lib_dirs`.

### Results look outdated

Results are cached per configuration. Opening a configuration refreshes the
cached ASTs automatically; if results still look stale, re-run the analysis
from the **Analyze** view. Completed runs are kept in the **Results** view,
and **App Settings → Run History** controls how many runs are retained.

---

## For Developers

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, tests, and tooling.

---

## License

SattLint is released under the MIT License.
