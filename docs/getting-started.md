# Getting Started

This page takes you from an empty machine to a first analysis. For the full
project schema and every configuration key, continue with
[Project files](project-files.md) and [Configuration](configuration.md).

## 1. Install SattLint

SattLint requires Python 3.13 or newer.

### Linux

```bash
python3 -m pip install --user sattlint
```

### Windows

```powershell
py -m pip install --user sattlint
```

Confirm the installed command:

```bash
sattlint --version
```

If the command is not found, the scripts directory is not on `PATH`. On Linux
it is usually `~/.local/bin`; on Windows it is usually
`%APPDATA%\Python\Python313\Scripts`.

### From a source checkout

```bash
git clone https://github.com/SorenHJohansen/SattLint.git
cd SattLint
python3 -m pip install --user .
```

For development setup with the locked environment, see
[Development](development.md).

## 2. Create a project file

A `.slproj` file is the checked-in description of one analysis project. Create
a file named `.slproj` at the root of the SattLine code you want to analyze, or
create one from the interactive shell with **File → New Configuration**.

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

The shell starts with no project loaded. Use **File → Open Configuration** to
open a `.slproj`, then:

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
