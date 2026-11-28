# Getting Started

This page takes you from an empty machine to a first analysis. For the full
project schema and every configuration key, continue with
[Project files](project-files.md) and [Configuration](configuration.md).

## 1. Install SattLint

SattLint requires Python 3.13 or newer. The released package is published on
PyPI under the name `sattlint`.

### Linux

Install [pipx](https://pipx.pypa.io/) with your distribution package manager so
SattLint gets its own environment and its command lands on `PATH`:

```bash
sudo apt install pipx        # Debian, Ubuntu
sudo dnf install pipx        # Fedora
sudo pacman -S python-pipx   # Arch
```

On an interpreter without the PEP 668 protection you can also bootstrap it with
`python3 -m pip install --user pipx`.

Then install SattLint and refresh `PATH`:

```bash
pipx ensurepath
pipx install sattlint
```

Restart the terminal after `ensurepath` changes `PATH`.

### Windows

```powershell
py -m pip install --user pipx
py -m pipx ensurepath
pipx install sattlint
```

### Virtual environment fallback

If pipx is not available, use a dedicated virtual environment:

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

Confirm the installed command:

```bash
sattlint --version
sattlint analyzers list
```

If the command is not found, see the installation troubleshooting in
[Troubleshooting](troubleshooting.md).

### From a source checkout

```bash
git clone https://github.com/SorenHJohansen/SattLint.git
cd SattLint
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

On Windows, use `py -m venv .venv` and
`.venv\Scripts\python -m pip install -e .`.

For development setup with the locked environment, see
[Development](development.md).

## 2. Create a project file

A `.slproj` file is the checked-in description of one analysis project. Create
a file named `.slproj` at the root of the SattLine code you want to analyze, or
create one from the interactive shell with **New Configuration**.

From a shell, start with the scaffold and let the target scan name the units:

```bash
cd path/to/your/sattline/code
sattlint project init
sattlint project targets
```

`project init` writes a minimal version 2 `.slproj` in the current directory and
refuses to overwrite an existing file. `project targets` lists each unit it can
find, with its inferred kind and resolved path, so you can copy valid names into
the project.

A minimal version 2 project looks like this:

```toml
slproj_version = 2
mode = "official"
analyzed_programs_and_libraries = ["MyProgram"]
analyzers = ["variables", "sfc"]

program_dir = "."
ABB_lib_dir = ""
icf_dir = ""
other_lib_dirs = []

[string_capacities]
identstring = 15
tagstring = 30
string = 40
linestring = 80
maxstring = 140
```

The `[string_capacities]` table is required, not optional. The standard values
above are what a new project is scaffolded with.

Paths are relative to the project file. `program_dir = "."` therefore means the
directory that holds `.slproj`, regardless of where you run `sattlint`.

Unit names are bare names. Use `MyProgram`, not `MyProgram.s` or
`MyProgram.x`.

## 3. Inspect the project

```bash
sattlint project show --format text
```

`project show` resolves project settings over the user configuration and prints
the effective targets, mode, analyzer selection, string capacities, paths, run
history directory, Change Review directory, and configuration file location.

Confirm that the schema, roots, and targets are usable before running:

```bash
sattlint project check
```

`project check` exits `0` when the project is valid and `1` when it names a
target that no configured root provides, a suffix that should be stripped, or a
required directory that is missing. An optional directory that no analyzer needs
does not fail the check.

To confirm the analyzer keys you can select:

```bash
sattlint analyzers list
```

## 4. Run an analysis

Run the analyzers selected in the project file:

```bash
sattlint analyze --project .slproj
```

Run specific analyzers, overriding the project list:

```bash
sattlint analyze --project .slproj --analyzer variables --analyzer sfc
```

Write machine-readable output and do not fail the command when findings exist:

```bash
sattlint analyze --project .slproj --format json --fail-on none --output findings.json
```

Exit codes are part of the contract. The default `--fail-on any` returns `1`
when findings exist, `0` when there are none, and `2` for usage, configuration,
project, or target-loading errors.

## 5. Query the stored run

A run is stored in run history unless `--no-save` is passed. Query it without
loading SattLine again:

```bash
sattlint findings --run latest
sattlint findings --run latest --module Root.A --group-by module --format json
sattlint show <finding-id> --format markdown
```

Finding IDs are stable for the same finding across runs.

## 6. Use the interactive shell

```bash
sattlint
```

The shell starts with no project loaded. Use **Open Configuration** to open a
`.slproj`, then:

1. Open **Configuration Settings** (`Ctrl+3`) to review targets, directories,
   and mode.
2. Open **Analyze** (`Ctrl+1`), select analyzers, and run them.
3. Open **Results** (`Ctrl+2`) to browse stored runs.
4. Open **Output** (`Ctrl+5`) to generate a Change Review.

For view details and keyboard shortcuts, see [Interactive UI](interactive-ui.md).

## 7. Generate a Change Review

A Change Review compares the official version of a project with its draft
version. Configure both versions in the project directories, open the
**Output** view, and choose **Generate Change Review**. SattLint writes one JSON
and one Markdown artifact per target into the configured review output
directory.

The review contains the semantic changes, the complete containing equation
blocks and sequences, related blocks that read or write the changed variables,
and the definitions of the variables involved. No analyzers run during review
generation.

See [Change Review](change-review.md) for the artifact contract.

## Common first-run problems

| Symptom | Cause | Fix |
| --- | --- | --- |
| `No analyzers selected` | Neither the command line nor the project names an analyzer. | Add `analyzers = [...]` or pass `--analyzer`. |
| `No .slproj found` | The current directory has no project file in its ancestry. | Pass `--project PATH` or create `.slproj`. |
| Target not found | Wrong name, wrong directory, or wrong mode. | Use a bare unit name and check `program_dir` and `mode`. |
| Configuration value error | A key has the wrong type or an unknown key. | See [Configuration](configuration.md). |
| `Missing required [string_capacities]` | The project file is version 1 or incomplete. | Add all five capacities. |

More answers are in [Troubleshooting](troubleshooting.md).
