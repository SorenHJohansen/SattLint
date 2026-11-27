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

## Documentation

The full documentation set lives in [docs/README.md](docs/README.md). Start
with the page that matches what you are doing:

- [Getting started](docs/getting-started.md) for installation and a first run
- [Project files](docs/project-files.md) and
  [Configuration](docs/configuration.md) for settings
- [CLI reference](docs/cli.md) for automation
- [Analyzers](docs/analyzers.md) for every check and its selection
- [Architecture](docs/architecture.md) for how the code is organized
- [Change Review](docs/change-review.md) for official-versus-draft reviews
- [Development](docs/development.md) for contributing

---

## Requirements

- **Windows** or **Linux**
- **Python 3.13 or newer**
- A local copy of your SattLine code

---

## Installation

### 1. Install SattLint

SattLint requires Python 3.13 or newer. Install the released package with
[pipx](https://pipx.pypa.io/), which keeps SattLint in its own environment and
puts the `sattlint` command on your `PATH`.

#### Linux

Install pipx with your distribution package manager, which avoids the
`externally-managed-environment` rejection from a system Python:

```bash
sudo apt install pipx        # Debian, Ubuntu
sudo dnf install pipx        # Fedora
sudo pacman -S python-pipx   # Arch
```

On an interpreter without that protection you can also bootstrap it with
`python3 -m pip install --user pipx`.

Then install SattLint and refresh `PATH`:

```bash
pipx ensurepath
pipx install sattlint
```

Restart the terminal after `ensurepath` changes `PATH`.

#### Windows

```powershell
py -m pip install --user pipx
py -m pipx ensurepath
pipx install sattlint
```

#### Virtual environment fallback

If pipx is not available, install into a dedicated virtual environment:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install sattlint
.venv/bin/sattlint --version
```

On Windows:

```powershell
py -m venv .venv
.venv\Scripts\python -m pip install sattlint
.venv\Scripts\sattlint --version
```

### 2. Verify

```bash
sattlint --version
sattlint analyzers list
```

### From source (for development)

To run the latest code from the repository:

```bash
git clone https://github.com/SorenHJohansen/SattLint.git
cd SattLint
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

On Windows, use `py -m venv .venv` and `.venv\Scripts\python -m pip install -e .`.

For the locked development environment, see [Development](docs/development.md).

---

## Quick Start

Start the interactive terminal UI:

```bash
sattlint
```

Open a configuration first (**File → Open Configuration** or **File → New
Configuration**), then use the **Analyze** view to pick analyzers and run
checks.

### Headless automation

The same capabilities are available without the TUI for scripts and AI agents:

```bash
sattlint project show --project app.slproj --format json
sattlint analyzers list --format json
sattlint analyze --project app.slproj --analyzer variables --format json
sattlint findings --run latest --module Root.A --group-by module --format json
sattlint show <finding-id> --format json
sattlint baseline update --project app.slproj
sattlint analyze --project app.slproj --baseline .sattlint-baseline.json --fail-on warning
```

Commands write data to stdout and diagnostics to stderr. JSON output carries a
`schema_version`; finding IDs are stable across runs. Text and Markdown output
use human-readable finding labels; structured output keeps the machine IDs.

A checked-in `.sattlint-baseline.json` lets a pipeline fail only on new or more
severe findings. `sattlint baseline update` accepts reviewed findings and prunes
stale ones, while `sattlint analyze --baseline` is the CI gate. `findings` stays
a read-only query and never applies the baseline.

Exit codes:

- `0` — success / no blocking findings
- `1` — findings were reported (`analyze --fail-on any`, the default)
- `2` — usage, configuration, project, or target-loading error
- `3` — internal error
- `130` — interrupted

With `--baseline`, exit `1` means an added or changed finding crossed the
`--fail-on` threshold.

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

### String capacities

A project file is version 2: `slproj_version = 2`. Version 2 requires a
top-level `[string_capacities]` table, so every checked-in project states the
capacity of each SattLine string datatype instead of inheriting a hidden
default:

```toml
slproj_version = 2

[string_capacities]
identstring = 15
tagstring = 30
string = 40
linestring = 80
maxstring = 140
```

The table is **required, not optional**. All five keys must be present, every
value must be a positive integer, and no other key is accepted. The values
above are the standard capacities, and they are what a new project is
scaffolded with.

A project file that omits the table, omits one of its keys, adds an unknown
key, or uses a non-positive value fails to load with an error that names the
problem. A version 1 project is rejected with a message naming the required
table and the standard values.

The values are not cosmetic. They drive:

- **String inference** — the configured capacity of each string datatype is
  used when literal, copy, and concatenation results are sized.
- **String validation** — the variables analyzer checks assignments and
  variable-to-parameter mappings against the destination capacity.
- **PictureDisplay path resolution** — display-path literals are sized from
  the configured capacities, so a resolved path and its destination agree.
- **The project cache key** — the table is part of the key, so changing a
  capacity invalidates cached analysis results.

### Analyzer selection

Every run names the analyzers it uses; there is no default set. List the keys
in the project file so a checked-in project reproduces its run:

```toml
analyzers = ["variables", "sfc", "dataflow"]
```

`sattlint analyzers list` prints the selectable keys. `--analyzer` on the
command line overrides the project list:

```bash
sattlint analyze --project app.slproj --analyzer variables --analyzer sfc
```

A run with no selection, on the command line or in the project file, fails
with an error that lists every selectable analyzer.

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
pipx upgrade sattlint
```

In a virtual environment, run `.venv/bin/python -m pip install --upgrade
sattlint` (on Windows, `.venv\Scripts\python`). For a source checkout, pull the
changes and reinstall with `.venv/bin/python -m pip install -e .`.

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

The `sattlint` script is not on your `PATH`. With pipx, run `pipx ensurepath`
and restart the terminal; pipx installs commands under `~/.local/bin` on Linux
and `%USERPROFILE%\.local\bin` on Windows. In a virtual environment, call
`.venv/bin/sattlint` or `.venv\Scripts\sattlint` directly.

### Python version error

SattLint needs Python 3.13 or newer. Install a current Python, then point the
existing pipx environment at it. `pipx upgrade` and `pipx reinstall` keep the
interpreter they were created with unless you name a new one:

```bash
pipx reinstall --python 3.14 sattlint
```

Use the interpreter version you installed. If pipx reports that SattLint is
already installed, run `pipx install --python 3.14 --force sattlint` instead.

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

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and
[docs/development.md](docs/development.md) for the code rules, validation
ladder, and analyzer development. The documentation index is
[docs/README.md](docs/README.md).

---

## License

SattLint is released under the MIT License.
